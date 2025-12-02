"""
Geometry Input Loading Module

Handles reading geospatial files and detecting geometry types.
Supports multiple file formats through GeoPandas.
"""

import geopandas as gpd
import zipfile
import tempfile
from pathlib import Path
from typing import Tuple
from utils.logger import get_logger

logger = get_logger(__name__)


def load_geometry_file(file_path: str) -> gpd.GeoDataFrame:
    """
    Load geospatial file and return GeoDataFrame with original CRS.

    Supports: Shapefile, GeoPackage, KML, KMZ, GeoJSON, FileGeodatabase

    Args:
        file_path: Path to geospatial file

    Returns:
        GeoDataFrame with geometries in original CRS

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file cannot be read or has no CRS
    """
    file_path_obj = Path(file_path)

    if not file_path_obj.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")

    logger.info(f"Loading geometry from: {file_path}")

    try:
        # Handle ZIP files containing shapefiles by extracting to temp directory
        if file_path_obj.suffix.lower() == '.zip':
            logger.info("  - Detected ZIP file, extracting to read shapefile...")
            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(tmpdir)
                # Find the .shp file in extracted contents
                shp_files = list(Path(tmpdir).rglob('*.shp'))
                if not shp_files:
                    raise ValueError("No shapefile (.shp) found in ZIP archive")
                if len(shp_files) > 1:
                    logger.warning(f"  - Multiple shapefiles found in ZIP, using first: {shp_files[0].name}")
                logger.info(f"  - Found shapefile: {shp_files[0].name}")
                gdf = gpd.read_file(shp_files[0])
        else:
            gdf = gpd.read_file(file_path)
    except zipfile.BadZipFile:
        raise ValueError("Invalid ZIP file - file appears to be corrupted")
    except Exception as e:
        raise ValueError(f"Failed to read geospatial file: {e}")

    if gdf.empty:
        raise ValueError("Input file contains no features")

    if gdf.crs is None:
        raise ValueError(
            "Input file has no Coordinate Reference System (CRS) defined. "
            "Please assign a CRS to your data before using it as input."
        )

    logger.info(f"  - Loaded {len(gdf)} feature(s)")
    logger.info(f"  - Original CRS: {gdf.crs}")
    logger.debug(f"  - Geometry types: {gdf.geometry.geom_type.unique().tolist()}")

    return gdf


def detect_geometry_type(gdf: gpd.GeoDataFrame) -> str:
    """
    Detect the primary geometry type in the GeoDataFrame.

    Args:
        gdf: GeoDataFrame with geometries

    Returns:
        One of: 'point', 'line', 'polygon', or 'mixed'

    Note:
        - MultiPoint/MultiLineString/MultiPolygon are classified as their base type
        - If multiple different types exist, returns 'mixed'
    """
    geom_types = gdf.geometry.geom_type.unique()

    # Normalize geometry types
    normalized_types = set()
    for gtype in geom_types:
        if gtype in ['Point', 'MultiPoint']:
            normalized_types.add('point')
        elif gtype in ['LineString', 'MultiLineString']:
            normalized_types.add('line')
        elif gtype in ['Polygon', 'MultiPolygon']:
            normalized_types.add('polygon')
        else:
            logger.warning(f"Unsupported geometry type detected: {gtype}")
            normalized_types.add('unknown')

    if len(normalized_types) > 1:
        logger.warning(f"Mixed geometry types detected: {normalized_types}")
        return 'mixed'

    detected_type = list(normalized_types)[0]
    logger.info(f"  - Detected geometry type: {detected_type}")
    return detected_type


def validate_input_geometry(gdf: gpd.GeoDataFrame) -> Tuple[bool, str]:
    """
    Validate that input geometry is suitable for processing.

    Args:
        gdf: GeoDataFrame with geometries

    Returns:
        Tuple of (is_valid, error_message)
        If is_valid is True, error_message is empty string

    Checks:
        - Geometry column exists
        - At least one feature present
        - CRS is defined
        - No null geometries
        - Geometry types are supported
    """
    if 'geometry' not in gdf.columns:
        return False, "GeoDataFrame has no geometry column"

    if gdf.empty:
        return False, "GeoDataFrame contains no features"

    if gdf.crs is None:
        return False, "GeoDataFrame has no CRS defined"

    null_geoms = gdf.geometry.isnull().sum()
    if null_geoms > 0:
        return False, f"GeoDataFrame contains {null_geoms} null geometries"

    geom_types = gdf.geometry.geom_type.unique()
    supported_types = {'Point', 'MultiPoint', 'LineString', 'MultiLineString',
                      'Polygon', 'MultiPolygon'}
    unsupported = set(geom_types) - supported_types

    if unsupported:
        return False, f"Unsupported geometry types: {unsupported}"

    logger.debug("Input geometry validation passed")
    return True, ""


def extract_geometry_metadata(gdf: gpd.GeoDataFrame, file_path: str) -> dict:
    """
    Extract metadata about the input geometry for tracking.

    Args:
        gdf: GeoDataFrame with geometries
        file_path: Original file path

    Returns:
        Dictionary with metadata fields
    """
    geom_type = detect_geometry_type(gdf)

    metadata = {
        'original_file': str(Path(file_path).name),
        'original_crs': str(gdf.crs),
        'feature_count': len(gdf),
        'geometry_type': geom_type,
        'geometry_types_detail': gdf.geometry.geom_type.unique().tolist(),
        'bounds': gdf.total_bounds.tolist()  # [minx, miny, maxx, maxy]
    }

    return metadata
