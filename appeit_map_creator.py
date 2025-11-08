# %%
"""
APPEIT Map Creator
==================
A Python tool to replicate NTIA's APPEIT functionality by querying ArcGIS FeatureServers
and generating interactive Leaflet web maps showing environmental layer intersections.

Author: Created with Claude Code
Repository: https://github.com/lukaskucinski/appeit_map_creator.git
"""

# %%
# Cell 1: Imports and Configuration Setup

import geopandas as gpd
import folium
from folium import plugins
from folium.plugins import Geocoder
import requests
import json
from pathlib import Path
from datetime import datetime
import warnings
from shapely.geometry import mapping, shape
from shapely.ops import unary_union
import time
from typing import Dict, List, Tuple, Optional
import sys

warnings.filterwarnings('ignore')

# Project paths
PROJECT_ROOT = Path(__file__).parent
CONFIG_DIR = PROJECT_ROOT / 'config'
OUTPUT_DIR = PROJECT_ROOT / 'outputs'
TEMP_DIR = PROJECT_ROOT / 'temp'

# Ensure directories exist
OUTPUT_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

# Load configuration
def load_config() -> Dict:
    """Load layer configuration from JSON file."""
    config_path = CONFIG_DIR / 'layers_config.json'
    with open(config_path, 'r') as f:
        return json.load(f)

CONFIG = load_config()

print("=" * 80)
print("APPEIT Map Creator - Environmental Layer Intersection Tool")
print("=" * 80)
print(f"Configuration loaded: {len(CONFIG['layers'])} layers defined")
print(f"Output directory: {OUTPUT_DIR}")
print("✓ Cell 1 completed: Imports and configuration loaded successfully")
print()


# %%
# Cell 2: Input Polygon Reader Function

def read_input_polygon(file_path: str) -> gpd.GeoDataFrame:
    """
    Read input polygon from various geospatial formats and prepare for analysis.

    Parameters:
    -----------
    file_path : str
        Path to the input file (supports: .shp, .kml, .kmz, .gpkg, .geojson, .gdb)

    Returns:
    --------
    gpd.GeoDataFrame
        GeoDataFrame with single polygon in EPSG:4326 (WGS84)
    """
    print(f"Reading input polygon from: {file_path}")

    # Read the file
    gdf = gpd.read_file(file_path)

    print(f"  - Original CRS: {gdf.crs}")
    print(f"  - Number of features: {len(gdf)}")
    print(f"  - Geometry types: {gdf.geometry.type.unique()}")

    # Warn if multiple features
    if len(gdf) > 1:
        print(f"  WARNING: File contains {len(gdf)} features. Using union of all geometries.")
        # Dissolve all features into one
        gdf = gpd.GeoDataFrame(
            geometry=[unary_union(gdf.geometry)],
            crs=gdf.crs
        )

    # Reproject to WGS84 if needed
    if gdf.crs != 'EPSG:4326':
        print(f"  - Reprojecting to EPSG:4326...")
        gdf = gdf.to_crs('EPSG:4326')

    # Get bounds for reporting
    bounds = gdf.total_bounds
    print(f"  - Bounding box: ({bounds[0]:.6f}, {bounds[1]:.6f}) to ({bounds[2]:.6f}, {bounds[3]:.6f})")
    print(f"   Polygon loaded successfully\n")

    return gdf

print("✓ Cell 2 completed: Input polygon reader function defined")
print()


# %%
# Cell 3: ArcGIS FeatureServer Query Function

def query_arcgis_layer(
    layer_url: str,
    layer_id: int,
    polygon_geom: gpd.GeoDataFrame,
    layer_name: str = "Layer"
) -> Tuple[Optional[gpd.GeoDataFrame], Dict]:
    """
    Query an ArcGIS FeatureServer with spatial intersection.

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

    Returns:
    --------
    Tuple[Optional[gpd.GeoDataFrame], Dict]
        GeoDataFrame of intersecting features and metadata dictionary
    """
    print(f"  Querying {layer_name}...")

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
        response = requests.post(query_url, data=params, timeout=60)
        response.raise_for_status()

        # Parse response
        result = response.json()

        # Check for features
        if 'features' in result and len(result['features']) > 0:
            # Convert ESRI JSON to GeoDataFrame
            features = []
            for feature in result['features']:
                geom = feature.get('geometry')
                props = feature.get('attributes', {})

                # Convert ESRI geometry to GeoJSON format
                if geom and 'x' in geom and 'y' in geom:
                    # Point geometry
                    geojson_feat = {
                        'type': 'Feature',
                        'geometry': {'type': 'Point', 'coordinates': [geom['x'], geom['y']]},
                        'properties': props
                    }
                elif geom and 'paths' in geom:
                    # LineString geometry
                    coords = geom['paths'][0] if len(geom['paths']) == 1 else geom['paths']
                    geom_type = 'LineString' if len(geom['paths']) == 1 else 'MultiLineString'
                    geojson_feat = {
                        'type': 'Feature',
                        'geometry': {'type': geom_type, 'coordinates': coords},
                        'properties': props
                    }
                elif geom and 'rings' in geom:
                    # Polygon geometry
                    geojson_feat = {
                        'type': 'Feature',
                        'geometry': {'type': 'Polygon', 'coordinates': geom['rings']},
                        'properties': props
                    }
                else:
                    continue

                features.append(geojson_feat)

            # Convert to GeoDataFrame
            gdf = gpd.GeoDataFrame.from_features(features, crs='EPSG:4326')
            initial_count = len(gdf)

            print(f"    - Bounding box returned {initial_count} features")

            # Client-side filtering: precise polygon intersection
            # This filters out features that are in the bbox but not in the actual polygon
            polygon_geometry = polygon_geom.geometry.iloc[0]
            gdf = gdf[gdf.intersects(polygon_geometry)]

            metadata['feature_count'] = len(gdf)
            metadata['bbox_count'] = initial_count
            metadata['filtered_count'] = initial_count - len(gdf)

            # Check if result exceeded limit
            if result.get('exceededTransferLimit', False):
                metadata['warning'] = f"Result exceeded server limit. Showing first {len(gdf)} features."
                print(f"    ⚠ WARNING: {metadata['warning']}")

            if initial_count != len(gdf):
                print(f"    - Filtered to {len(gdf)} features (removed {initial_count - len(gdf)} outside polygon)")

            print(f"     Found {len(gdf)} intersecting features")

            metadata['query_time'] = time.time() - start_time
            return gdf, metadata
        else:
            print(f"    - No intersecting features found")
            metadata['query_time'] = time.time() - start_time
            return None, metadata

    except requests.exceptions.RequestException as e:
        error_msg = f"Request failed: {str(e)}"
        print(f"     ERROR: {error_msg}")
        metadata['error'] = error_msg
        metadata['query_time'] = time.time() - start_time
        return None, metadata

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"     ERROR: {error_msg}")
        metadata['error'] = error_msg
        metadata['query_time'] = time.time() - start_time
        return None, metadata

print("✓ Cell 3 completed: ArcGIS FeatureServer query function defined")
print()


# %%
# Cell 4: Process All Layers Function

def process_all_layers(
    polygon_gdf: gpd.GeoDataFrame,
    config: Dict
) -> Tuple[Dict[str, gpd.GeoDataFrame], Dict[str, Dict]]:
    """
    Query all configured FeatureServer layers.

    Parameters:
    -----------
    polygon_gdf : gpd.GeoDataFrame
        Input polygon for intersection
    config : Dict
        Configuration dictionary with layer definitions

    Returns:
    --------
    Tuple[Dict, Dict]
        Dictionary of layer results and metadata
    """
    print("=" * 80)
    print("Querying ArcGIS FeatureServers")
    print("=" * 80)

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
        print()

    # Summary
    print("=" * 80)
    print("Query Summary")
    print("=" * 80)
    total_features = sum(m['feature_count'] for m in metadata.values())
    layers_with_data = sum(1 for m in metadata.values() if m['feature_count'] > 0)
    total_time = sum(m['query_time'] for m in metadata.values())

    print(f"Total layers queried: {len(metadata)}")
    print(f"Layers with intersections: {layers_with_data}")
    print(f"Total features found: {total_features}")
    print(f"Total query time: {total_time:.2f} seconds")
    print()

    return results, metadata

print("✓ Cell 4 completed: Process all layers function defined")
print()


# %%
# Cell 5: Create Leaflet Map with Folium

def generate_layer_download_sections(layer_results: Dict[str, gpd.GeoDataFrame], config: Dict, input_filename: str) -> str:
    """
    Generate HTML for individual layer download sections.

    Parameters:
    -----------
    layer_results : Dict[str, gpd.GeoDataFrame]
        Dictionary of layer results
    config : Dict
        Configuration dictionary
    input_filename : str
        Name of input file for the input polygon section

    Returns:
    --------
    str
        HTML string for layer download sections
    """
    sections_html = ""

    # Add input polygon section first
    sections_html += f"""
        <div class="download-section">
            <div class="download-layer-name">{input_filename} (Input Area)</div>
            <div class="download-format-buttons">
                <button class="download-format-btn" onclick="downloadLayer('Input Polygon', 'geojson')">GeoJSON</button>
                <button class="download-format-btn" onclick="downloadLayer('Input Polygon', 'shp')">SHP</button>
                <button class="download-format-btn" onclick="downloadLayer('Input Polygon', 'kmz')">KMZ</button>
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
                <button class="download-format-btn" onclick="downloadLayer('{layer_name}', 'geojson')">GeoJSON</button>
                <button class="download-format-btn" onclick="downloadLayer('{layer_name}', 'shp')">SHP</button>
                <button class="download-format-btn" onclick="downloadLayer('{layer_name}', 'kmz')">KMZ</button>
            </div>
        </div>
        """

    return sections_html


def generate_layer_data_mapping(
    layer_results: Dict[str, gpd.GeoDataFrame],
    polygon_gdf: gpd.GeoDataFrame
) -> str:
    """
    Generate JavaScript object with embedded GeoJSON data.

    Parameters:
    -----------
    layer_results : Dict[str, gpd.GeoDataFrame]
        Dictionary of layer results
    polygon_gdf : gpd.GeoDataFrame
        Input polygon GeoDataFrame

    Returns:
    --------
    str
        JavaScript string with embedded GeoJSON objects
    """
    mappings = []

    # Add input polygon (convert GeoDataFrame to GeoJSON dict)
    input_geojson = json.loads(polygon_gdf.to_json())
    input_geojson_str = json.dumps(input_geojson, separators=(',', ':'))
    mappings.append(f"'Input Polygon': {input_geojson_str}")

    # Add each intersected layer
    for layer_name, gdf in layer_results.items():
        layer_geojson = json.loads(gdf.to_json())
        layer_geojson_str = json.dumps(layer_geojson, separators=(',', ':'))
        mappings.append(f"'{layer_name}': {layer_geojson_str}")

    return ",\n        ".join(mappings)


def format_popup_value(col: str, value) -> str:
    """
    Format popup values, converting URLs to clickable hyperlinks.

    Parameters:
    -----------
    col : str
        Column name
    value : any
        Value to format

    Returns:
    --------
    str
        Formatted HTML string
    """
    if value is None or (isinstance(value, float) and value != value):  # Check for NaN
        return 'None'

    value_str = str(value)

    # Check if this is a URL field (by column name or value content)
    if 'url' in col.lower() or value_str.startswith(('http://', 'https://')):
        # Truncate long URLs for display
        display_text = value_str if len(value_str) <= 60 else f"{value_str[:57]}..."
        return f'<a href="{value_str}" target="_blank" style="word-break: break-all; color: #0066cc;">{display_text}</a>'

    return value_str

def create_web_map(
    polygon_gdf: gpd.GeoDataFrame,
    layer_results: Dict[str, gpd.GeoDataFrame],
    metadata: Dict[str, Dict],
    config: Dict,
    input_filename: Optional[str] = None
) -> folium.Map:
    """
    Create an interactive Leaflet map with all layers.

    Parameters:
    -----------
    polygon_gdf : gpd.GeoDataFrame
        Input polygon to display
    layer_results : Dict[str, gpd.GeoDataFrame]
        Dictionary of layer results
    metadata : Dict[str, Dict]
        Layer metadata
    config : Dict
        Configuration dictionary
    input_filename : Optional[str]
        Name of input file (without extension) for layer naming

    Returns:
    --------
    folium.Map
        Folium map object
    """
    print("=" * 80)
    print("Creating Interactive Web Map")
    print("=" * 80)

    # Calculate map center from polygon bounds
    bounds = polygon_gdf.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2

    # Initialize map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=config['settings']['default_zoom'],
        tiles='OpenStreetMap'
    )

    # Add additional tile layers
    folium.TileLayer('CartoDB positron', name='CartoDB Positron').add_to(m)
    folium.TileLayer('CartoDB dark_matter', name='CartoDB Dark Matter').add_to(m)
    folium.TileLayer('Esri WorldImagery', name='Esri Satellite').add_to(m)

    # Add input polygon
    print("  - Adding input polygon...")
    layer_name = input_filename if input_filename else 'Input Area'
    folium.GeoJson(
        polygon_gdf,
        name=layer_name,
        style_function=lambda x: {
            'fillColor': '#FFD700',
            'color': '#FF8C00',
            'weight': 3,
            'fillOpacity': 0.2
        },
        tooltip=layer_name
    ).add_to(m)

    # Add each layer with appropriate styling
    for layer_config in config['layers']:
        layer_name = layer_config['name']

        if layer_name not in layer_results:
            print(f"  - Skipping {layer_name} (no features)")
            continue

        gdf = layer_results[layer_name]

        # Skip if no features
        if len(gdf) == 0:
            print(f"  - Skipping {layer_name} (0 features)")
            continue

        print(f"  - Adding {layer_name} ({len(gdf)} features)...")

        # Check if clustering should be used
        use_clustering = (
            config['settings']['enable_clustering'] and
            layer_config['geometry_type'] == 'point' and
            len(gdf) >= config['settings']['cluster_threshold']
        )

        if use_clustering:
            print(f"    (Using marker clustering)")
            marker_cluster = plugins.MarkerCluster(name=layer_name)

            for _, row in gdf.iterrows():
                # Create popup with all attributes
                popup_html = f"<b>{layer_name}</b><br>"
                popup_html += "<hr>"
                for col in gdf.columns:
                    if col != 'geometry':
                        popup_html += f"<b>{col}:</b> {format_popup_value(col, row[col])}<br>"

                # Add marker to cluster
                folium.Marker(
                    location=[row.geometry.y, row.geometry.x],
                    popup=folium.Popup(popup_html, max_width=400),
                    icon=folium.Icon(
                        color=layer_config['icon_color'],
                        icon=layer_config['icon'],
                        prefix='fa'
                    )
                ).add_to(marker_cluster)

            marker_cluster.add_to(m)
            print(f"    ✓ Added {len(gdf)} clustered markers to map")

        else:
            # Add as GeoJSON layer
            if layer_config['geometry_type'] == 'point':
                # Use markers for points
                feature_group = folium.FeatureGroup(name=layer_name)

                for _, row in gdf.iterrows():
                    popup_html = f"<b>{layer_name}</b><br>"
                    popup_html += "<hr>"
                    for col in gdf.columns:
                        if col != 'geometry':
                            popup_html += f"<b>{col}:</b> {format_popup_value(col, row[col])}<br>"

                    folium.Marker(
                        location=[row.geometry.y, row.geometry.x],
                        popup=folium.Popup(popup_html, max_width=400),
                        icon=folium.Icon(
                            color=layer_config['icon_color'],
                            icon=layer_config['icon'],
                            prefix='fa'
                        )
                    ).add_to(feature_group)

                feature_group.add_to(m)
                print(f"    ✓ Added {len(gdf)} point markers to map")

            else:
                # Use GeoJSON for lines/polygons
                def style_function(feature):
                    return {
                        'color': layer_config['color'],
                        'weight': 3,
                        'opacity': 0.8
                    }

                def highlight_function(feature):
                    return {
                        'color': layer_config['color'],
                        'weight': 5,
                        'opacity': 1.0
                    }

                folium.GeoJson(
                    gdf,
                    name=layer_name,
                    style_function=style_function,
                    highlight_function=highlight_function,
                    tooltip=folium.GeoJsonTooltip(
                        fields=list(gdf.columns.drop('geometry')),
                        aliases=list(gdf.columns.drop('geometry')),
                        localize=True
                    )
                ).add_to(m)
                print(f"    ✓ Added {len(gdf)} features as GeoJSON layer")

    # Add layer control
    folium.LayerControl(position='topright', collapsed=False).add_to(m)

    # Add geocoding search control (address and coordinate search)
    geocoder_config = config.get('settings', {}).get('geocoder', {})
    if geocoder_config.get('enabled', True):
        Geocoder(
            collapsed=geocoder_config.get('collapsed', True),
            position=geocoder_config.get('position', 'topright'),
            add_marker=True,
            zoom=geocoder_config.get('search_zoom', 15),
            provider='nominatim',
            placeholder='Search address or coordinates...'
        ).add_to(m)

    # Add scale bar
    plugins.MeasureControl(position='bottomleft', primary_length_unit='miles').add_to(m)

    # Add fullscreen button
    plugins.Fullscreen(position='topleft').add_to(m)

    # Add mouse position
    plugins.MousePosition().add_to(m)

    # Add CDN libraries for download functionality
    from folium import Element

    libraries_html = """
    <script src="https://unpkg.com/shp-write@latest/shpwrite.js"></script>
    <script src="https://unpkg.com/tokml@0.4.0/tokml.js"></script>
    <script src="https://unpkg.com/jszip@3.10.1/dist/jszip.min.js"></script>
    <script src="https://unpkg.com/file-saver@2.0.5/dist/FileSaver.min.js"></script>
    """
    m.get_root().html.add_child(Element(libraries_html))

    # Add download control button
    download_control_html = f"""
    <style>
        /* Download control container */
        .leaflet-control-download {{
            position: fixed;
            bottom: 50px;
            right: 10px;
            z-index: 1000;
        }}

        /* Main download button - matches Leaflet control style */
        .download-button {{
            background: white;
            border: 2px solid rgba(0,0,0,0.2);
            border-radius: 4px;
            box-shadow: 0 1px 5px rgba(0,0,0,0.4);
            width: 36px;
            height: 36px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            color: #333;
            transition: background 0.2s;
        }}

        .download-button:hover {{
            background: #f4f4f4;
        }}

        /* Expanded menu panel */
        .download-menu {{
            position: absolute;
            bottom: 0;
            right: 0;
            background: white;
            border: 2px solid rgba(0,0,0,0.2);
            border-radius: 4px;
            box-shadow: 0 1px 5px rgba(0,0,0,0.65);
            padding: 12px;
            min-width: 240px;
            display: none;
            max-height: 500px;
            overflow-y: auto;
        }}

        .download-menu.active {{
            display: block;
        }}

        .download-menu-header {{
            font-weight: bold;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 2px solid #ddd;
            font-size: 14px;
            color: #333;
        }}

        .download-section {{
            margin-bottom: 14px;
        }}

        .download-layer-name {{
            font-weight: 600;
            font-size: 12px;
            color: #555;
            margin-bottom: 6px;
        }}

        .download-format-buttons {{
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
        }}

        .download-format-btn {{
            background: #0078A8;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 11px;
            font-weight: 500;
            transition: background 0.2s;
        }}

        .download-format-btn:hover {{
            background: #005a80;
        }}

        .download-format-btn:active {{
            background: #004060;
        }}

        .download-all-section {{
            background: #f0f8ff;
            padding: 10px;
            border-radius: 4px;
            margin-bottom: 14px;
            border: 1px solid #d0e8ff;
        }}

        .download-all-section .download-layer-name {{
            color: #0078A8;
            font-size: 13px;
        }}
    </style>

    <div class="leaflet-control-download">
        <div class="download-button" onclick="toggleDownloadMenu()" title="Download Layers">
            <i class="fa fa-download"></i>
        </div>

        <div class="download-menu" id="download-menu">
            <div class="download-menu-header">
                <i class="fa fa-download"></i> Download Layers
            </div>

            <!-- Download All Section -->
            <div class="download-all-section">
                <div class="download-layer-name">All Layers</div>
                <div class="download-format-buttons">
                    <button class="download-format-btn" onclick="downloadAll('geojson')">GeoJSON</button>
                    <button class="download-format-btn" onclick="downloadAll('shp')">Shapefile</button>
                    <button class="download-format-btn" onclick="downloadAll('kmz')">KMZ</button>
                </div>
            </div>

            <!-- Individual Layer Sections -->
            {generate_layer_download_sections(layer_results, config, input_filename)}
        </div>
    </div>

    <script>
        // Layer data embedded in page (GeoJSON objects)
        const layerData = {{
            {generate_layer_data_mapping(layer_results, polygon_gdf)}
        }};

        function toggleDownloadMenu() {{
            const menu = document.getElementById('download-menu');
            menu.classList.toggle('active');
        }}

        // Close menu when clicking outside
        document.addEventListener('click', function(event) {{
            const control = document.querySelector('.leaflet-control-download');
            const menu = document.getElementById('download-menu');
            if (!control.contains(event.target) && menu.classList.contains('active')) {{
                menu.classList.remove('active');
            }}
        }});

        // Get GeoJSON from embedded data (no fetch needed - fixes CORS issue)
        async function loadGeoJSON(layerName) {{
            return layerData[layerName];
        }}

        // Download individual layer in specified format
        async function downloadLayer(layerName, format) {{
            const geojson = await loadGeoJSON(layerName);
            const fileName = layerName.replace(/\\s+/g, '_').replace(/[^a-zA-Z0-9_]/g, '').toLowerCase();

            switch(format) {{
                case 'geojson':
                    downloadGeoJSON(geojson, fileName);
                    break;
                case 'shp':
                    downloadShapefile(geojson, fileName);
                    break;
                case 'kmz':
                    downloadKMZ(geojson, fileName);
                    break;
            }}
        }}

        // Download all layers as a single ZIP file
        async function downloadAll(format) {{
            const zip = new JSZip();

            for (const layerName of Object.keys(layerData)) {{
                const geojson = await loadGeoJSON(layerName);
                const fileName = layerName.replace(/\\s+/g, '_').replace(/[^a-zA-Z0-9_]/g, '').toLowerCase();

                switch(format) {{
                    case 'geojson':
                        zip.file(fileName + '.geojson', JSON.stringify(geojson, null, 2));
                        break;
                    case 'shp':
                        // Add shapefile as nested zip
                        const shpData = shpwrite.zip(geojson);
                        const shpBlob = await fetch('data:application/zip;base64,' + shpData).then(r => r.blob());
                        zip.file(fileName + '_shapefile.zip', shpBlob);
                        break;
                    case 'kmz':
                        const kml = tokml(geojson);
                        const kmzBlob = await createKMZBlob(kml);
                        zip.file(fileName + '.kmz', kmzBlob);
                        break;
                }}
            }}

            // Generate and download ZIP
            const content = await zip.generateAsync({{type: 'blob'}});
            saveAs(content, 'all_layers_' + format + '.zip');
        }}

        // Format-specific download functions
        function downloadGeoJSON(geojson, fileName) {{
            const blob = new Blob([JSON.stringify(geojson, null, 2)], {{type: 'application/json'}});
            saveAs(blob, fileName + '.geojson');
        }}

        function downloadShapefile(geojson, fileName) {{
            // shp-write returns a base64 encoded zip file containing .shp, .shx, .dbf, .prj
            const shpData = shpwrite.zip(geojson);
            const byteCharacters = atob(shpData);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {{
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }}
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], {{type: 'application/zip'}});
            saveAs(blob, fileName + '_shapefile.zip');
        }}

        async function downloadKMZ(geojson, fileName) {{
            const kml = tokml(geojson);
            const kmzBlob = await createKMZBlob(kml);
            saveAs(kmzBlob, fileName + '.kmz');
        }}

        async function createKMZBlob(kml) {{
            const zip = new JSZip();
            zip.file('doc.kml', kml);
            return await zip.generateAsync({{type: 'blob'}});
        }}
    </script>
    """
    m.get_root().html.add_child(Element(download_control_html))

    # Add collapsible side panel with About section and dynamic legend

    # Generate legend HTML for layers with features
    legend_items_html = ""
    for layer_config in config['layers']:
        layer_name = layer_config['name']

        # Skip layers without features
        if layer_name not in layer_results or len(layer_results[layer_name]) == 0:
            continue

        feature_count = len(layer_results[layer_name])
        geometry_type = layer_config['geometry_type']

        # Create legend item based on geometry type
        if geometry_type == 'point':
            # Point layer: show icon
            icon = layer_config['icon']
            icon_color = layer_config['icon_color']
            legend_items_html += f"""
            <div class="legend-item" data-layer-name="{layer_name}">
                <i class="fa fa-{icon}" style="color: {icon_color}; margin-right: 8px;"></i>
                <span>{layer_name} ({feature_count})</span>
            </div>
            """
        elif geometry_type == 'line':
            # Line layer: show line sample
            color = layer_config['color']
            legend_items_html += f"""
            <div class="legend-item" data-layer-name="{layer_name}">
                <svg width="30" height="15" style="margin-right: 8px; vertical-align: middle;">
                    <line x1="0" y1="7" x2="30" y2="7" style="stroke:{color}; stroke-width:3;" />
                </svg>
                <span>{layer_name} ({feature_count})</span>
            </div>
            """
        elif geometry_type == 'polygon':
            # Polygon layer: show filled rectangle
            color = layer_config['color']
            legend_items_html += f"""
            <div class="legend-item" data-layer-name="{layer_name}">
                <svg width="20" height="15" style="margin-right: 8px; vertical-align: middle;">
                    <rect width="20" height="15" style="fill:{color}; stroke:{color}; stroke-width:1; opacity:0.6;" />
                </svg>
                <span>{layer_name} ({feature_count})</span>
            </div>
            """

    # Build complete side panel HTML with CSS and JavaScript
    side_panel_html = f"""
    <style>
        /* Side panel container */
        #side-panel {{
            position: fixed;
            top: 0;
            left: 0;
            width: 350px;
            height: 100vh;
            background: white;
            box-shadow: 2px 0 8px rgba(0,0,0,0.2);
            z-index: 1001;
            transition: transform 0.3s ease-in-out;
            font-family: Arial, sans-serif;
            display: flex;
            flex-direction: column;
        }}

        #side-panel.collapsed {{
            transform: translateX(-350px);
        }}

        /* Adjust Leaflet controls position to account for panel */
        body:not(.panel-collapsed) .leaflet-left {{
            left: 350px !important;
            transition: left 0.3s ease-in-out;
        }}

        body:not(.panel-collapsed) .leaflet-control-download {{
            right: 10px !important;
            transition: right 0.3s ease-in-out;
        }}

        body.panel-collapsed .leaflet-left {{
            left: 0 !important;
            transition: left 0.3s ease-in-out;
        }}

        body.panel-collapsed .leaflet-control-download {{
            right: 10px !important;
            transition: right 0.3s ease-in-out;
        }}

        /* Toggle button */
        #panel-toggle {{
            position: absolute;
            top: 50%;
            right: -25px;
            transform: translateY(-50%);
            width: 25px;
            height: 60px;
            background: white;
            border: 2px solid rgba(0,0,0,0.2);
            border-left: none;
            border-radius: 0 8px 8px 0;
            box-shadow: 2px 0 6px rgba(0,0,0,0.15);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
            color: #333;
            transition: background 0.2s;
        }}

        #panel-toggle:hover {{
            background: #f5f5f5;
        }}

        /* Panel content area */
        .panel-content {{
            padding: 20px;
            overflow-y: auto;
            flex: 1;
        }}

        /* About section */
        .about-section {{
            margin-bottom: 20px;
        }}

        .about-section details {{
            background: #f8f9fa;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}

        .about-section summary {{
            cursor: pointer;
            font-weight: bold;
            font-size: 14px;
            color: #333;
            user-select: none;
        }}

        .about-section summary:hover {{
            color: #007bff;
        }}

        .about-content {{
            margin-top: 10px;
            font-size: 12px;
            line-height: 1.6;
            color: #444;
        }}

        .about-content p {{
            margin: 8px 0;
        }}

        /* Legend section */
        .legend-section {{
            border-top: 2px solid #ddd;
            padding-top: 15px;
        }}

        .legend-section h4 {{
            margin: 0 0 12px 0;
            font-size: 14px;
            font-weight: bold;
            color: #333;
        }}

        .legend-items {{
            max-height: calc(100vh - 400px);
            overflow-y: auto;
        }}

        .legend-item {{
            padding: 8px 0;
            font-size: 13px;
            color: #333;
            display: flex;
            align-items: center;
            border-bottom: 1px solid #eee;
        }}

        .legend-item:last-child {{
            border-bottom: none;
        }}

        .legend-item i {{
            font-size: 16px;
        }}

        .legend-item span {{
            flex: 1;
        }}

        /* Custom scrollbar */
        .legend-items::-webkit-scrollbar {{
            width: 8px;
        }}

        .legend-items::-webkit-scrollbar-track {{
            background: #f1f1f1;
            border-radius: 4px;
        }}

        .legend-items::-webkit-scrollbar-thumb {{
            background: #888;
            border-radius: 4px;
        }}

        .legend-items::-webkit-scrollbar-thumb:hover {{
            background: #555;
        }}
    </style>

    <div id="side-panel">
        <div id="panel-toggle" onclick="togglePanel()">
            <span id="toggle-icon">◄</span>
        </div>

        <div class="panel-content">
            <!-- About Section -->
            <div class="about-section">
                <details open>
                    <summary>ℹ️ About APPEIT Map Creator</summary>
                    <div class="about-content">
                        <p>
                            The <strong>APPEIT Map Creator</strong> replicates NTIA's APPEIT tool functionality
                            without requiring an ArcGIS Pro license. This tool queries ESRI-hosted FeatureServer
                            REST APIs to perform spatial intersection analysis.
                        </p>
                        <p>
                            <strong>Features:</strong> Interactive Leaflet maps, multi-layer visualization,
                            marker clustering, and GeoJSON export capabilities.
                        </p>
                        <p style="font-size: 11px;">
                            <strong>Data Sources:</strong> EPA RCRA Sites, NPDES Permits, USACE Navigable
                            Waterways, National Register of Historic Places, and other environmental datasets.
                        </p>
                        <p style="font-size: 10px; color: #666; border-top: 1px solid #ddd; padding-top: 8px;">
                            Generated with Claude Code | Open source environmental analysis tool
                        </p>
                    </div>
                </details>
            </div>

            <!-- Legend Section -->
            <div class="legend-section">
                <h4>Active Layers</h4>
                <div class="legend-items">
                    {legend_items_html}
                </div>
            </div>
        </div>
    </div>

    <script>
        // Toggle panel collapse/expand
        function togglePanel() {{
            var panel = document.getElementById('side-panel');
            var icon = document.getElementById('toggle-icon');

            panel.classList.toggle('collapsed');
            document.body.classList.toggle('panel-collapsed');
            icon.textContent = panel.classList.contains('collapsed') ? '►' : '◄';
        }}

        // Update legend based on layer visibility
        document.addEventListener('DOMContentLoaded', function() {{
            // Get the map object (it's stored in a global variable)
            var mapElement = document.querySelector('.folium-map');
            if (mapElement && mapElement._leaflet_id) {{
                var map = window[Object.keys(window).find(key =>
                    window[key] instanceof L.Map && window[key]._container === mapElement
                )];

                if (map) {{
                    // Listen for layer add/remove events
                    map.on('overlayadd', function(e) {{
                        var layerName = e.name;
                        var legendItem = document.querySelector('.legend-item[data-layer-name="' + layerName + '"]');
                        if (legendItem) {{
                            legendItem.style.display = 'flex';
                        }}
                    }});

                    map.on('overlayremove', function(e) {{
                        var layerName = e.name;
                        var legendItem = document.querySelector('.legend-item[data-layer-name="' + layerName + '"]');
                        if (legendItem) {{
                            legendItem.style.display = 'none';
                        }}
                    }});

                    // Initialize legend to show all layers (all are visible by default)
                    setTimeout(function() {{
                        var legendItems = document.querySelectorAll('.legend-item');
                        legendItems.forEach(function(item) {{
                            item.style.display = 'flex';
                        }});
                    }}, 500);
                }}
            }}
        }});
    </script>
    """
    m.get_root().html.add_child(Element(side_panel_html))

    # Fit bounds to polygon
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

    print("   Map created successfully\n")

    return m

print("✓ Cell 5 completed: Web map creation function defined")
print()


# %%
# Cell 6: Generate Output Files and Structure

def generate_output(
    map_obj: folium.Map,
    polygon_gdf: gpd.GeoDataFrame,
    layer_results: Dict[str, gpd.GeoDataFrame],
    metadata: Dict[str, Dict],
    output_name: Optional[str] = None
) -> Path:
    """
    Generate output directory with HTML map and GeoJSON data files.

    Parameters:
    -----------
    map_obj : folium.Map
        Folium map object to save
    polygon_gdf : gpd.GeoDataFrame
        Input polygon
    layer_results : Dict[str, gpd.GeoDataFrame]
        Dictionary of layer results
    metadata : Dict[str, Dict]
        Layer metadata
    output_name : Optional[str]
        Custom output directory name

    Returns:
    --------
    Path
        Path to output directory
    """
    print("=" * 80)
    print("Generating Output Files")
    print("=" * 80)

    # Create timestamped output directory
    if output_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"appeit_map_{timestamp}"

    output_path = OUTPUT_DIR / output_name
    output_path.mkdir(exist_ok=True)

    # Create data subdirectory
    data_path = output_path / 'data'
    data_path.mkdir(exist_ok=True)

    print(f"Output directory: {output_path}")

    # Save input polygon
    print("  - Saving input polygon...")
    polygon_file = data_path / 'input_polygon.geojson'
    polygon_gdf.to_file(polygon_file, driver='GeoJSON')

    # Save each layer's features
    for layer_name, gdf in layer_results.items():
        print(f"  - Saving {layer_name} features...")
        # Sanitize filename
        safe_name = layer_name.replace(' ', '_').replace('/', '_').lower()
        layer_file = data_path / f'{safe_name}.geojson'
        gdf.to_file(layer_file, driver='GeoJSON')

    # Save map HTML
    print("  - Saving interactive map...")
    map_file = output_path / 'index.html'
    map_obj.save(str(map_file))

    # Save metadata JSON
    print("  - Saving metadata...")
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

    with open(metadata_file, 'w') as f:
        json.dump(summary, f, indent=2)

    print()
    print("=" * 80)
    print(" Output Generation Complete")
    print("=" * 80)
    print(f"Files saved to: {output_path}")
    print(f"  - index.html (interactive map)")
    print(f"  - metadata.json (summary statistics)")
    print(f"  - data/ ({len(layer_results) + 1} GeoJSON files)")
    print()
    print(f"To view the map, open: {map_file}")
    print("=" * 80)

    return output_path

print("✓ Cell 6 completed: Output generation function defined")
print()


# %%
# Cell 7: Main Execution Workflow

def main(input_file: str, output_name: Optional[str] = None):
    """
    Main execution workflow for APPEIT Map Creator.

    Parameters:
    -----------
    input_file : str
        Path to input polygon file
    output_name : Optional[str]
        Custom name for output directory
    """
    print()
    print("T" + "=" * 78 + "W")
    print("Q" + " " * 20 + "APPEIT MAP CREATOR WORKFLOW" + " " * 31 + "Q")
    print("Z" + "=" * 78 + "]")
    print()

    try:
        # Step 1: Read input polygon
        polygon_gdf = read_input_polygon(input_file)

        # Extract filename for layer naming
        input_filename = Path(input_file).stem

        # Step 2: Process all layers
        layer_results, metadata = process_all_layers(polygon_gdf, CONFIG)

        # Check if any results found
        if not layer_results:
            print("� WARNING: No intersecting features found in any layer.")
            print("The output map will only show the input polygon.")
            print()

        # Step 3: Create web map
        map_obj = create_web_map(polygon_gdf, layer_results, metadata, CONFIG, input_filename)

        # Step 4: Generate output
        output_path = generate_output(
            map_obj,
            polygon_gdf,
            layer_results,
            metadata,
            output_name
        )

        print()
        print(" WORKFLOW COMPLETE")
        print()

        return output_path

    except Exception as e:
        print()
        print("=" * 80)
        print(" ERROR: Workflow failed")
        print("=" * 80)
        print(f"Error: {str(e)}")
        print()
        import traceback
        traceback.print_exc()
        return None

print("✓ Cell 7 completed: Main execution workflow function defined")
print()


# %%
# Cell 8: Example Usage

if __name__ == "__main__":
    # Example: Process the Pennsylvania test file
    INPUT_FILE = r"C:\Users\lukas\Downloads\pa045_mpb.gpkg"

    # Run the workflow
    output_dir = main(INPUT_FILE)

    if output_dir:
        print(f"\n Success! Open {output_dir / 'index.html'} in your browser.")
    else:
        print("\n Failed to generate map.")
