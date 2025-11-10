"""
Map building module for APPEIT Map Creator.

This module creates interactive Leaflet maps with Folium, incorporating layer controls,
clustering, download functionality, and a collapsible side panel with legend.

Functions:
    create_web_map: Generate complete interactive Leaflet map
"""

import folium
import geopandas as gpd
from folium import plugins
from folium.plugins import Geocoder
from folium import Element
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from typing import Dict, Optional
from utils.html_generators import generate_layer_download_sections, generate_layer_data_mapping
from utils.popup_formatters import format_popup_value
from utils.layer_control_helpers import organize_layers_by_group, generate_layer_control_data, generate_layer_geojson_data
from utils.logger import get_logger

logger = get_logger(__name__)

# Template directory path
TEMPLATES_DIR = Path(__file__).parent.parent / 'templates'


def create_web_map(
    polygon_gdf: gpd.GeoDataFrame,
    layer_results: Dict[str, gpd.GeoDataFrame],
    metadata: Dict[str, Dict],
    config: Dict,
    input_filename: Optional[str] = None
) -> folium.Map:
    """
    Create an interactive Leaflet map with all layers.

    Generates a fully-featured web map including:
    - Multiple base map options
    - Layered environmental data with custom styling
    - Point clustering for large datasets
    - Download control (GeoJSON, Shapefile, KMZ)
    - Collapsible side panel with legend
    - Geocoder search
    - Measurement tools
    - Fullscreen mode

    Parameters:
    -----------
    polygon_gdf : gpd.GeoDataFrame
        Input polygon to display
    layer_results : Dict[str, gpd.GeoDataFrame]
        Dictionary of layer results (layer name -> GeoDataFrame)
    metadata : Dict[str, Dict]
        Layer metadata
    config : Dict
        Configuration dictionary
    input_filename : Optional[str]
        Name of input file (without extension) for layer naming

    Returns:
    --------
    folium.Map
        Folium map object ready to be saved

    Example:
        >>> map_obj = create_web_map(polygon_gdf, results, metadata, config, 'pa045_mpb')
        >>> map_obj.save('output.html')
    """
    logger.info("=" * 80)
    logger.info("Creating Interactive Web Map")
    logger.info("=" * 80)

    # Calculate map center from polygon bounds
    bounds = polygon_gdf.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2

    # Initialize map with no default tiles
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=config['settings']['default_zoom'],
        tiles=None
    )

    # Add tile layers with custom names
    folium.TileLayer('OpenStreetMap', name='Street Map', control=True).add_to(m)
    folium.TileLayer('CartoDB positron', name='Light Theme').add_to(m)
    folium.TileLayer('CartoDB dark_matter', name='Dark Theme').add_to(m)
    folium.TileLayer('Esri WorldImagery', name='Satellite Imagery').add_to(m)

    # Add input polygon
    logger.info("  - Adding input polygon...")
    layer_name = input_filename if input_filename else 'Input Area'
    folium.GeoJson(
        polygon_gdf,
        name=layer_name,
        style_function=lambda x: {
            'fillColor': '#FFD700',
            'color': '#FF8C00',
            'weight': 3,
            'fillOpacity': 0.2,
            'className': 'appeit-input-polygon'  # Unique identifier for JavaScript detection
        },
        tooltip=layer_name
    ).add_to(m)

    # Store layer variable names for JavaScript reference
    layer_var_names = {}

    # Add each layer with appropriate styling
    # Note: Layers are added to map but will be controlled via custom layer control panel
    for layer_config in config['layers']:
        layer_name = layer_config['name']

        if layer_name not in layer_results:
            logger.info(f"  - Skipping {layer_name} (no features)")
            continue

        gdf = layer_results[layer_name]

        # Skip if no features
        if len(gdf) == 0:
            logger.info(f"  - Skipping {layer_name} (0 features)")
            continue

        logger.info(f"  - Adding {layer_name} ({len(gdf)} features)...")

        # Check if clustering should be used
        use_clustering = (
            config['settings']['enable_clustering'] and
            layer_config['geometry_type'] == 'point' and
            len(gdf) >= config['settings']['cluster_threshold']
        )

        if use_clustering:
            logger.info("    (Using marker clustering)")
            # Add name for JavaScript layer identification (doesn't show in LayerControl)
            marker_cluster = plugins.MarkerCluster(name=layer_name)

            for _, row in gdf.iterrows():
                # Find name column (case-insensitive search for first column containing 'name')
                name_col = None
                name_value = None
                for col in gdf.columns:
                    if col != 'geometry' and 'name' in col.lower():
                        name_col = col
                        name_value = row[col]
                        break

                # Create popup with all attributes
                popup_html = f"<div style='font-size: 10px;'><i>{layer_name}</i></div>"
                if name_value:
                    popup_html += f"<div style='font-size: 14px; font-weight: bold; margin: 5px 0;'>{name_value}</div>"
                popup_html += "<hr style='margin: 5px 0;'>"

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
            layer_var_names[layer_name] = 'cluster'
            logger.info(f"    ✓ Added {len(gdf)} clustered markers to map")

        else:
            # Add as GeoJSON layer
            if layer_config['geometry_type'] == 'point':
                # Use markers for points
                # Add name for JavaScript layer identification (doesn't show in LayerControl)
                feature_group = folium.FeatureGroup(name=layer_name)

                for _, row in gdf.iterrows():
                    # Find name column (case-insensitive search for first column containing 'name')
                    name_col = None
                    name_value = None
                    for col in gdf.columns:
                        if col != 'geometry' and 'name' in col.lower():
                            name_col = col
                            name_value = row[col]
                            break

                    # Create popup with all attributes
                    popup_html = f"<div style='font-size: 10px;'><i>{layer_name}</i></div>"
                    if name_value:
                        popup_html += f"<div style='font-size: 14px; font-weight: bold; margin: 5px 0;'>{name_value}</div>"
                    popup_html += "<hr style='margin: 5px 0;'>"

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
                layer_var_names[layer_name] = 'featuregroup'
                logger.info(f"    ✓ Added {len(gdf)} point markers to map")

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

                # Add name for JavaScript layer identification (doesn't show in LayerControl if no control param)
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
                layer_var_names[layer_name] = 'geojson'
                logger.info(f"    ✓ Added {len(gdf)} features as GeoJSON layer")

    # Add LayerControl for base map switching
    # Note: Overlay layers will be hidden via CSS since they're controlled by custom panel
    folium.LayerControl(position='topright', collapsed=False).add_to(m)

    # Hide overlay section of LayerControl using CSS (show only base maps)
    hide_overlays_css = """
<style>
/* Hide overlay layers from LayerControl - they're managed by custom right panel */
.leaflet-control-layers-overlays {
    display: none !important;
}
</style>
"""
    m.get_root().html.add_child(Element(hide_overlays_css))

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

    # Setup Jinja2 template environment
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

    # Render download control template
    logger.info("  - Adding download control...")
    download_template = env.get_template('download_control.html')
    download_html = download_template.render(
        layer_sections=generate_layer_download_sections(layer_results, config, input_filename),
        layer_data=generate_layer_data_mapping(layer_results, polygon_gdf)
    )
    m.get_root().html.add_child(Element(download_html))

    # Generate legend HTML for side panel
    logger.info("  - Adding side panel with legend...")
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

    # Render side panel template
    side_panel_template = env.get_template('side_panel.html')
    side_panel_html = side_panel_template.render(
        legend_items=legend_items_html
    )
    m.get_root().html.add_child(Element(side_panel_html))

    # Render layer control panel (right side)
    logger.info("  - Adding layer control panel...")
    groups = organize_layers_by_group(config, layer_results)
    control_data = generate_layer_control_data(groups, layer_results, config)

    layer_control_template = env.get_template('layer_control_panel.html')
    layer_control_html = layer_control_template.render(
        groups=control_data['groups'],
        input_filename=input_filename or 'Input Geometry'
    )
    m.get_root().html.add_child(Element(layer_control_html))

    # Add JavaScript to create and manage layer objects from GeoJSON
    logger.info("  - Adding layer management JavaScript...")
    geojson_data_js = generate_layer_geojson_data(layer_results, polygon_gdf)

    layer_management_script = f"""
    <script>
    // Embed GeoJSON data
    {geojson_data_js}

    // Store layer references by iterating through map layers and matching them
    // Since we removed 'name' from layers to prevent them appearing in LayerControl,
    // we need to store them by order of creation and match with layer list
    const layerNames = {list(layer_results.keys())};
    let layerIndex = 0;

    // Function to find and store map object
    function initializeLayerControl() {{
        // Find the Leaflet map object
        const mapElement = document.querySelector('.folium-map');
        if (!mapElement) {{
            console.error('Map element not found');
            return;
        }}

        // Store map reference globally
        window.mapObject = null;

        // Find map in Folium's generated variables
        for (let key in window) {{
            if (window[key] && window[key] instanceof L.Map) {{
                window.mapObject = window[key];
                break;
            }}
        }}

        if (!window.mapObject) {{
            console.error('Map object not found');
            return;
        }}

        // Get all non-base layers from the map
        window.inputPolygonLayer = null;
        const foundLayers = [];  // Array of {{name, layer}} objects

        window.mapObject.eachLayer(function(layer) {{
            // Skip tile layers
            if (layer instanceof L.TileLayer) return;

            // Identify input polygon by className 'appeit-input-polygon'
            if (layer instanceof L.GeoJSON) {{
                // Check if this layer has the input polygon className
                const hasInputClass = Object.values(layer._layers || {{}}).some(function(l) {{
                    return l._path &&
                           l._path.classList &&
                           l._path.classList.contains('appeit-input-polygon');
                }});

                if (hasInputClass) {{
                    window.inputPolygonLayer = layer;
                    console.log('Found input polygon by className');
                    return;  // Skip adding to foundLayers
                }}
            }}

            // Collect environmental data layers and try to get their names
            if (layer instanceof L.MarkerClusterGroup ||
                layer instanceof L.FeatureGroup ||
                layer instanceof L.GeoJSON) {{

                // Try to get the layer name from options
                let layerName = null;
                if (layer.options && layer.options.name) {{
                    layerName = layer.options.name;
                }}

                foundLayers.push({{
                    name: layerName,
                    layer: layer
                }});

                console.log('Found layer:', layerName || 'unnamed', layer);
            }}
        }});

        // Map layers by NAME, not by index position (order-independent!)
        foundLayers.forEach(function(item) {{
            if (item.name && layerNames.includes(item.name)) {{
                mapLayers[item.name] = item.layer;
                console.log('Mapped layer by name:', item.name);
            }} else if (item.name) {{
                console.warn('Found layer not in layerNames:', item.name);
            }} else {{
                console.warn('Found unnamed layer:', item.layer);
            }}
        }});

        console.log('Layer control initialized with', Object.keys(mapLayers).length, 'layers');
    }}

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', initializeLayerControl);
    }} else {{
        initializeLayerControl();
    }}
    </script>
    """

    m.get_root().html.add_child(Element(layer_management_script))

    # Fit bounds to polygon
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

    logger.info("  ✓ Map created successfully\n")

    return m
