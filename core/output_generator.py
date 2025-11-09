"""
Output generation module for APPEIT Map Creator.

This module handles saving the generated map and data files to the output directory.
Creates a timestamped directory structure with HTML map, GeoJSON data files, and metadata.

Functions:
    generate_output: Save map, data files, and metadata to output directory
"""

import folium
import geopandas as gpd
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from config.config_loader import OUTPUT_DIR
from utils.logger import get_logger

logger = get_logger(__name__)


def generate_output(
    map_obj: folium.Map,
    polygon_gdf: gpd.GeoDataFrame,
    layer_results: Dict[str, gpd.GeoDataFrame],
    metadata: Dict[str, Dict],
    output_name: Optional[str] = None
) -> Path:
    """
    Generate output directory with HTML map and GeoJSON data files.

    Creates a timestamped output directory containing:
    - index.html: Interactive Leaflet map
    - metadata.json: Summary statistics and query information
    - data/: GeoJSON files for input polygon and all layers

    Parameters:
    -----------
    map_obj : folium.Map
        Folium map object to save
    polygon_gdf : gpd.GeoDataFrame
        Input polygon
    layer_results : Dict[str, gpd.GeoDataFrame]
        Dictionary of layer results (layer name -> GeoDataFrame)
    metadata : Dict[str, Dict]
        Layer metadata
    output_name : Optional[str]
        Custom output directory name (defaults to timestamped name)

    Returns:
    --------
    Path
        Path to output directory

    Example:
        >>> output_path = generate_output(map_obj, polygon_gdf, results, metadata)
        >>> output_path
        Path('outputs/appeit_map_20250108_143022')
    """
    logger.info("=" * 80)
    logger.info("Generating Output Files")
    logger.info("=" * 80)

    # Create timestamped output directory
    if output_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"appeit_map_{timestamp}"

    output_path = OUTPUT_DIR / output_name
    output_path.mkdir(exist_ok=True)

    # Create data subdirectory
    data_path = output_path / 'data'
    data_path.mkdir(exist_ok=True)

    logger.info(f"Output directory: {output_path}")

    # Save input polygon
    logger.info("  - Saving input polygon...")
    polygon_file = data_path / 'input_polygon.geojson'
    polygon_gdf.to_file(polygon_file, driver='GeoJSON')

    # Save each layer's features
    for layer_name, gdf in layer_results.items():
        logger.info(f"  - Saving {layer_name} features...")
        # Sanitize filename
        safe_name = layer_name.replace(' ', '_').replace('/', '_').lower()
        layer_file = data_path / f'{safe_name}.geojson'
        gdf.to_file(layer_file, driver='GeoJSON')

    # Save map HTML
    logger.info("  - Saving interactive map...")
    map_file = output_path / 'index.html'
    map_obj.save(str(map_file))

    # Save metadata JSON
    logger.info("  - Saving metadata...")
    metadata_file = output_path / 'metadata.json'

    summary = {
        'generated_at': datetime.now().isoformat(),
        'input_polygon': {
            'bounds': polygon_gdf.total_bounds.tolist(),
            'crs': str(polygon_gdf.crs)
        },
        'layers': metadata,
        'total_features': sum(m['feature_count'] for m in metadata.values()),
        'layers_with_data': sum(1 for m in metadata.values() if m['feature_count'] > 0)
    }

    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    logger.info("")
    logger.info("=" * 80)
    logger.info("✓ Output Generation Complete")
    logger.info("=" * 80)
    logger.info(f"Files saved to: {output_path}")
    logger.info("  - index.html (interactive map)")
    logger.info("  - metadata.json (summary statistics)")
    logger.info(f"  - data/ ({len(layer_results) + 1} GeoJSON files)")
    logger.info("")
    logger.info(f"To view the map, open: {map_file}")
    logger.info("=" * 80)

    return output_path
