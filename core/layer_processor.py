"""
Layer processing module for PEIT Map Creator.

This module handles batch processing of multiple FeatureServer layers.
Queries all configured layers and collects results and metadata.

Functions:
    process_all_layers: Query all configured layers and return results
"""

import geopandas as gpd
from typing import Dict, List, Optional, Set, Tuple
from pyproj import CRS
from shapely.geometry.base import BaseGeometry
from core.arcgis_query import query_arcgis_layer
from geometry_input.clipping import create_clip_boundary, aggregate_clip_metadata
from config.config_loader import load_geometry_settings
from utils.logger import get_logger
from utils.state_filter import get_intersecting_states, filter_layers_by_state

logger = get_logger(__name__)


def process_all_layers(
    polygon_gdf: gpd.GeoDataFrame,
    config: Dict
) -> Tuple[Dict[str, gpd.GeoDataFrame], Dict[str, Dict], Dict, Optional[BaseGeometry]]:
    """
    Query all configured FeatureServer layers.

    Iterates through all layers defined in the configuration and queries
    each one for features that intersect the input polygon. Optionally clips
    line and polygon geometries to a buffer boundary around the input polygon.

    Parameters:
    -----------
    polygon_gdf : gpd.GeoDataFrame
        Input polygon for intersection
    config : Dict
        Configuration dictionary with layer definitions

    Returns:
    --------
    Tuple[Dict[str, gpd.GeoDataFrame], Dict[str, Dict], Dict, Optional[BaseGeometry]]
        - Dictionary of layer results (layer name -> GeoDataFrame)
        - Dictionary of metadata (layer name -> metadata dict)
        - Dictionary of clipping summary statistics
        - Clip boundary geometry (Shapely polygon in EPSG:4326), or None if clipping disabled

    Example:
        >>> results, metadata, clip_summary, clip_boundary = process_all_layers(polygon_gdf, config)
        >>> len(results)  # Number of layers with features
        3
        >>> metadata['RCRA Sites']['feature_count']
        152
        >>> clip_summary['total_features_clipped']
        45
    """
    logger.info("=" * 80)
    logger.info("Querying ArcGIS FeatureServers")
    logger.info("=" * 80)

    # Load geometry settings and create clip boundary if enabled
    geometry_settings = load_geometry_settings(config)
    clip_boundary = None
    clip_enabled = geometry_settings.get('clip_results_to_buffer', True)
    clip_buffer_miles = geometry_settings.get('clip_buffer_miles', 1.0)

    if clip_enabled:
        logger.info(f"Geometry clipping enabled: {clip_buffer_miles} mile buffer")
        try:
            clip_boundary = create_clip_boundary(
                polygon_gdf.geometry.iloc[0],
                clip_buffer_miles,
                CRS.from_epsg(4326)
            )
        except Exception as e:
            logger.warning(f"Failed to create clip boundary: {e}")
            logger.warning("Continuing without geometry clipping")
            clip_boundary = None

    # State-based layer filtering
    state_filter_enabled = geometry_settings.get('state_filter_enabled', True)
    intersecting_states: Set[str] = set()
    layers_to_process = config['layers']
    skipped_count = 0
    skipped_layers: List[str] = []

    if state_filter_enabled:
        intersecting_states = get_intersecting_states(polygon_gdf, clip_buffer_miles)
        if intersecting_states:
            layers_to_process, skipped_count, skipped_layers = filter_layers_by_state(
                config['layers'], intersecting_states
            )
            logger.info(f"State filter: {len(intersecting_states)} state(s) detected: "
                        f"{', '.join(sorted(intersecting_states))}")
            logger.info(f"Processing {len(layers_to_process)} of {len(config['layers'])} layers "
                        f"({skipped_count} skipped)")
        else:
            logger.info("State filter: No states detected (processing all layers)")

    results = {}
    metadata = {}

    for layer_config in layers_to_process:
        layer_name = layer_config['name']
        geometry_type = layer_config.get('geometry_type', None)

        gdf, meta = query_arcgis_layer(
            layer_url=layer_config['url'],
            layer_id=layer_config['layer_id'],
            polygon_geom=polygon_gdf,
            layer_name=layer_name,
            clip_boundary=clip_boundary,
            geometry_type=geometry_type
        )

        if gdf is not None:
            results[layer_name] = gdf

        metadata[layer_name] = meta
        logger.info("")  # Blank line between layers

    # Summary
    logger.info("=" * 80)
    logger.info("Query Summary")
    logger.info("=" * 80)
    total_features = sum(m['feature_count'] for m in metadata.values())
    layers_with_data = sum(1 for m in metadata.values() if m['feature_count'] > 0)
    total_time = sum(m['query_time'] for m in metadata.values())

    logger.info(f"Total layers queried: {len(metadata)}")
    logger.info(f"Layers with intersections: {layers_with_data}")
    logger.info(f"Total features found: {total_features}")
    logger.info(f"Total query time: {total_time:.2f} seconds")

    # Aggregate clipping statistics
    clip_summary = {
        'enabled': clip_enabled,
        'clip_buffer_miles': clip_buffer_miles
    }

    if clip_enabled and clip_boundary is not None:
        clip_stats = aggregate_clip_metadata(list(metadata.values()))
        clip_summary.update(clip_stats)

        if clip_stats['total_features_clipped'] > 0 or clip_stats['total_clip_failures'] > 0:
            logger.info("")
            logger.info("Clipping Summary:")
            logger.info(f"  Features clipped: {clip_stats['total_features_clipped']}")
            logger.info(f"    - Lines: {clip_stats['total_lines_clipped']}")
            logger.info(f"    - Polygons: {clip_stats['total_polygons_clipped']}")
            logger.info(
                f"  Vertex reduction: {clip_stats['total_original_vertices']:,} -> "
                f"{clip_stats['total_clipped_vertices']:,} "
                f"({clip_stats['overall_vertex_reduction_percent']}%)"
            )
            if clip_stats['total_clip_failures'] > 0:
                logger.warning(
                    f"  Clip failures: {clip_stats['total_clip_failures']} "
                    f"(original geometry kept)"
                )

    # Add state filter statistics to clip_summary
    clip_summary['state_filter'] = {
        'enabled': state_filter_enabled,
        'buffer_miles': clip_buffer_miles,
        'intersecting_states': sorted(list(intersecting_states)),
        'total_layers': len(config['layers']),
        'layers_after_filter': len(layers_to_process),
        'layers_skipped': skipped_count
    }

    logger.info("")

    return results, metadata, clip_summary, clip_boundary
