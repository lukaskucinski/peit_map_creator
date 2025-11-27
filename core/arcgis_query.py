"""
ArcGIS FeatureServer query module for APPEIT Map Creator.

This module handles querying ArcGIS FeatureServers with spatial intersection
and converting the results to GeoDataFrames. Uses POST requests to avoid URI length
limitations and performs client-side filtering for precise polygon intersection.

Functions:
    query_arcgis_layer: Query a FeatureServer layer and return intersecting features
"""

import geopandas as gpd
import requests
import json
import time
from typing import Tuple, Optional, Dict
from shapely.geometry.base import BaseGeometry
from utils.geometry_converters import convert_esri_to_geojson
from utils.logger import get_logger
from geometry_input.clipping import clip_geodataframe

logger = get_logger(__name__)


def query_arcgis_layer(
    layer_url: str,
    layer_id: int,
    polygon_geom: gpd.GeoDataFrame,
    layer_name: str = "Layer",
    clip_boundary: Optional[BaseGeometry] = None,
    geometry_type: Optional[str] = None
) -> Tuple[Optional[gpd.GeoDataFrame], Dict]:
    """
    Query an ArcGIS FeatureServer with spatial intersection.

    Uses a three-stage approach:
    1. Server-side: Query using bounding box (envelope) for speed
    2. Client-side: Filter to precise polygon intersection
    3. Client-side: Clip geometries to buffer boundary (lines/polygons only)

    Parameters:
    -----------
    layer_url : str
        Base URL of the FeatureServer
    layer_id : int
        Layer index within the FeatureServer
    polygon_geom : gpd.GeoDataFrame
        Input polygon for spatial intersection
    layer_name : str
        Name of the layer for logging
    clip_boundary : BaseGeometry, optional
        Geometry boundary to clip results to (typically 1-mile buffer around input)
    geometry_type : str, optional
        Type of geometry ('point', 'line', or 'polygon') for clipping decision

    Returns:
    --------
    Tuple[Optional[gpd.GeoDataFrame], Dict]
        GeoDataFrame of intersecting features and metadata dictionary

    Metadata Keys:
        - layer_name: Name of the layer
        - feature_count: Final count after filtering
        - bbox_count: Initial count from bounding box query
        - filtered_count: Number of features filtered out
        - clipping: Clipping statistics (if clipping was applied)
        - query_time: Total query time in seconds
        - warning: Any warnings (e.g., exceededTransferLimit)
        - error: Error message if query failed
    """
    logger.info(f"  Querying {layer_name}...")

    metadata = {
        'layer_name': layer_name,
        'feature_count': 0,
        'warning': None,
        'error': None,
        'query_time': 0
    }

    start_time = time.time()

    try:
        # Construct query URL
        query_url = f"{layer_url}/{layer_id}/query"

        # Get bounding box (envelope) for spatial query
        bounds = polygon_geom.total_bounds
        envelope = {
            'xmin': bounds[0],
            'ymin': bounds[1],
            'xmax': bounds[2],
            'ymax': bounds[3],
            'spatialReference': {'wkid': 4326}
        }

        # Build query parameters (using POST to avoid 414 URI too long errors)
        params = {
            'where': '1=1',
            'geometry': json.dumps(envelope),
            'geometryType': 'esriGeometryEnvelope',
            'spatialRel': 'esriSpatialRelIntersects',
            'outFields': '*',
            'returnGeometry': 'true',
            'f': 'json',
            'inSR': '4326',
            'outSR': '4326'
        }

        # Make POST request (avoids URL length limitations)
        logger.debug(f"Querying: {query_url}")
        response = requests.post(query_url, data=params, timeout=60)
        response.raise_for_status()

        # Parse response
        result = response.json()

        # Check for features
        if 'features' in result and len(result['features']) > 0:
            # Convert ESRI JSON to GeoDataFrame
            features = []
            for feature in result['features']:
                geojson_feat = convert_esri_to_geojson(feature)
                if geojson_feat:
                    features.append(geojson_feat)

            # Convert to GeoDataFrame
            gdf = gpd.GeoDataFrame.from_features(features, crs='EPSG:4326')
            initial_count = len(gdf)

            logger.info(f"    - Bounding box returned {initial_count} features")

            # Client-side filtering: precise polygon intersection
            # This filters out features that are in the bbox but not in the actual polygon
            polygon_geometry = polygon_geom.geometry.iloc[0]
            gdf = gdf[gdf.intersects(polygon_geometry)]

            metadata['bbox_count'] = initial_count
            metadata['filtered_count'] = initial_count - len(gdf)

            # Check if result exceeded limit
            if result.get('exceededTransferLimit', False):
                metadata['warning'] = f"Result exceeded server limit. Showing first {len(gdf)} features."
                logger.warning(f"    ⚠ {metadata['warning']}")

            if initial_count != len(gdf):
                logger.info(
                    f"    - Filtered to {len(gdf)} features "
                    f"(removed {initial_count - len(gdf)} outside polygon)"
                )

            # Client-side clipping: clip geometries to buffer boundary
            # Only applies to line and polygon geometries (points cannot extend beyond boundaries)
            if clip_boundary is not None and geometry_type in ('line', 'polygon') and len(gdf) > 0:
                gdf, clip_metadata = clip_geodataframe(
                    gdf, clip_boundary, layer_name, geometry_type
                )
                metadata['clipping'] = clip_metadata

            metadata['feature_count'] = len(gdf)
            logger.info(f"    ✓ Found {len(gdf)} intersecting features")

            metadata['query_time'] = time.time() - start_time
            return gdf, metadata
        else:
            logger.info("    - No intersecting features found")
            metadata['query_time'] = time.time() - start_time
            return None, metadata

    except requests.exceptions.RequestException as e:
        error_msg = f"Request failed: {str(e)}"
        logger.error(f"    ✗ {error_msg}")
        metadata['error'] = error_msg
        metadata['query_time'] = time.time() - start_time
        return None, metadata

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"    ✗ {error_msg}", exc_info=True)
        metadata['error'] = error_msg
        metadata['query_time'] = time.time() - start_time
        return None, metadata
