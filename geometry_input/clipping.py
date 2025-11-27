"""
Geometry Clipping Module

Clips line and polygon geometries to a buffer boundary around the input geometry.
This reduces output file sizes when large complex features intersect the project area.
"""

from typing import Tuple, Dict, Optional
import geopandas as gpd
from pyproj import CRS
from shapely.geometry import (
    Point, MultiPoint, LineString, MultiLineString,
    Polygon, MultiPolygon, GeometryCollection
)
from shapely.geometry.base import BaseGeometry
from shapely.validation import make_valid
from utils.logger import get_logger
from geometry_input.buffering import buffer_geometry_feet

logger = get_logger(__name__)

# Constants
FEET_PER_MILE = 5280


def create_clip_boundary(
    input_geom: BaseGeometry,
    buffer_miles: float,
    original_crs: CRS
) -> BaseGeometry:
    """
    Create a clip boundary by buffering the input geometry.

    Args:
        input_geom: Input geometry (typically the project polygon) in EPSG:4326
        buffer_miles: Buffer distance in miles
        original_crs: Original CRS of the geometry

    Returns:
        Buffered polygon in EPSG:4326 to use as clip boundary

    Note:
        Uses projected CRS for accurate distance-based buffering.
    """
    if buffer_miles <= 0:
        raise ValueError(f"Buffer distance must be positive, got {buffer_miles} miles")

    buffer_feet = buffer_miles * FEET_PER_MILE
    logger.info(f"Creating clip boundary with {buffer_miles} mile buffer ({buffer_feet} feet)...")

    clip_boundary = buffer_geometry_feet(input_geom, buffer_feet, original_crs)

    logger.info(f"  Clip boundary created in EPSG:4326")
    return clip_boundary


def count_vertices(geometry: BaseGeometry) -> int:
    """
    Count total vertices in a geometry.

    Handles Point, MultiPoint, LineString, MultiLineString,
    Polygon, MultiPolygon, and GeometryCollection types.

    Args:
        geometry: Shapely geometry object

    Returns:
        Total number of vertices/coordinates in the geometry
    """
    if geometry is None or geometry.is_empty:
        return 0

    if isinstance(geometry, Point):
        return 1
    elif isinstance(geometry, MultiPoint):
        return len(geometry.geoms)
    elif isinstance(geometry, LineString):
        return len(geometry.coords)
    elif isinstance(geometry, MultiLineString):
        return sum(len(line.coords) for line in geometry.geoms)
    elif isinstance(geometry, Polygon):
        # Exterior ring + interior rings (holes)
        count = len(geometry.exterior.coords)
        for interior in geometry.interiors:
            count += len(interior.coords)
        return count
    elif isinstance(geometry, MultiPolygon):
        return sum(count_vertices(poly) for poly in geometry.geoms)
    elif isinstance(geometry, GeometryCollection):
        return sum(count_vertices(geom) for geom in geometry.geoms)
    else:
        # Fallback: try to access coords
        try:
            return len(geometry.coords)
        except (AttributeError, NotImplementedError):
            return 0


def extract_geometry_type(
    geometry: BaseGeometry,
    target_type: str
) -> Optional[BaseGeometry]:
    """
    Extract geometries of a specific type from a potentially mixed result.

    When .intersection() returns a GeometryCollection, this extracts
    only the relevant geometry type (lines or polygons).

    Args:
        geometry: Result geometry (may be GeometryCollection)
        target_type: 'line' or 'polygon'

    Returns:
        Extracted geometry of the target type, or None if no matching geometries
    """
    if geometry is None or geometry.is_empty:
        return None

    # Direct match - return as-is
    if target_type == 'line':
        if isinstance(geometry, (LineString, MultiLineString)):
            return geometry
    elif target_type == 'polygon':
        if isinstance(geometry, (Polygon, MultiPolygon)):
            return geometry

    # Handle GeometryCollection
    if isinstance(geometry, GeometryCollection):
        extracted = []
        for geom in geometry.geoms:
            if target_type == 'line' and isinstance(geom, (LineString, MultiLineString)):
                if isinstance(geom, MultiLineString):
                    extracted.extend(geom.geoms)
                else:
                    extracted.append(geom)
            elif target_type == 'polygon' and isinstance(geom, (Polygon, MultiPolygon)):
                if isinstance(geom, MultiPolygon):
                    extracted.extend(geom.geoms)
                else:
                    extracted.append(geom)

        if not extracted:
            return None
        elif len(extracted) == 1:
            return extracted[0]
        else:
            if target_type == 'line':
                return MultiLineString(extracted)
            else:
                return MultiPolygon(extracted)

    # No match found
    return None


def clip_geodataframe(
    gdf: gpd.GeoDataFrame,
    clip_boundary: BaseGeometry,
    layer_name: str,
    geometry_type: str
) -> Tuple[gpd.GeoDataFrame, Dict]:
    """
    Clip all geometries in a GeoDataFrame to the clip boundary.

    Only clips line and polygon geometries. Point geometries are returned unchanged.
    Uses optimized vectorized operations with fallback to per-feature clipping
    for complex geometries that fail the vectorized approach.

    Args:
        gdf: GeoDataFrame with geometries to clip
        clip_boundary: Polygon boundary to clip geometries to
        layer_name: Name of the layer (for logging)
        geometry_type: Type of geometry ('point', 'line', or 'polygon')

    Returns:
        Tuple of (clipped GeoDataFrame, metadata dictionary)

    Metadata dictionary contains:
        - features_clipped: Number of features that were modified by clipping
        - lines_clipped: Count of line features clipped
        - polygons_clipped: Count of polygon features clipped
        - original_vertex_count: Total vertices before clipping
        - clipped_vertex_count: Total vertices after clipping
        - vertex_reduction_percent: Percentage reduction in vertices
        - empty_geometries_removed: Features removed due to empty geometry after clip
        - clip_failures: Features where clipping failed and original was kept
    """
    clip_metadata = {
        'features_clipped': 0,
        'lines_clipped': 0,
        'polygons_clipped': 0,
        'original_vertex_count': 0,
        'clipped_vertex_count': 0,
        'vertex_reduction_percent': 0.0,
        'empty_geometries_removed': 0,
        'clip_failures': 0
    }

    # Skip if empty GeoDataFrame
    if gdf is None or len(gdf) == 0:
        return gdf, clip_metadata

    # Skip point geometries - they can't extend beyond boundaries
    if geometry_type == 'point':
        logger.debug(f"  Skipping clipping for point layer: {layer_name}")
        return gdf, clip_metadata

    logger.info(f"  Clipping {len(gdf)} features for {layer_name}...")

    # Count original vertices (needed for statistics)
    original_vertex_count = sum(count_vertices(geom) for geom in gdf.geometry if geom is not None)
    clip_metadata['original_vertex_count'] = original_vertex_count

    # Step 1: Batch repair invalid geometries (vectorized validity check)
    invalid_mask = ~gdf.is_valid
    repair_count = invalid_mask.sum()

    if repair_count > 0:
        logger.debug(f"    Repairing {repair_count} invalid geometries...")
        gdf = gdf.copy()

        def safe_repair(geom):
            """Repair a single geometry with fallback to original."""
            try:
                repaired = make_valid(geom)
                if isinstance(repaired, GeometryCollection):
                    repaired = extract_geometry_type(repaired, geometry_type)
                return repaired if repaired and not repaired.is_empty else geom
            except Exception:
                return geom

        gdf.loc[invalid_mask, 'geometry'] = gdf.loc[invalid_mask, 'geometry'].apply(safe_repair)

    # Step 2: Try vectorized clipping using gpd.clip()
    try:
        clipped_gdf = gpd.clip(gdf, clip_boundary)
    except Exception as e:
        logger.debug(f"    Vectorized clip failed: {e}, falling back to per-feature clipping")
        # Fall back to per-feature clipping (slow path but handles edge cases)
        return _clip_per_feature(gdf, clip_boundary, layer_name, geometry_type, original_vertex_count)

    # Step 3: Handle GeometryCollection results from clipping
    if len(clipped_gdf) > 0:
        gc_mask = clipped_gdf.geometry.apply(
            lambda g: g is not None and isinstance(g, GeometryCollection)
        )
        if gc_mask.any():
            clipped_gdf = clipped_gdf.copy()
            clipped_gdf.loc[gc_mask, 'geometry'] = clipped_gdf.loc[gc_mask, 'geometry'].apply(
                lambda g: extract_geometry_type(g, geometry_type)
            )

    # Step 4: Remove empty/null geometries
    if len(clipped_gdf) > 0:
        empty_mask = clipped_gdf.geometry.isna() | clipped_gdf.geometry.apply(
            lambda g: g is None or g.is_empty
        )
        empty_count = empty_mask.sum()
        if empty_count > 0:
            clipped_gdf = clipped_gdf[~empty_mask]
            clip_metadata['empty_geometries_removed'] = int(empty_count)
            logger.info(f"    Removed {empty_count} features with empty geometries after clipping")

    # Step 5: Calculate statistics
    clipped_vertex_count = sum(count_vertices(g) for g in clipped_gdf.geometry if g is not None)
    clip_metadata['clipped_vertex_count'] = clipped_vertex_count

    # Determine if clipping actually occurred (based on vertex reduction)
    if original_vertex_count > 0 and clipped_vertex_count < original_vertex_count:
        features_clipped = len(clipped_gdf)
        clip_metadata['features_clipped'] = features_clipped
        if geometry_type == 'line':
            clip_metadata['lines_clipped'] = features_clipped
        elif geometry_type == 'polygon':
            clip_metadata['polygons_clipped'] = features_clipped

    # Calculate reduction percentage
    if original_vertex_count > 0:
        reduction = ((original_vertex_count - clipped_vertex_count) / original_vertex_count) * 100
        clip_metadata['vertex_reduction_percent'] = round(reduction, 1)

    # Log summary
    if clip_metadata['features_clipped'] > 0:
        logger.info(
            f"    Clipped {clip_metadata['features_clipped']} features: "
            f"{original_vertex_count:,} -> {clipped_vertex_count:,} vertices "
            f"({clip_metadata['vertex_reduction_percent']}% reduction)"
        )
    else:
        logger.info(f"    No features required clipping (all within buffer boundary)")

    return clipped_gdf, clip_metadata


def _clip_per_feature(
    gdf: gpd.GeoDataFrame,
    clip_boundary: BaseGeometry,
    layer_name: str,
    geometry_type: str,
    original_vertex_count: int
) -> Tuple[gpd.GeoDataFrame, Dict]:
    """
    Fallback per-feature clipping with repair attempts.

    This slower path is used when gpd.clip() fails, typically due to
    complex or invalid geometries. Uses multiple repair strategies.

    Args:
        gdf: GeoDataFrame with geometries to clip
        clip_boundary: Polygon boundary to clip geometries to
        layer_name: Name of the layer (for logging)
        geometry_type: Type of geometry ('line' or 'polygon')
        original_vertex_count: Pre-calculated vertex count for statistics

    Returns:
        Tuple of (clipped GeoDataFrame, metadata dictionary)
    """
    clip_metadata = {
        'features_clipped': 0,
        'lines_clipped': 0,
        'polygons_clipped': 0,
        'original_vertex_count': original_vertex_count,
        'clipped_vertex_count': 0,
        'vertex_reduction_percent': 0.0,
        'empty_geometries_removed': 0,
        'clip_failures': 0
    }

    clipped_geometries = []
    features_clipped = 0
    empty_indices = []
    clip_failures = 0

    for idx, row in gdf.iterrows():
        original_geom = row.geometry

        if original_geom is None or original_geom.is_empty:
            clipped_geometries.append(original_geom)
            continue

        # Working geometry (may be repaired)
        working_geom = original_geom

        # Perform intersection (clip) with fallback attempts
        clipped_geom = None
        clip_succeeded = False

        # Attempt 1: Direct intersection
        try:
            clipped_geom = working_geom.intersection(clip_boundary)
            clip_succeeded = True
        except Exception as e1:
            logger.debug(f"    Feature {idx} direct intersection failed: {e1}")

            # Attempt 2: Repair with buffer(0) and retry
            try:
                repaired_geom = working_geom.buffer(0)
                if repaired_geom is not None and not repaired_geom.is_empty:
                    clipped_geom = repaired_geom.intersection(clip_boundary)
                    clip_succeeded = True
                    logger.debug(f"    Feature {idx} clipped after buffer(0) repair")
            except Exception as e2:
                logger.debug(f"    Feature {idx} buffer(0) repair failed: {e2}")

                # Attempt 3: Try make_valid then buffer(0) then intersection
                try:
                    double_repaired = make_valid(working_geom)
                    if isinstance(double_repaired, GeometryCollection):
                        double_repaired = extract_geometry_type(double_repaired, geometry_type)
                    if double_repaired is not None and not double_repaired.is_empty:
                        double_repaired = double_repaired.buffer(0)
                        clipped_geom = double_repaired.intersection(clip_boundary)
                        clip_succeeded = True
                        logger.debug(f"    Feature {idx} clipped after double repair")
                except Exception as e3:
                    logger.warning(f"    Feature {idx} could not be clipped after all attempts")
                    clip_failures += 1

        if not clip_succeeded:
            # Keep original geometry if all clipping attempts failed
            clipped_geometries.append(original_geom)
            continue

        # Handle GeometryCollection results from intersection
        if isinstance(clipped_geom, GeometryCollection):
            clipped_geom = extract_geometry_type(clipped_geom, geometry_type)

        # Check if result is empty
        if clipped_geom is None or clipped_geom.is_empty:
            empty_indices.append(idx)
            clipped_geometries.append(None)
            continue

        # Validate the clipped geometry
        if not clipped_geom.is_valid:
            try:
                clipped_geom = make_valid(clipped_geom)
                if isinstance(clipped_geom, GeometryCollection):
                    clipped_geom = extract_geometry_type(clipped_geom, geometry_type)
            except Exception:
                pass  # Use potentially invalid geometry rather than failing

        if clipped_geom is None or clipped_geom.is_empty:
            empty_indices.append(idx)
            clipped_geometries.append(None)
            continue

        clipped_geometries.append(clipped_geom)

        # Track as clipped (simplified - count based on vertex change at end)
        features_clipped += 1

    # Update GeoDataFrame with clipped geometries
    gdf = gdf.copy()
    gdf['geometry'] = clipped_geometries

    # Remove features with empty geometries
    if empty_indices:
        gdf = gdf.drop(empty_indices)
        clip_metadata['empty_geometries_removed'] = len(empty_indices)
        logger.info(f"    Removed {len(empty_indices)} features with empty geometries after clipping")

    # Count clipped vertices
    clipped_vertex_count = sum(count_vertices(geom) for geom in gdf.geometry if geom is not None)
    clip_metadata['clipped_vertex_count'] = clipped_vertex_count
    clip_metadata['clip_failures'] = clip_failures

    # Update feature counts based on actual vertex reduction
    if original_vertex_count > 0 and clipped_vertex_count < original_vertex_count:
        clip_metadata['features_clipped'] = features_clipped
        if geometry_type == 'line':
            clip_metadata['lines_clipped'] = features_clipped
        elif geometry_type == 'polygon':
            clip_metadata['polygons_clipped'] = features_clipped

    # Calculate reduction percentage
    if original_vertex_count > 0:
        reduction = ((original_vertex_count - clipped_vertex_count) / original_vertex_count) * 100
        clip_metadata['vertex_reduction_percent'] = round(reduction, 1)

    # Log summary
    if clip_metadata['features_clipped'] > 0:
        logger.info(
            f"    Clipped {clip_metadata['features_clipped']} features: "
            f"{original_vertex_count:,} -> {clipped_vertex_count:,} vertices "
            f"({clip_metadata['vertex_reduction_percent']}% reduction)"
        )
    else:
        logger.info(f"    No features required clipping (all within buffer boundary)")

    if clip_failures > 0:
        logger.warning(f"    {clip_failures} features could not be clipped (original geometry kept)")

    return gdf, clip_metadata


def aggregate_clip_metadata(layer_metadata_list: list) -> Dict:
    """
    Aggregate clipping statistics across all layers.

    Args:
        layer_metadata_list: List of metadata dictionaries from each layer

    Returns:
        Dictionary with aggregated clipping statistics
    """
    summary = {
        'total_features_clipped': 0,
        'total_lines_clipped': 0,
        'total_polygons_clipped': 0,
        'total_original_vertices': 0,
        'total_clipped_vertices': 0,
        'total_empty_removed': 0,
        'total_clip_failures': 0,
        'overall_vertex_reduction_percent': 0.0
    }

    for meta in layer_metadata_list:
        if 'clipping' in meta and meta['clipping']:
            clip_data = meta['clipping']
            summary['total_features_clipped'] += clip_data.get('features_clipped', 0)
            summary['total_lines_clipped'] += clip_data.get('lines_clipped', 0)
            summary['total_polygons_clipped'] += clip_data.get('polygons_clipped', 0)
            summary['total_original_vertices'] += clip_data.get('original_vertex_count', 0)
            summary['total_clipped_vertices'] += clip_data.get('clipped_vertex_count', 0)
            summary['total_empty_removed'] += clip_data.get('empty_geometries_removed', 0)
            summary['total_clip_failures'] += clip_data.get('clip_failures', 0)

    # Calculate overall reduction percentage
    if summary['total_original_vertices'] > 0:
        reduction = (
            (summary['total_original_vertices'] - summary['total_clipped_vertices'])
            / summary['total_original_vertices']
        ) * 100
        summary['overall_vertex_reduction_percent'] = round(reduction, 1)

    return summary
