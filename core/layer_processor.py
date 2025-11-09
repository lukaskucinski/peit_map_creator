"""
Layer processing module for APPEIT Map Creator.

This module handles batch processing of multiple FeatureServer layers.
Queries all configured layers and collects results and metadata.

Functions:
    process_all_layers: Query all configured layers and return results
"""

import geopandas as gpd
from typing import Dict, Tuple
from core.arcgis_query import query_arcgis_layer
from utils.logger import get_logger

logger = get_logger(__name__)


def process_all_layers(
    polygon_gdf: gpd.GeoDataFrame,
    config: Dict
) -> Tuple[Dict[str, gpd.GeoDataFrame], Dict[str, Dict]]:
    """
    Query all configured FeatureServer layers.

    Iterates through all layers defined in the configuration and queries
    each one for features that intersect the input polygon.

    Parameters:
    -----------
    polygon_gdf : gpd.GeoDataFrame
        Input polygon for intersection
    config : Dict
        Configuration dictionary with layer definitions

    Returns:
    --------
    Tuple[Dict[str, gpd.GeoDataFrame], Dict[str, Dict]]
        - Dictionary of layer results (layer name -> GeoDataFrame)
        - Dictionary of metadata (layer name -> metadata dict)

    Example:
        >>> results, metadata = process_all_layers(polygon_gdf, config)
        >>> len(results)  # Number of layers with features
        3
        >>> metadata['RCRA Sites']['feature_count']
        152
    """
    logger.info("=" * 80)
    logger.info("Querying ArcGIS FeatureServers")
    logger.info("=" * 80)

    results = {}
    metadata = {}

    for layer_config in config['layers']:
        layer_name = layer_config['name']

        gdf, meta = query_arcgis_layer(
            layer_url=layer_config['url'],
            layer_id=layer_config['layer_id'],
            polygon_geom=polygon_gdf,
            layer_name=layer_name
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
    logger.info("")

    return results, metadata
