"""
ArcGIS FeatureServer query module for PEIT Map Creator.

This module handles querying ArcGIS FeatureServers with spatial intersection
and converting the results to GeoDataFrames. Uses POST requests to avoid URI length
limitations and performs client-side filtering for precise polygon intersection.

Supports two query strategies:
1. Polygon query: Sends actual polygon geometry for precise server-side filtering
2. Envelope query: Sends bounding box (fallback for complex geometries or errors)

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
    geometry_type: Optional[str] = None,
    use_polygon_query: bool = True,
    esri_polygon_json: Optional[str] = None,
    polygon_query_metadata: Optional[Dict] = None
) -> Tuple[Optional[gpd.GeoDataFrame], Dict]:
    """
    Query an ArcGIS FeatureServer with spatial intersection.

    Supports two query strategies:
    1. Polygon query (default): Sends actual polygon geometry for precise
       server-side filtering. More efficient for complex/discontiguous polygons.
    2. Envelope query (fallback): Sends bounding box. Used when polygon query
       fails or is disabled.

    After server-side filtering, applies:
    - Client-side precise polygon intersection filter
    - Client-side geometry clipping (lines/polygons only)

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
    use_polygon_query : bool
        If True, send actual polygon geometry instead of bounding box (default: True)
    esri_polygon_json : str, optional
        Pre-computed ESRI JSON polygon string for query (avoids per-layer conversion)
    polygon_query_metadata : Dict, optional
        Pre-computed metadata about the polygon query (vertices, simplification info)

    Returns:
    --------
    Tuple[Optional[gpd.GeoDataFrame], Dict]
        GeoDataFrame of intersecting features and metadata dictionary

    Metadata Keys:
        - layer_name: Name of the layer
        - feature_count: Final count after filtering
        - server_count: Initial count from server query
        - filtered_count: Number of features filtered out by client-side intersection
        - query_method: 'polygon' | 'envelope' | 'envelope_fallback'
        - query_vertices: Vertex count used in polygon query (if applicable)
        - simplification_applied: Whether geometry was simplified (if applicable)
        - query_fallback_reason: Reason for fallback to envelope (if applicable)
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
        'query_time': 0,
        'query_method': 'envelope'  # Default, updated if polygon query succeeds
    }

    start_time = time.time()

    try:
        # Construct query URL
        query_url = f"{layer_url}/{layer_id}/query"

        # Extract polygon geometry for queries
        polygon_geometry = polygon_geom.geometry.iloc[0]

        # Determine query strategy
        query_method = 'envelope'
        result = None

        if use_polygon_query and esri_polygon_json:
            try:
                # Use pre-computed metadata if available
                if polygon_query_metadata:
                    metadata['query_vertices'] = polygon_query_metadata.get('query_vertices')
                    metadata['simplification_applied'] = polygon_query_metadata.get('simplification_applied', False)
                    if metadata['simplification_applied']:
                        metadata['original_vertices'] = polygon_query_metadata.get('original_vertices')

                # Build polygon query parameters using pre-computed ESRI JSON
                params = {
                    'where': '1=1',
                    'geometry': esri_polygon_json,
                    'geometryType': 'esriGeometryPolygon',
                    'spatialRel': 'esriSpatialRelIntersects',
                    'outFields': '*',
                    'returnGeometry': 'true',
                    'f': 'json',
                    'inSR': '4326',
                    'outSR': '4326'
                }

                query_vertices = metadata.get('query_vertices', 'N/A')
                logger.info(f"    - Using polygon query ({query_vertices} vertices)")
                logger.debug(f"Querying: {query_url}")
                response = requests.post(query_url, data=params, timeout=60)
                response.raise_for_status()

                result = response.json()

                # Check for ESRI error in response
                if 'error' in result:
                    error_msg = result['error'].get('message', 'Unknown error')
                    logger.warning(
                        f"    - Polygon query returned ESRI error: {error_msg}, "
                        f"falling back to envelope"
                    )
                    metadata['query_fallback_reason'] = f"esri_error: {error_msg}"
                    result = None
                else:
                    query_method = 'polygon'

            except requests.exceptions.Timeout:
                logger.warning(
                    "    - Polygon query timed out, falling back to envelope"
                )
                metadata['query_fallback_reason'] = "timeout"
            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"    - Polygon query failed ({e}), falling back to envelope"
                )
                metadata['query_fallback_reason'] = f"request_error: {str(e)}"
            except Exception as e:
                logger.warning(
                    f"    - Polygon query error ({e}), falling back to envelope"
                )
                metadata['query_fallback_reason'] = f"error: {str(e)}"

        # Fallback to envelope query if polygon query failed or is disabled
        if result is None:
            # Get bounding box (envelope) for spatial query
            bounds = polygon_geom.total_bounds
            envelope = {
                'xmin': bounds[0],
                'ymin': bounds[1],
                'xmax': bounds[2],
                'ymax': bounds[3],
                'spatialReference': {'wkid': 4326}
            }

            # Build envelope query parameters
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

            if use_polygon_query:
                # This is a fallback from polygon query
                query_method = 'envelope_fallback'
                logger.info("    - Using envelope query (fallback)")
            else:
                logger.info("    - Using envelope query")

            logger.debug(f"Querying: {query_url}")
            response = requests.post(query_url, data=params, timeout=60)
            response.raise_for_status()
            result = response.json()

        metadata['query_method'] = query_method

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

            logger.info(f"    - Server returned {initial_count} features")

            # Client-side filtering: precise polygon intersection
            # This filters out features that are in the query area but not in the actual polygon
            # (More relevant for envelope queries, but also catches edge cases for polygon queries)
            gdf = gdf[gdf.intersects(polygon_geometry)]

            metadata['server_count'] = initial_count
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
