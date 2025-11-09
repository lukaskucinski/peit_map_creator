"""
Input polygon reader module for APPEIT Map Creator.

This module handles reading and preprocessing input polygon files from various
geospatial formats. All inputs are reprojected to WGS84 (EPSG:4326) for web mapping.

Functions:
    read_input_polygon: Read polygon from file and prepare for analysis
"""

import geopandas as gpd
from shapely.ops import unary_union
from utils.logger import get_logger

logger = get_logger(__name__)


def read_input_polygon(file_path: str) -> gpd.GeoDataFrame:
    """
    Read input polygon from various geospatial formats and prepare for analysis.

    Supports multiple file formats including Shapefile, KML, GeoPackage, GeoJSON,
    and FileGeodatabase. If the file contains multiple features, they are dissolved
    into a single polygon using union.

    Parameters:
    -----------
    file_path : str
        Path to the input file (supports: .shp, .kml, .kmz, .gpkg, .geojson, .gdb)

    Returns:
    --------
    gpd.GeoDataFrame
        GeoDataFrame with single polygon in EPSG:4326 (WGS84)

    Raises:
    -------
    FileNotFoundError
        If the input file doesn't exist
    ValueError
        If the file cannot be read or contains no geometries

    Example:
        >>> gdf = read_input_polygon('project_area.gpkg')
        >>> gdf.crs
        'EPSG:4326'
    """
    logger.info(f"Reading input polygon from: {file_path}")

    try:
        # Read the file
        gdf = gpd.read_file(file_path)

        logger.info(f"  - Original CRS: {gdf.crs}")
        logger.info(f"  - Number of features: {len(gdf)}")
        logger.info(f"  - Geometry types: {gdf.geometry.type.unique()}")

        # Warn if multiple features
        if len(gdf) > 1:
            logger.warning(
                f"File contains {len(gdf)} features. Using union of all geometries."
            )
            # Dissolve all features into one
            gdf = gpd.GeoDataFrame(
                geometry=[unary_union(gdf.geometry)],
                crs=gdf.crs
            )

        # Reproject to WGS84 if needed
        if gdf.crs != 'EPSG:4326':
            logger.info("  - Reprojecting to EPSG:4326...")
            gdf = gdf.to_crs('EPSG:4326')

        # Get bounds for reporting
        bounds = gdf.total_bounds
        logger.info(
            f"  - Bounding box: ({bounds[0]:.6f}, {bounds[1]:.6f}) to "
            f"({bounds[2]:.6f}, {bounds[3]:.6f})"
        )
        logger.info("  ✓ Polygon loaded successfully\n")

        return gdf

    except Exception as e:
        logger.error(f"Failed to read input polygon: {e}", exc_info=True)
        raise
