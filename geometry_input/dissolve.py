"""
Geometry Dissolve Module

Handles dissolving multi-part geometries into single unified geometries
and repairing invalid geometries.
"""

import geopandas as gpd
from shapely.ops import unary_union
from shapely.geometry.base import BaseGeometry
from shapely import make_valid
from utils.logger import get_logger

logger = get_logger(__name__)


def dissolve_geometries(gdf: gpd.GeoDataFrame) -> BaseGeometry:
    """
    Dissolve all geometries in GeoDataFrame into a single unified geometry.

    Uses shapely.ops.unary_union to merge all features, handling:
    - Multiple separate geometries → single geometry (or MultiGeometry)
    - MultiPoint/MultiLineString/MultiPolygon → unified equivalent

    Args:
        gdf: GeoDataFrame with one or more geometries

    Returns:
        Single Shapely geometry (may be Multi* type)

    Example:
        Input: 3 separate polygons
        Output: 1 MultiPolygon or 1 merged Polygon (if overlapping)
    """
    if len(gdf) == 1:
        logger.debug("Single feature detected, returning as-is")
        return gdf.geometry.iloc[0]

    logger.info(f"Dissolving {len(gdf)} features into single geometry...")

    try:
        dissolved = unary_union(gdf.geometry)
    except Exception as e:
        logger.error(f"Failed to dissolve geometries: {e}")
        raise ValueError(f"Geometry dissolve failed: {e}")

    logger.info(f"  - Result: {dissolved.geom_type}")
    logger.debug(f"  - Is valid: {dissolved.is_valid}")

    return dissolved


def repair_invalid_geometry(geom: BaseGeometry) -> BaseGeometry:
    """
    Repair invalid geometries using make_valid() or buffer(0) technique.

    Common issues fixed:
    - Self-intersecting polygons
    - Duplicate vertices
    - Invalid ring orientations
    - Topology errors from CRS transformations

    Args:
        geom: Potentially invalid Shapely geometry

    Returns:
        Valid Shapely geometry

    Note:
        Uses shapely's make_valid() which applies OGC standards for fixing
        invalid geometries. Falls back to buffer(0) if make_valid fails.
    """
    if geom.is_valid:
        logger.debug("Geometry is valid, no repair needed")
        return geom

    logger.warning(f"Invalid geometry detected: {geom.geom_type}")
    logger.debug(f"  - Reason: {geom.is_valid_reason if hasattr(geom, 'is_valid_reason') else 'Unknown'}")

    try:
        # Primary repair method
        repaired = make_valid(geom)
        logger.info("  ✓ Geometry repaired using make_valid()")
        return repaired

    except Exception as e:
        logger.warning(f"make_valid() failed: {e}, trying buffer(0)...")

        try:
            # Fallback repair method
            repaired = geom.buffer(0)
            logger.info("  ✓ Geometry repaired using buffer(0)")
            return repaired

        except Exception as e2:
            logger.error(f"All repair attempts failed: {e2}")
            raise ValueError(f"Cannot repair invalid geometry: {e2}")


def extract_geometry_collection(geom: BaseGeometry, target_type: str) -> BaseGeometry:
    """
    Extract specific geometry types from a GeometryCollection.

    Useful when input contains mixed geometry types (e.g., both polygons and points).
    This function extracts only the desired type.

    Args:
        geom: GeometryCollection or other geometry type
        target_type: One of 'Point', 'LineString', 'Polygon'

    Returns:
        Single geometry of target type, or Multi* variant

    Example:
        Input: GeometryCollection([Polygon, Point, LineString])
        Target: 'Polygon'
        Output: Polygon (extracted)
    """
    if geom.geom_type != 'GeometryCollection':
        return geom

    logger.info(f"Extracting {target_type} geometries from GeometryCollection...")

    extracted = []
    for g in geom.geoms:
        if g.geom_type == target_type or g.geom_type == f"Multi{target_type}":
            extracted.append(g)

    if not extracted:
        raise ValueError(f"No {target_type} geometries found in collection")

    if len(extracted) == 1:
        return extracted[0]

    # Merge extracted geometries
    return unary_union(extracted)


def simplify_geometry(geom: BaseGeometry, tolerance: float = 0.0001) -> BaseGeometry:
    """
    Simplify geometry to reduce vertex count while preserving shape.

    Useful for very complex geometries that may cause performance issues.

    Args:
        geom: Shapely geometry to simplify
        tolerance: Simplification tolerance in degrees (for EPSG:4326)
                  Default 0.0001 ≈ 11 meters at equator

    Returns:
        Simplified geometry

    Note:
        Use with caution - may change geometry shape slightly.
        Only apply if vertex count is extremely high (>10,000).
    """
    vertex_count = len(geom.coords) if hasattr(geom, 'coords') else 0

    if vertex_count == 0 and hasattr(geom, 'exterior'):
        vertex_count = len(geom.exterior.coords)

    if vertex_count > 10000:
        logger.warning(f"Large geometry detected ({vertex_count} vertices), applying simplification...")
        simplified = geom.simplify(tolerance, preserve_topology=True)
        new_vertex_count = len(simplified.coords) if hasattr(simplified, 'coords') else len(simplified.exterior.coords)
        logger.info(f"  - Reduced from {vertex_count} to {new_vertex_count} vertices")
        return simplified

    return geom
