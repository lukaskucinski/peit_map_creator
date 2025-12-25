"""
Layer processing module for PEIT Map Creator.

This module handles batch processing of multiple FeatureServer layers.
Queries all configured layers and collects results and metadata.

Functions:
    process_all_layers: Query all configured layers and return results
"""

import json
import geopandas as gpd
from typing import Dict, List, Optional, Set, Tuple
from pyproj import CRS
from shapely.geometry.base import BaseGeometry
from core.arcgis_query import query_arcgis_layer
from geometry_input.clipping import create_clip_boundary, aggregate_clip_metadata
from config.config_loader import load_geometry_settings
from utils.logger import get_logger
from utils.state_filter import get_intersecting_states, filter_layers_by_state
from utils.geometry_converters import (
    shapely_to_esri_polygon,
    count_geometry_vertices,
    simplify_for_query,
    calculate_bbox_fill_ratio,
    calculate_area_sq_miles,
    calculate_dynamic_bbox_threshold
)

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

    # Polygon query settings - use actual polygon geometry instead of bounding box
    polygon_query_config = geometry_settings.get('polygon_query_enabled', True)
    max_query_vertices = geometry_settings.get('polygon_query_max_vertices', 1000)
    simplify_tolerance = geometry_settings.get('polygon_query_simplify_tolerance', 0.0001)

    # Pagination settings - automatically fetch all features when server limit exceeded
    pagination_enabled = geometry_settings.get('pagination_enabled', True)
    pagination_max_iterations = geometry_settings.get('pagination_max_iterations', 10)
    pagination_total_timeout = geometry_settings.get('pagination_total_timeout', 300.0)

    if pagination_enabled:
        logger.info(f"Pagination enabled: max {pagination_max_iterations} pages, "
                    f"{pagination_total_timeout}s timeout")

    # Pre-compute ESRI polygon JSON ONCE for all layer queries (optimization)
    esri_polygon_json = None
    polygon_query_metadata = {}
    use_polygon_query = False  # Will be set based on heuristic

    if polygon_query_config:
        polygon_geometry = polygon_gdf.geometry.iloc[0]

        # Calculate area and dynamic threshold
        # Larger areas need stricter thresholds (prefer polygon query to avoid hitting limits)
        area_sq_miles = calculate_area_sq_miles(polygon_geometry)
        bbox_fill_ratio = calculate_bbox_fill_ratio(polygon_geometry)
        bbox_fill_threshold = calculate_dynamic_bbox_threshold(area_sq_miles)

        # Track in metadata
        polygon_query_metadata['area_sq_miles'] = round(area_sq_miles, 1)
        polygon_query_metadata['bbox_fill_ratio'] = round(bbox_fill_ratio, 3)
        polygon_query_metadata['dynamic_threshold'] = round(bbox_fill_threshold, 2)

        if bbox_fill_ratio >= bbox_fill_threshold:
            # Polygon fills most of its bounding box - envelope query is more efficient
            logger.info(
                f"Polygon query: disabled (bbox fill {bbox_fill_ratio:.1%} >= "
                f"{bbox_fill_threshold:.0%} threshold for {area_sq_miles:.0f} sq mi)"
            )
            logger.info("  Using envelope queries (more efficient for compact geometries)")
        else:
            # Polygon is sparse/discontiguous - polygon query is more efficient
            use_polygon_query = True
            original_vertices = count_geometry_vertices(polygon_geometry)

            # Simplify geometry if needed (done once, not per-layer)
            simplified_geom = simplify_for_query(
                polygon_geometry,
                max_vertices=max_query_vertices,
                tolerance=simplify_tolerance
            )
            query_vertices = count_geometry_vertices(simplified_geom)

            # Track simplification metadata
            polygon_query_metadata['query_vertices'] = query_vertices
            polygon_query_metadata['simplification_applied'] = query_vertices < original_vertices
            if polygon_query_metadata['simplification_applied']:
                polygon_query_metadata['original_vertices'] = original_vertices
                logger.info(
                    f"Polygon query: enabled (bbox fill {bbox_fill_ratio:.1%} < "
                    f"{bbox_fill_threshold:.0%} threshold for {area_sq_miles:.0f} sq mi)"
                )
                logger.info(
                    f"  Simplified from {original_vertices} to {query_vertices} vertices"
                )
            else:
                logger.info(
                    f"Polygon query: enabled ({query_vertices} vertices, "
                    f"bbox fill {bbox_fill_ratio:.1%}, {area_sq_miles:.0f} sq mi)"
                )

            # Convert to ESRI JSON once
            esri_polygon = shapely_to_esri_polygon(simplified_geom)
            if esri_polygon:
                esri_polygon_json = json.dumps(esri_polygon)
            else:
                logger.warning("Could not convert geometry to ESRI format, using envelope queries")
                use_polygon_query = False
    else:
        logger.info("Polygon query disabled in config (using envelope queries)")

    results = {}
    metadata = {}

    for layer_config in layers_to_process:
        layer_name = layer_config['name']

        # Skip disabled layers
        if not layer_config.get('enabled', True):
            logger.info(f"Skipping {layer_name} (disabled)")
            continue

        geometry_type = layer_config.get('geometry_type', None)

        gdf, meta = query_arcgis_layer(
            layer_url=layer_config['url'],
            layer_id=layer_config['layer_id'],
            polygon_geom=polygon_gdf,
            layer_name=layer_name,
            clip_boundary=clip_boundary,
            geometry_type=geometry_type,
            use_polygon_query=use_polygon_query,
            esri_polygon_json=esri_polygon_json,
            polygon_query_metadata=polygon_query_metadata,
            pagination_enabled=pagination_enabled,
            pagination_max_iterations=pagination_max_iterations,
            pagination_total_timeout=pagination_total_timeout
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

    # Count query methods used
    polygon_queries = sum(
        1 for m in metadata.values() if m.get('query_method') == 'polygon'
    )
    envelope_queries = sum(
        1 for m in metadata.values() if m.get('query_method') == 'envelope'
    )
    fallback_queries = sum(
        1 for m in metadata.values() if m.get('query_method') == 'envelope_fallback'
    )

    logger.info(f"Total layers queried: {len(metadata)}")
    logger.info(f"Layers with intersections: {layers_with_data}")
    logger.info(f"Total features found: {total_features}")
    logger.info(f"Total query time: {total_time:.2f} seconds")

    # Log query method summary
    if use_polygon_query:
        logger.info(
            f"Query methods: {polygon_queries} polygon, "
            f"{envelope_queries} envelope, {fallback_queries} fallback"
        )

    # Log pagination summary
    layers_with_pagination = sum(
        1 for m in metadata.values()
        if m.get('pagination', {}).get('used', False)
    )
    layers_incomplete = sum(
        1 for m in metadata.values()
        if m.get('results_incomplete', False)
    )

    if layers_with_pagination > 0:
        total_pages = sum(
            m.get('pagination', {}).get('pages_fetched', 0)
            for m in metadata.values()
        )
        logger.info(f"Pagination used: {layers_with_pagination} layers, {total_pages} total pages")

    if layers_incomplete > 0:
        incomplete_layers = [
            m['layer_name'] for m in metadata.values()
            if m.get('results_incomplete', False)
        ]
        logger.warning(
            f"⚠ INCOMPLETE RESULTS: {layers_incomplete} layer(s) may have missing features"
        )
        for layer_name in incomplete_layers:
            layer_meta = metadata.get(layer_name, {})
            reason = layer_meta.get('incomplete_reason', 'unknown')
            logger.warning(f"  - {layer_name}: {reason}")

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
