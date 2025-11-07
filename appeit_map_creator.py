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

def create_web_map(
    polygon_gdf: gpd.GeoDataFrame,
    layer_results: Dict[str, gpd.GeoDataFrame],
    metadata: Dict[str, Dict],
    config: Dict
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
    folium.TileLayer('Esri WorldImagery', name='Esri Satellite').add_to(m)

    # Add input polygon
    print("  - Adding input polygon...")
    folium.GeoJson(
        polygon_gdf,
        name='Input Area',
        style_function=lambda x: {
            'fillColor': '#FFD700',
            'color': '#FF8C00',
            'weight': 3,
            'fillOpacity': 0.2
        },
        tooltip='Input Polygon'
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

            for idx, row in gdf.iterrows():
                # Create popup with all attributes
                popup_html = f"<b>{layer_name}</b><br>"
                popup_html += "<hr>"
                for col in gdf.columns:
                    if col != 'geometry':
                        popup_html += f"<b>{col}:</b> {row[col]}<br>"

                # Add marker to cluster
                folium.Marker(
                    location=[row.geometry.y, row.geometry.x],
                    popup=folium.Popup(popup_html, max_width=300),
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

                for idx, row in gdf.iterrows():
                    popup_html = f"<b>{layer_name}</b><br>"
                    popup_html += "<hr>"
                    for col in gdf.columns:
                        if col != 'geometry':
                            popup_html += f"<b>{col}:</b> {row[col]}<br>"

                    folium.Marker(
                        location=[row.geometry.y, row.geometry.x],
                        popup=folium.Popup(popup_html, max_width=300),
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

    # Add scale bar
    plugins.MeasureControl(position='bottomleft', primary_length_unit='miles').add_to(m)

    # Add fullscreen button
    plugins.Fullscreen(position='topleft').add_to(m)

    # Add mouse position
    plugins.MousePosition().add_to(m)

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

        # Step 2: Process all layers
        layer_results, metadata = process_all_layers(polygon_gdf, CONFIG)

        # Check if any results found
        if not layer_results:
            print("� WARNING: No intersecting features found in any layer.")
            print("The output map will only show the input polygon.")
            print()

        # Step 3: Create web map
        map_obj = create_web_map(polygon_gdf, layer_results, metadata, CONFIG)

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
