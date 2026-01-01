"""
HTML generation utilities for PEIT Map Creator.

This module provides functions to generate HTML and JavaScript code for map UI elements.
Used by the map builder to create download menus and embed GeoJSON data.

Functions:
    generate_layer_download_sections: Create HTML for layer download menu
    generate_layer_data_mapping: Embed GeoJSON data in JavaScript
"""

import json
import geopandas as gpd
from typing import Dict, Optional


def generate_layer_download_sections(
    layer_results: Dict[str, gpd.GeoDataFrame],
    config: Dict,
    input_filename: str,
    original_geometry_gdf: Optional[gpd.GeoDataFrame] = None
) -> str:
    """
    Generate HTML for individual layer download sections.

    Creates download button groups for each layer (GeoJSON, SHP, KMZ, GPKG formats).
    Only includes layers that have features.

    Parameters:
    -----------
    layer_results : Dict[str, gpd.GeoDataFrame]
        Dictionary of layer results (layer name -> GeoDataFrame)
    config : Dict
        Configuration dictionary with layer definitions
    input_filename : str
        Name of input file for the input polygon section
    original_geometry_gdf : Optional[gpd.GeoDataFrame]
        Original pre-buffer geometry (None if no buffering was applied)

    Returns:
    --------
    str
        HTML string with download sections for all layers

    Example Output:
        <div class="download-section">
            <div class="download-layer-name">RCRA Sites (150)</div>
            <div class="download-format-buttons">
                <button onclick="...">GeoJSON</button>
                <button onclick="...">SHP</button>
                <button onclick="...">KMZ</button>
            </div>
        </div>
    """
    sections_html = ""

    # Add original input geometry section (if buffer was applied)
    if original_geometry_gdf is not None:
        sections_html += f"""
        <div class="download-section">
            <div class="download-layer-name">{input_filename} (Original Input)</div>
            <div class="download-format-buttons">
                <button class="download-format-btn" onclick="downloadLayer('Original Geometry', 'geojson'); event.stopPropagation();">GeoJSON</button>
                <button class="download-format-btn" onclick="downloadLayer('Original Geometry', 'shp'); event.stopPropagation();">SHP</button>
                <button class="download-format-btn" onclick="downloadLayer('Original Geometry', 'kmz'); event.stopPropagation();">KMZ</button>
                <button class="download-format-btn" onclick="downloadLayer('Original Geometry', 'gpkg'); event.stopPropagation();">GPKG</button>
            </div>
        </div>
        """

    # Add input polygon section (buffered polygon or original if no buffering)
    sections_html += f"""
        <div class="download-section">
            <div class="download-layer-name">{input_filename} (Input Area)</div>
            <div class="download-format-buttons">
                <button class="download-format-btn" onclick="downloadLayer('Input Polygon', 'geojson'); event.stopPropagation();">GeoJSON</button>
                <button class="download-format-btn" onclick="downloadLayer('Input Polygon', 'shp'); event.stopPropagation();">SHP</button>
                <button class="download-format-btn" onclick="downloadLayer('Input Polygon', 'kmz'); event.stopPropagation();">KMZ</button>
                <button class="download-format-btn" onclick="downloadLayer('Input Polygon', 'gpkg'); event.stopPropagation();">GPKG</button>
            </div>
        </div>
        """

    # Add sections for each intersected layer
    for layer_config in config['layers']:
        layer_name = layer_config['name']

        # Skip layers without features
        if layer_name not in layer_results or len(layer_results[layer_name]) == 0:
            continue

        feature_count = len(layer_results[layer_name])

        sections_html += f"""
        <div class="download-section">
            <div class="download-layer-name">{layer_name} ({feature_count})</div>
            <div class="download-format-buttons">
                <button class="download-format-btn" onclick="downloadLayer('{layer_name}', 'geojson'); event.stopPropagation();">GeoJSON</button>
                <button class="download-format-btn" onclick="downloadLayer('{layer_name}', 'shp'); event.stopPropagation();">SHP</button>
                <button class="download-format-btn" onclick="downloadLayer('{layer_name}', 'kmz'); event.stopPropagation();">KMZ</button>
                <button class="download-format-btn" onclick="downloadLayer('{layer_name}', 'gpkg'); event.stopPropagation();">GPKG</button>
            </div>
        </div>
        """

    return sections_html


def generate_layer_data_mapping(
    layer_results: Dict[str, gpd.GeoDataFrame],
    polygon_gdf: gpd.GeoDataFrame,
    original_geometry_gdf: Optional[gpd.GeoDataFrame] = None
) -> str:
    """
    Generate JavaScript object with embedded GeoJSON data.

    Converts all GeoDataFrames to GeoJSON and embeds them as a JavaScript object.
    This avoids CORS issues with external file loading in the browser.

    Parameters:
    -----------
    layer_results : Dict[str, gpd.GeoDataFrame]
        Dictionary of layer results (layer name -> GeoDataFrame)
    polygon_gdf : gpd.GeoDataFrame
        Input polygon GeoDataFrame (buffered polygon or original if no buffering)
    original_geometry_gdf : Optional[gpd.GeoDataFrame]
        Original pre-buffer geometry (None if no buffering was applied)

    Returns:
    --------
    str
        JavaScript string defining layerData object

    Example Output:
        "Original Input": {type: "FeatureCollection", features: [...]},
        "Input Polygon": {type: "FeatureCollection", features: [...]},
        "RCRA Sites": {type: "FeatureCollection", features: [...]}
    """
    mappings = []

    # Add original input geometry (if buffer was applied)
    if original_geometry_gdf is not None:
        original_geojson = json.loads(original_geometry_gdf.to_json())
        original_geojson_str = json.dumps(original_geojson, separators=(',', ':'))
        # Escape forward slashes to prevent </script> breaking out of script context
        original_geojson_str = original_geojson_str.replace('</', '<\\/')
        mappings.append(f'"Original Geometry": {original_geojson_str}')

    # Add input polygon (convert GeoDataFrame to GeoJSON dict)
    input_geojson = json.loads(polygon_gdf.to_json())
    input_geojson_str = json.dumps(input_geojson, separators=(',', ':'))
    # Escape forward slashes to prevent </script> breaking out of script context
    input_geojson_str = input_geojson_str.replace('</', '<\\/')
    # Use double quotes to avoid conflicts with apostrophes in layer names
    mappings.append(f'"Input Polygon": {input_geojson_str}')

    # Add each intersected layer
    for layer_name, gdf in layer_results.items():
        layer_geojson = json.loads(gdf.to_json())
        layer_geojson_str = json.dumps(layer_geojson, separators=(',', ':'))
        # Escape forward slashes to prevent </script> breaking out of script context
        layer_geojson_str = layer_geojson_str.replace('</', '<\\/')
        # Escape any double quotes in the layer name and use double quotes
        escaped_name = layer_name.replace('"', '\\"')
        mappings.append(f'"{escaped_name}": {layer_geojson_str}')

    return ",\n        ".join(mappings)
