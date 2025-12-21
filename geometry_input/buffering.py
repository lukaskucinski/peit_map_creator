"""
Geometry Buffering Module

Handles buffering point and line geometries in appropriate projected CRS,
then converting back to EPSG:4326 for web mapping compatibility.
"""

import math
from pyproj import CRS, Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform
from utils.logger import get_logger

logger = get_logger(__name__)

# Constants
FEET_TO_METERS = 0.3048
CONUS_ALBERS = 'EPSG:5070'  # Albers Equal Area Conic for CONUS
WEB_MERCATOR = 'EPSG:3857'  # Web Mercator for global coverage


def select_projected_crs(geom: BaseGeometry, original_crs: CRS) -> CRS:
    """
    Select appropriate projected CRS for accurate distance-based buffering.

    Strategy:
    1. Calculate geometry centroid
    2. Determine UTM zone from centroid longitude
    3. Determine hemisphere (North/South) from centroid latitude
    4. Return appropriate UTM CRS
    5. Fallback to Albers Equal Area (CONUS) or Web Mercator (global)

    Args:
        geom: Shapely geometry (should be in EPSG:4326)
        original_crs: Original CRS of the geometry

    Returns:
        Projected CRS suitable for metric buffering

    Note:
        UTM zones provide best accuracy for localized areas.
        Fallback CRS used if UTM determination fails or geometry spans multiple zones.
    """
    try:
        # Get centroid for CRS selection
        centroid = geom.centroid

        # If original CRS is not EPSG:4326, we need to get lon/lat
        if original_crs != CRS.from_epsg(4326):
            transformer = Transformer.from_crs(original_crs, CRS.from_epsg(4326), always_xy=True)
            lon, lat = transformer.transform(centroid.x, centroid.y)
        else:
            lon = centroid.x
            lat = centroid.y

        # Determine UTM zone from longitude
        # UTM zones are 6 degrees wide, starting at -180°
        utm_zone = int((lon + 180) / 6) + 1

        # Determine hemisphere
        if lat >= 0:
            hemisphere = 'north'
            epsg_code = 32600 + utm_zone  # WGS84 UTM North
        else:
            hemisphere = 'south'
            epsg_code = 32700 + utm_zone  # WGS84 UTM South

        utm_crs = CRS.from_epsg(epsg_code)
        logger.info(f"  - Selected UTM Zone {utm_zone}{hemisphere[0].upper()} (EPSG:{epsg_code}) for buffering")
        return utm_crs

    except Exception as e:
        logger.warning(f"Failed to determine UTM zone: {e}")

        # Fallback: Check if geometry is within CONUS bounds
        centroid = geom.centroid
        if original_crs == CRS.from_epsg(4326):
            lon, lat = centroid.x, centroid.y
        else:
            transformer = Transformer.from_crs(original_crs, CRS.from_epsg(4326), always_xy=True)
            lon, lat = transformer.transform(centroid.x, centroid.y)

        # CONUS approximate bounds: lon -125 to -66, lat 24 to 49
        if -125 <= lon <= -66 and 24 <= lat <= 49:
            logger.info(f"  - Using fallback: Albers Equal Area Conic (EPSG:5070) for CONUS")
            return CRS.from_string(CONUS_ALBERS)
        else:
            logger.info(f"  - Using fallback: Web Mercator (EPSG:3857) for global coverage")
            return CRS.from_string(WEB_MERCATOR)


def buffer_geometry_feet(geom: BaseGeometry,
                         buffer_feet: float,
                         original_crs: CRS) -> BaseGeometry:
    """
    Buffer a geometry by specified distance in feet, return result in EPSG:4326.

    Process:
    1. Select appropriate projected CRS (UTM or fallback)
    2. Transform geometry to projected CRS
    3. Convert buffer distance from feet to meters
    4. Apply buffer in meters
    5. Transform buffered geometry back to EPSG:4326

    Args:
        geom: Shapely geometry to buffer (should be in EPSG:4326)
        buffer_feet: Buffer distance in feet
        original_crs: Original CRS of the geometry

    Returns:
        Buffered geometry in EPSG:4326

    Note:
        Always returns polygon or multipolygon, even for point/line inputs.
    """
    if buffer_feet <= 0:
        raise ValueError(f"Buffer distance must be positive, got {buffer_feet} feet")

    logger.info(f"Buffering geometry by {buffer_feet} feet...")

    # Step 1: Select projected CRS
    projected_crs = select_projected_crs(geom, original_crs)

    # Step 2: Transform to projected CRS
    transformer_to_proj = Transformer.from_crs(
        CRS.from_epsg(4326),
        projected_crs,
        always_xy=True
    )

    try:
        geom_projected = transform(transformer_to_proj.transform, geom)
    except Exception as e:
        logger.error(f"Failed to transform geometry to projected CRS: {e}")
        raise ValueError(f"CRS transformation failed: {e}")

    # Step 3: Convert buffer distance from feet to meters
    buffer_meters = buffer_feet * FEET_TO_METERS
    logger.info(f"  - Buffer distance: {buffer_feet} ft = {buffer_meters:.2f} m")

    # Step 4: Apply buffer
    try:
        buffered_projected = geom_projected.buffer(buffer_meters)
    except Exception as e:
        logger.error(f"Failed to buffer geometry: {e}")
        raise ValueError(f"Buffer operation failed: {e}")

    logger.info(f"  - Buffered geometry type: {buffered_projected.geom_type}")

    # Step 5: Transform back to EPSG:4326
    transformer_to_wgs84 = Transformer.from_crs(
        projected_crs,
        CRS.from_epsg(4326),
        always_xy=True
    )

    try:
        buffered_wgs84 = transform(transformer_to_wgs84.transform, buffered_projected)
    except Exception as e:
        logger.error(f"Failed to transform buffered geometry back to EPSG:4326: {e}")
        raise ValueError(f"CRS back-transformation failed: {e}")

    logger.info(f"  ✓ Buffered geometry created in EPSG:4326")

    return buffered_wgs84


def calculate_buffer_area(buffered_geom: BaseGeometry) -> dict:
    """
    Calculate approximate area of buffered geometry for validation.

    Args:
        buffered_geom: Buffered geometry in EPSG:4326

    Returns:
        Dictionary with area in different units

    Note:
        Area calculations in EPSG:4326 (degrees) are approximate.
        Uses latitude-dependent scaling for more accurate results.
        For precise area, would need to reproject to equal-area CRS.
    """
    import math

    # Quick area calculation (approximate for lat/lon)
    area_degrees_sq = buffered_geom.area

    # Get centroid latitude for scaling
    # Longitude degrees shrink as you move away from equator
    centroid = buffered_geom.centroid
    lat = centroid.y

    # Latitude-dependent calculation (matches geometry_converters.py)
    # 1 degree latitude ≈ 69 miles (fairly constant)
    # 1 degree longitude ≈ 69 * cos(lat) miles
    lat_miles_per_deg = 69.0
    lon_miles_per_deg = 69.0 * math.cos(math.radians(lat))
    area_miles_sq_approx = area_degrees_sq * lat_miles_per_deg * lon_miles_per_deg

    # Convert to km for backward compatibility
    area_km_sq_approx = area_miles_sq_approx / 0.386102

    area_info = {
        'area_sq_degrees': area_degrees_sq,
        'area_sq_km_approx': round(area_km_sq_approx, 2),
        'area_sq_miles_approx': round(area_miles_sq_approx, 2)
    }

    logger.debug(f"  - Buffered area: ~{area_miles_sq_approx:.2f} sq miles "
                f"({area_km_sq_approx:.2f} sq km)")

    # Warning for very large buffers
    if area_miles_sq_approx > 100:
        logger.warning(f"Large buffer area detected: {area_miles_sq_approx:.1f} sq miles")
        logger.warning("This may result in very long query times or incomplete results")

    return area_info


def validate_buffer_distance(buffer_feet: float, geom_type: str) -> bool:
    """
    Validate that buffer distance is reasonable for the geometry type.

    Args:
        buffer_feet: Buffer distance in feet
        geom_type: Geometry type ('point', 'line', 'polygon')

    Returns:
        True if valid, raises ValueError if invalid

    Validation rules:
        - Point: 1 to 10,000 feet (0.19 to 1.89 miles)
        - Line: 1 to 5,000 feet (0.19 to 0.95 miles)
        - Polygon: No buffer allowed

    Note:
        These are soft limits for safety. Users can override if needed.
    """
    if geom_type == 'polygon':
        raise ValueError("Buffer should not be applied to polygon geometries")

    if buffer_feet < 1:
        raise ValueError(f"Buffer distance too small: {buffer_feet} feet (minimum 1 foot)")

    max_buffer = 10000 if geom_type == 'point' else 5000

    if buffer_feet > max_buffer:
        logger.warning(f"Large buffer distance: {buffer_feet} feet (>{max_buffer/5280:.1f} miles)")
        logger.warning("This may cause very long query times")

    return True
