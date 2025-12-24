"""
Geometry Processing Pipeline

Orchestrates the complete workflow for processing input geometries:
1. Load geometry file
2. Validate and detect geometry type
3. Dissolve to single geometry
4. Apply buffer (for points/lines only)
5. Repair and validate
6. Return standardized GeoDataFrame in EPSG:4326

Note on Feature Collections (mixed geometry types):
When input contains mixed geometry types (e.g., points + lines + polygons),
the pipeline:
1. Separates geometries by type
2. Buffers points and lines individually
3. Combines all polygons (original + buffered) into a unified polygon output
"""

import geopandas as gpd
from pyproj import CRS
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection
from shapely.ops import unary_union
from typing import Tuple, List, Optional

from geometry_input.load_input import (
    load_geometry_file,
    detect_geometry_type,
    validate_input_geometry,
    extract_geometry_metadata
)
from geometry_input.dissolve import (
    dissolve_geometries,
    repair_invalid_geometry,
    simplify_geometry
)
from geometry_input.buffering import (
    buffer_geometry_feet,
    calculate_buffer_area,
    validate_buffer_distance
)
from utils.logger import get_logger

logger = get_logger(__name__)


def _separate_geometry_types(gdf: gpd.GeoDataFrame) -> dict:
    """
    Separate geometries in a GeoDataFrame by type.

    Args:
        gdf: GeoDataFrame with potentially mixed geometry types

    Returns:
        Dictionary with keys 'point', 'line', 'polygon' containing lists of geometries
    """
    result = {'point': [], 'line': [], 'polygon': []}

    for geom in gdf.geometry:
        geom_type = geom.geom_type
        if geom_type in ['Point', 'MultiPoint']:
            result['point'].append(geom)
        elif geom_type in ['LineString', 'MultiLineString']:
            result['line'].append(geom)
        elif geom_type in ['Polygon', 'MultiPolygon']:
            result['polygon'].append(geom)
        elif geom_type == 'GeometryCollection':
            # Recursively extract from GeometryCollection
            for sub_geom in geom.geoms:
                sub_type = sub_geom.geom_type
                if sub_type in ['Point', 'MultiPoint']:
                    result['point'].append(sub_geom)
                elif sub_type in ['LineString', 'MultiLineString']:
                    result['line'].append(sub_geom)
                elif sub_type in ['Polygon', 'MultiPolygon']:
                    result['polygon'].append(sub_geom)

    return result


def _process_mixed_geometries(gdf: gpd.GeoDataFrame,
                               buffer_distance_feet: float,
                               original_crs: CRS) -> tuple:
    """
    Process mixed geometry types by buffering points/lines and combining with polygons.

    Args:
        gdf: GeoDataFrame with mixed geometry types
        buffer_distance_feet: Buffer distance for points and lines
        original_crs: Original CRS of the data

    Returns:
        Tuple of (unified_polygon, buffer_info, was_buffered, original_gdf)
        - original_gdf: GeoDataFrame with pre-buffer geometry (for display), or None if only polygons
    """
    logger.info("Processing mixed geometry types (FeatureCollection)...")

    # First, ensure we're working in EPSG:4326
    if gdf.crs != CRS.from_epsg(4326):
        logger.info(f"  - Converting from {gdf.crs} to EPSG:4326 before processing...")
        gdf = gdf.to_crs('EPSG:4326')

    # Separate geometries by type
    separated = _separate_geometry_types(gdf)

    logger.info(f"  - Found: {len(separated['point'])} point(s), "
                f"{len(separated['line'])} line(s), {len(separated['polygon'])} polygon(s)")

    all_polygons = []
    buffer_applied = False
    buffer_info = {}
    original_geometries = []  # Store pre-buffer geometries for display

    # Process polygons (no buffering needed)
    if separated['polygon']:
        polygon_union = unary_union(separated['polygon'])
        polygon_union = repair_invalid_geometry(polygon_union)
        all_polygons.append(polygon_union)
        logger.info(f"  - Added {len(separated['polygon'])} polygon(s) directly")

    # Buffer and add points (preserve original for display)
    if separated['point']:
        point_union = unary_union(separated['point'])
        point_union = repair_invalid_geometry(point_union)
        original_geometries.append(point_union)  # Save original point(s)

        logger.info(f"  - Buffering {len(separated['point'])} point(s) by {buffer_distance_feet} ft...")
        buffered_points = buffer_geometry_feet(point_union, buffer_distance_feet, CRS.from_epsg(4326))
        all_polygons.append(buffered_points)
        buffer_applied = True

    # Buffer and add lines (preserve original for display)
    if separated['line']:
        line_union = unary_union(separated['line'])
        line_union = repair_invalid_geometry(line_union)
        original_geometries.append(line_union)  # Save original line(s)

        logger.info(f"  - Buffering {len(separated['line'])} line(s) by {buffer_distance_feet} ft...")
        buffered_lines = buffer_geometry_feet(line_union, buffer_distance_feet, CRS.from_epsg(4326))
        all_polygons.append(buffered_lines)
        buffer_applied = True

    # Combine all polygons into one
    if not all_polygons:
        raise ValueError("No valid geometries found after processing mixed types")

    unified = unary_union(all_polygons)
    unified = repair_invalid_geometry(unified)

    # Calculate buffer area if buffering was applied
    if buffer_applied:
        buffer_info = calculate_buffer_area(unified)

    logger.info(f"  ✓ Combined into single {unified.geom_type}")

    # Create original geometry GeoDataFrame for display (only if we have points/lines)
    original_gdf = None
    if original_geometries:
        # Combine original geometries (may be mixed Point + LineString)
        if len(original_geometries) == 1:
            original_geom = original_geometries[0]
        else:
            original_geom = GeometryCollection(original_geometries)
        original_gdf = gpd.GeoDataFrame([{'geometry': original_geom}], crs='EPSG:4326')
        logger.info(f"  ✓ Preserved original geometry for display: {original_geom.geom_type}")

    return unified, buffer_info, buffer_applied, original_gdf


def process_input_geometry(file_path: str,
                          buffer_distance_feet: float = 500,
                          apply_simplification: bool = False) -> Tuple[gpd.GeoDataFrame, dict, Optional[gpd.GeoDataFrame]]:
    """
    Process input geometry file and return standardized GeoDataFrame in EPSG:4326.

    Complete workflow:
    1. Load geometry from file
    2. Validate input
    3. Detect geometry type (point/line/polygon)
    4. Dissolve multi-part geometries
    5. Apply buffer to point/line geometries (converts to polygon)
    6. Skip buffer for polygon geometries
    7. Repair any invalid geometries
    8. Convert to EPSG:4326 (WGS84)
    9. Return single-row GeoDataFrame

    Args:
        file_path: Path to geospatial file (Shapefile, GeoPackage, KML, etc.)
        buffer_distance_feet: Buffer distance in feet (default 500)
                             Only applied to point/line geometries
        apply_simplification: Whether to simplify complex geometries (default False)

    Returns:
        Tuple of (GeoDataFrame, metadata_dict, original_gdf)
        - GeoDataFrame: Single-row GeoDataFrame with processed geometry in EPSG:4326
        - metadata_dict: Tracking information about transformations applied
        - original_gdf: GeoDataFrame with pre-buffer geometry for display, or None if no buffer applied

    Raises:
        FileNotFoundError: If input file doesn't exist
        ValueError: If geometry is invalid or unsupported

    Example:
        >>> polygon_gdf, metadata, original_gdf = process_input_geometry(
        ...     'path/to/point.gpkg',
        ...     buffer_distance_feet=1000
        ... )
        >>> print(metadata['geometry_type'])  # 'point'
        >>> print(metadata['buffer_applied'])  # True
        >>> print(polygon_gdf.crs)  # EPSG:4326
        >>> print(original_gdf is not None)  # True - original point for display
    """
    logger.info("="*80)
    logger.info("GEOMETRY PROCESSING PIPELINE")
    logger.info("="*80)

    # Step 1: Load geometry file
    gdf = load_geometry_file(file_path)

    # Step 2: Validate input
    is_valid, error_msg = validate_input_geometry(gdf)
    if not is_valid:
        raise ValueError(f"Input validation failed: {error_msg}")

    # Step 3: Extract metadata before processing
    metadata = extract_geometry_metadata(gdf, file_path)

    # Step 4: Detect geometry type
    geom_type = detect_geometry_type(gdf)
    metadata['detected_geometry_type'] = geom_type

    # Track original geometry for display (only set when buffer is applied)
    original_gdf = None

    # Step 5: Handle mixed geometries specially (FeatureCollection with different types)
    if geom_type == 'mixed':
        logger.info("Mixed geometry types detected - processing each type separately")

        # Use special mixed geometry processing
        dissolved_geom, buffer_info, buffer_applied, original_gdf = _process_mixed_geometries(
            gdf, buffer_distance_feet, gdf.crs
        )

        metadata['buffer_applied'] = buffer_applied
        if buffer_applied:
            metadata['buffer_distance_feet'] = buffer_distance_feet
            metadata['buffer_distance_meters'] = round(buffer_distance_feet * 0.3048, 2)
            metadata['buffer_area'] = buffer_info
            metadata['mixed_geometry_processing'] = True

    else:
        # Standard processing for single geometry type

        # Step 5: Dissolve geometries into single unified geometry
        dissolved_geom = dissolve_geometries(gdf)

        # Step 6: Repair if needed
        dissolved_geom = repair_invalid_geometry(dissolved_geom)

        # Step 7: Apply simplification if requested and geometry is complex
        if apply_simplification:
            dissolved_geom = simplify_geometry(dissolved_geom)

        # Step 8: Determine if buffering is needed
        buffer_applied = False
        buffer_info = {}

        # Check if geometry type requires buffering
        needs_buffer = geom_type in ['point', 'line']

        # Also check actual geometry type after dissolve (handles edge cases)
        actual_geom_type = dissolved_geom.geom_type
        is_point_or_line = actual_geom_type in ['Point', 'MultiPoint', 'LineString', 'MultiLineString']

        if needs_buffer or is_point_or_line:
            logger.info(f"Geometry type '{geom_type}' requires buffering")

            # Validate buffer distance
            try:
                validate_buffer_distance(buffer_distance_feet, geom_type)
            except ValueError as e:
                logger.warning(f"Buffer validation warning: {e}")
                # Continue anyway - validation is advisory

            # Convert to EPSG:4326 first (if not already)
            if gdf.crs != CRS.from_epsg(4326):
                logger.info(f"  - Converting from {gdf.crs} to EPSG:4326 before buffering...")
                temp_gdf = gpd.GeoDataFrame([{'geometry': dissolved_geom}], crs=gdf.crs)
                temp_gdf = temp_gdf.to_crs('EPSG:4326')
                dissolved_geom = temp_gdf.geometry.iloc[0]

            # Preserve original geometry for display BEFORE buffering
            original_gdf = gpd.GeoDataFrame([{'geometry': dissolved_geom}], crs='EPSG:4326')
            logger.info(f"  ✓ Preserved original geometry for display: {dissolved_geom.geom_type}")

            # Apply buffer
            original_crs = CRS.from_epsg(4326)
            buffered_geom = buffer_geometry_feet(dissolved_geom, buffer_distance_feet, original_crs)

            # Calculate area info
            buffer_info = calculate_buffer_area(buffered_geom)

            # Update geometry and metadata
            dissolved_geom = buffered_geom
            buffer_applied = True

            metadata['buffer_applied'] = True
            metadata['buffer_distance_feet'] = buffer_distance_feet
            metadata['buffer_distance_meters'] = round(buffer_distance_feet * 0.3048, 2)
            metadata['buffer_area'] = buffer_info

        else:
            logger.info(f"Geometry type '{geom_type}' is polygon - skipping buffer")
            metadata['buffer_applied'] = False

            # Calculate area for polygons (needed for area validation even without buffering)
            # First ensure we're in EPSG:4326 for consistent area calculation
            if gdf.crs != CRS.from_epsg(4326):
                temp_gdf = gpd.GeoDataFrame([{'geometry': dissolved_geom}], crs=gdf.crs)
                temp_gdf = temp_gdf.to_crs('EPSG:4326')
                area_geom = temp_gdf.geometry.iloc[0]
            else:
                area_geom = dissolved_geom

            # Calculate area using the same function as buffered geometries
            polygon_area_info = calculate_buffer_area(area_geom)
            metadata['buffer_area'] = polygon_area_info
            logger.info(f"  - Polygon area: ~{polygon_area_info.get('area_sq_miles_approx', 0):.2f} sq miles")

        # Step 9: Ensure geometry is in EPSG:4326
        if not buffer_applied:  # If buffer was applied, already in EPSG:4326
            if gdf.crs != CRS.from_epsg(4326):
                logger.info(f"  - Converting from {gdf.crs} to EPSG:4326...")
                temp_gdf = gpd.GeoDataFrame([{'geometry': dissolved_geom}], crs=gdf.crs)
                temp_gdf = temp_gdf.to_crs('EPSG:4326')
                dissolved_geom = temp_gdf.geometry.iloc[0]

    # Step 10: Final validation and repair
    dissolved_geom = repair_invalid_geometry(dissolved_geom)

    # Step 11: Create output GeoDataFrame
    output_gdf = gpd.GeoDataFrame(
        [{'geometry': dissolved_geom}],
        crs='EPSG:4326'
    )

    # Step 12: Update final metadata
    metadata['final_crs'] = 'EPSG:4326'
    metadata['final_geometry_type'] = dissolved_geom.geom_type
    metadata['final_bounds'] = output_gdf.total_bounds.tolist()
    metadata['is_valid'] = dissolved_geom.is_valid

    logger.info("="*80)
    logger.info("GEOMETRY PROCESSING COMPLETE")
    logger.info("="*80)
    logger.info(f"  ✓ Input: {metadata['geometry_type']} ({metadata['feature_count']} features)")
    logger.info(f"  ✓ Output: {metadata['final_geometry_type']} (1 feature)")
    logger.info(f"  ✓ CRS: {metadata['original_crs']} → {metadata['final_crs']}")
    logger.info(f"  ✓ Buffer applied: {metadata.get('buffer_applied', False)}")
    if metadata.get('buffer_applied'):
        logger.info(f"  ✓ Buffer distance: {buffer_distance_feet} ft")
    # Always show area if available (for both buffered and polygon inputs)
    if metadata.get('buffer_area'):
        area_sq_miles = metadata['buffer_area'].get('area_sq_miles_approx', 0)
        logger.info(f"  ✓ Geometry area: ~{area_sq_miles:.2f} sq miles")
    if original_gdf is not None:
        logger.info(f"  ✓ Original geometry preserved for display")
    logger.info("="*80)

    return output_gdf, metadata, original_gdf


def process_input_geometry_simple(file_path: str,
                                  buffer_distance_feet: float = 500) -> gpd.GeoDataFrame:
    """
    Simplified version that returns only the GeoDataFrame (no metadata or original geometry).

    Use this when you don't need tracking metadata, only the processed geometry.

    Args:
        file_path: Path to geospatial file
        buffer_distance_feet: Buffer distance in feet (default 500)

    Returns:
        Single-row GeoDataFrame with processed geometry in EPSG:4326
    """
    gdf, _, _ = process_input_geometry(file_path, buffer_distance_feet)
    return gdf
