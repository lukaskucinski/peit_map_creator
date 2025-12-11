"""
Map building module for PEIT Map Creator.

This module creates interactive Leaflet maps with Folium, incorporating layer controls,
clustering, download functionality, and a collapsible side panel with legend.

Functions:
    create_web_map: Generate complete interactive Leaflet map
"""

import json
from datetime import datetime, timezone, timedelta
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
from utils.basemap_helpers import get_basemap_config
from utils.js_bundler import get_leaflet_pattern_js
from utils.logger import get_logger

logger = get_logger(__name__)

# Template directory path
TEMPLATES_DIR = Path(__file__).parent.parent / 'templates'


# Override Folium's default StripePattern CDN to use our bundled fixed version
# This eliminates the L.Mixin.Events deprecation warning by injecting
# a patched version that uses L.Evented.prototype || L.Mixin.Events
plugins.StripePattern.default_js = []  # Disable external CDN loading


def create_web_map(
    polygon_gdf: gpd.GeoDataFrame,
    layer_results: Dict[str, gpd.GeoDataFrame],
    metadata: Dict[str, Dict],
    config: Dict,
    input_filename: Optional[str] = None,
    project_name: Optional[str] = None,
    xlsx_relative_path: Optional[str] = None,
    pdf_relative_path: Optional[str] = None
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
    project_name : Optional[str]
        Project name for page title (displays as "PEIT Map - {project_name}")
    xlsx_relative_path : Optional[str]
        Relative path to XLSX report file (for About section link)
    pdf_relative_path : Optional[str]
        Relative path to PDF report file (for About section link)

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

    # Add MarkerCluster plugin explicitly to ensure it's available for JavaScript
    # This prevents "instanceof L.MarkerClusterGroup" errors
    marker_cluster_css = Element("""
        <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css"/>
        <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css"/>
    """)
    m.get_root().html.add_child(marker_cluster_css)

    marker_cluster_js = Element("""
        <script src="https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js"></script>
    """)
    m.get_root().html.add_child(marker_cluster_js)

    # Inject fixed Leaflet.pattern library to avoid L.Mixin.Events deprecation warning
    # This must be loaded AFTER Leaflet core but BEFORE StripePattern is used
    leaflet_pattern_js = get_leaflet_pattern_js()
    leaflet_pattern_script = Element(f"""
        <script>
        // Fixed Leaflet.pattern library (eliminates L.Mixin.Events deprecation warning)
        {leaflet_pattern_js}
        </script>
    """)
    m.get_root().html.add_child(leaflet_pattern_script)

    # Add tile layers with custom names
    # Only first layer has control=True to prevent conflicts with custom basemap control
    # All layers added to map so JavaScript can find them, but extras removed in JavaScript init
    folium.TileLayer('OpenStreetMap', name='Street Map', control=True).add_to(m)
    folium.TileLayer('CartoDB positron', name='Light Theme', control=False).add_to(m)
    folium.TileLayer('CartoDB dark_matter', name='Dark Theme', control=False).add_to(m)
    folium.TileLayer('Esri WorldImagery', name='Satellite Imagery', control=False).add_to(m)

    # Add input polygon with lower z-index to allow clicking through to environmental layers
    logger.info("  - Adding input polygon...")
    layer_name = input_filename if input_filename else 'Input Area'

    # Note: We don't add tooltip when interactive=False because Leaflet's tooltip
    # focus listener handling fails on non-interactive layers (getElement error)
    folium.GeoJson(
        polygon_gdf,
        name=layer_name,
        style_function=lambda x: {
            'fillColor': '#FFD700',
            'color': '#FF8C00',
            'weight': 3,
            'fillOpacity': 0.2,
            'className': 'appeit-input-polygon',  # Unique identifier for JavaScript detection
            'interactive': False  # Make non-interactive so clicks pass through to layers below
        }
        # tooltip removed - conflicts with interactive=False causing getElement error
    ).add_to(m)

    # Store layer variable names for JavaScript reference
    layer_var_names = {}

    # Track point layers for centralized identifier injection
    point_layer_info = []

    # Create pattern objects for layers with fill_pattern configuration
    # Patterns must be created before the layer loop and added to map
    pattern_objects = {}
    for layer_config in config['layers']:
        layer_name = layer_config['name']

        # Case 1: Layer-level pattern (existing functionality)
        if 'fill_pattern' in layer_config and layer_config['geometry_type'] == 'polygon':
            pattern_cfg = layer_config['fill_pattern']

            if pattern_cfg.get('type') == 'stripe':
                pattern = plugins.StripePattern(
                    angle=pattern_cfg.get('angle', -45),
                    weight=pattern_cfg.get('weight', 3),
                    space_weight=pattern_cfg.get('space_weight', 3),
                    color=layer_config['color'],
                    space_color=pattern_cfg.get('space_color', '#ffffff'),
                    opacity=pattern_cfg.get('opacity', 0.75),
                    space_opacity=pattern_cfg.get('space_opacity', 0.0)
                )
                pattern.add_to(m)
                pattern_objects[layer_name] = pattern
                logger.debug(f"Created stripe pattern for {layer_name}: angle={pattern_cfg.get('angle', -45)}°")

        # Case 2: Category-level patterns (NEW)
        if 'symbology' in layer_config and layer_config['symbology'].get('type') == 'unique_values':
            symbology = layer_config['symbology']

            # Process regular categories
            for category in symbology.get('categories', []):
                if 'fill_pattern' in category:
                    pattern_cfg = category['fill_pattern']
                    pattern_key = f"{layer_name}::{category['label']}"

                    if pattern_cfg.get('type') == 'stripe':
                        pattern = plugins.StripePattern(
                            angle=pattern_cfg.get('angle', -45),
                            weight=pattern_cfg.get('weight', 3),
                            space_weight=pattern_cfg.get('space_weight', 3),
                            color=category.get('fill_color', layer_config.get('color', '#333333')),
                            space_color=pattern_cfg.get('space_color', '#ffffff'),
                            opacity=pattern_cfg.get('opacity', 0.75),
                            space_opacity=pattern_cfg.get('space_opacity', 0.0)
                        )
                        pattern.add_to(m)
                        pattern_objects[pattern_key] = pattern
                        logger.debug(f"Created stripe pattern for {layer_name} category '{category['label']}': angle={pattern_cfg.get('angle', -45)}°")

            # Process default category
            if 'default_category' in symbology and 'fill_pattern' in symbology['default_category']:
                default_cat = symbology['default_category']
                pattern_cfg = default_cat['fill_pattern']
                pattern_key = f"{layer_name}::{default_cat['label']}"

                if pattern_cfg.get('type') == 'stripe':
                    pattern = plugins.StripePattern(
                        angle=pattern_cfg.get('angle', -45),
                        weight=pattern_cfg.get('weight', 3),
                        space_weight=pattern_cfg.get('space_weight', 3),
                        color=default_cat.get('fill_color', layer_config.get('color', '#333333')),
                        space_color=pattern_cfg.get('space_color', '#ffffff'),
                        opacity=pattern_cfg.get('opacity', 0.75),
                        space_opacity=pattern_cfg.get('space_opacity', 0.0)
                    )
                    pattern.add_to(m)
                    pattern_objects[pattern_key] = pattern
                    logger.debug(f"Created stripe pattern for {layer_name} default category '{default_cat['label']}': angle={pattern_cfg.get('angle', -45)}°")

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

        # Always use MarkerCluster for point layers (ensures reliable toggle behavior)
        # This eliminates Folium wrapper issues and scales to dozens of layers
        use_clustering = (
            config['settings']['enable_clustering'] and
            layer_config['geometry_type'] == 'point'
        )

        if use_clustering:
            # Configure clustering behavior based on feature count
            cluster_options = {}

            # For layers with few features, disable clustering at higher zoom levels
            # so users see individual markers when zoomed in
            if len(gdf) < config['settings']['cluster_threshold']:
                cluster_options['disableClusteringAtZoom'] = 15  # Show individual markers at zoom 15+
                cluster_options['spiderfyOnMaxZoom'] = False
                cluster_options['showCoverageOnHover'] = False
                cluster_options['zoomToBoundsOnClick'] = True
                logger.info(f"    (Using marker clustering - will show individuals at zoom 15+)")
            else:
                logger.info(f"    (Using marker clustering - {len(gdf)} features)")

            # NOTE: Do NOT add 'name' parameter - prevents interference with custom layer control
            marker_cluster = plugins.MarkerCluster(**cluster_options)

            for _, row in gdf.iterrows():
                # Get name value from configured area_name_field, fallback to searching for 'name'
                name_value = None
                area_name_field = layer_config.get('area_name_field')

                if area_name_field and area_name_field in gdf.columns:
                    # Use configured area_name_field
                    name_value = row[area_name_field]
                else:
                    # Fallback: search for first column containing 'name' (case-insensitive)
                    for col in gdf.columns:
                        if col != 'geometry' and 'name' in col.lower():
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

                # Determine icon and color (check for unique value symbology)
                icon_name = layer_config.get('icon', 'circle')
                icon_color = layer_config.get('icon_color', 'blue')

                if 'symbology' in layer_config and layer_config['symbology'].get('type') == 'unique_values':
                    symbology = layer_config['symbology']
                    field = symbology['field']
                    attr_value = row.get(field) if field in gdf.columns else None

                    # Find matching category (case-insensitive)
                    matched_category = None
                    if attr_value is not None:
                        for category in symbology['categories']:
                            if any(str(attr_value).upper() == str(v).upper() for v in category['values']):
                                matched_category = category
                                break

                    # Apply category styling or default
                    if matched_category:
                        icon_name = matched_category.get('icon', icon_name)
                        icon_color = matched_category.get('icon_color', icon_color)
                    elif 'default_category' in symbology:
                        default = symbology['default_category']
                        icon_name = default.get('icon', icon_name)
                        icon_color = default.get('icon_color', icon_color)

                # Add marker to cluster
                folium.Marker(
                    location=[row.geometry.y, row.geometry.x],
                    popup=folium.Popup(popup_html, max_width=400, max_height=600),
                    icon=folium.Icon(
                        color=icon_color,
                        icon=icon_name,
                        prefix='fa'
                    )
                ).add_to(marker_cluster)

            marker_cluster.add_to(m)

            # Track this layer for centralized identifier injection later
            point_layer_info.append({'name': layer_name, 'type': 'cluster'})

            layer_var_names[layer_name] = 'cluster'
            logger.info(f"    ✓ Added {len(gdf)} markers to map")

        else:
            # Add as GeoJSON layer for lines/polygons
            # NOTE: Points always use MarkerCluster above, so this is only for lines/polygons
            if layer_config['geometry_type'] != 'point':
                # Use GeoJSON for lines/polygons
                # Add className for JavaScript layer identification
                sanitized_name = layer_name.replace(' ', '-').replace("'", '').lower()
                layer_class = f'appeit-layer-{sanitized_name}'

                # Use default parameters to capture values (fixes closure bug with multiple polygon layers)
                def style_function(feature, config=layer_config, cls=layer_class, patterns=pattern_objects, lname=layer_name):
                    style = {
                        'color': config['color'],
                        'weight': 3,
                        'opacity': 0.8,
                        'className': cls  # Unique identifier for JavaScript
                    }

                    # Handle line symbology
                    if config['geometry_type'] == 'line':
                        # Check for unique value symbology
                        if 'symbology' in config and config['symbology'].get('type') == 'unique_values':
                            symbology = config['symbology']

                            # Get the attribute value from this feature (support concatenated fields)
                            if 'concat_fields' in symbology:
                                concat_fields = symbology['concat_fields']
                                separator = symbology.get('concat_separator', ',')
                                field_values = [feature['properties'].get(f, '') for f in concat_fields]
                                attr_value = separator.join(str(v) for v in field_values if v)
                            else:
                                field = symbology['field']
                                attr_value = feature['properties'].get(field)

                            # Find matching category (case-insensitive)
                            matched_category = None
                            if attr_value is not None:
                                for category in symbology['categories']:
                                    # Case-insensitive matching
                                    if any(str(attr_value).upper() == str(v).upper() for v in category['values']):
                                        matched_category = category
                                        break

                            # Apply category styling or default
                            if matched_category:
                                style['color'] = matched_category.get('color', config['color'])
                                style['weight'] = matched_category.get('weight', 3)
                                style['opacity'] = matched_category.get('opacity', 0.8)
                            elif 'default_category' in symbology:
                                default = symbology['default_category']
                                style['color'] = default.get('color', config['color'])
                                style['weight'] = default.get('weight', 3)
                                style['opacity'] = default.get('opacity', 0.8)
                            # else: use layer-level color already set above

                    # Add fill properties for polygon layers
                    elif config['geometry_type'] == 'polygon':
                        # Check for unique value symbology
                        if 'symbology' in config and config['symbology'].get('type') == 'unique_values':
                            symbology = config['symbology']

                            # Get the attribute value from this feature (support concatenated fields)
                            if 'concat_fields' in symbology:
                                concat_fields = symbology['concat_fields']
                                separator = symbology.get('concat_separator', ',')
                                field_values = [feature['properties'].get(f, '') for f in concat_fields]
                                attr_value = separator.join(str(v) for v in field_values if v)
                            else:
                                field = symbology['field']
                                attr_value = feature['properties'].get(field)

                            # Find matching category (case-insensitive)
                            matched_category = None
                            if attr_value is not None:
                                for category in symbology['categories']:
                                    # Case-insensitive matching
                                    if any(str(attr_value).upper() == str(v).upper() for v in category['values']):
                                        matched_category = category
                                        break

                            # Apply category styling or default
                            if matched_category:
                                # Check if category has a pattern fill
                                pattern_key = f"{lname}::{matched_category['label']}"
                                if pattern_key in patterns:
                                    # Category has a pattern - use it
                                    style['fillPattern'] = patterns[pattern_key]
                                    style['fillOpacity'] = 1.0  # Must be 1.0 for patterns
                                    style['color'] = matched_category.get('border_color', config['color'])
                                    style['weight'] = 2
                                else:
                                    # No pattern - use solid fill
                                    style['fillColor'] = matched_category.get('fill_color', config['color'])
                                    style['fillOpacity'] = matched_category.get('fill_opacity', 0.6)
                                    style['color'] = matched_category.get('border_color', config['color'])
                                    style['weight'] = 2
                            elif 'default_category' in symbology:
                                default = symbology['default_category']
                                pattern_key = f"{lname}::{default['label']}"
                                if pattern_key in patterns:
                                    # Default category has a pattern
                                    style['fillPattern'] = patterns[pattern_key]
                                    style['fillOpacity'] = 1.0  # Must be 1.0 for patterns
                                    style['color'] = default.get('border_color', config['color'])
                                    style['weight'] = 2
                                else:
                                    # No pattern - use solid fill
                                    style['fillColor'] = default.get('fill_color', '#CCCCCC')
                                    style['fillOpacity'] = default.get('fill_opacity', 0.4)
                                    style['color'] = default.get('border_color', config['color'])
                                    style['weight'] = 2
                            else:
                                # No default specified, use layer-level settings
                                style['fillColor'] = config.get('fill_color', config['color'])
                                style['fillOpacity'] = config.get('fill_opacity', 0.6)

                        # Pattern fills (existing logic for layer-level patterns)
                        elif 'fill_pattern' in config and lname in patterns:
                            # Use pattern fill
                            style['fillPattern'] = patterns[lname]
                            style['fillOpacity'] = 1.0  # Must be 1.0 for patterns to render

                        # Standard solid fill (existing logic)
                        else:
                            style['fillColor'] = config.get('fill_color', config['color'])
                            style['fillOpacity'] = config.get('fill_opacity', 0.6)
                    return style

                def highlight_function(feature, config=layer_config):
                    highlight = {
                        'color': config['color'],
                        'weight': 5,
                        'opacity': 1.0
                    }
                    # Increase fill opacity on hover for polygon layers
                    if config['geometry_type'] == 'polygon':
                        highlight['fillOpacity'] = min(config.get('fill_opacity', 0.6) + 0.2, 1.0)
                    return highlight

                # Create GeoJSON layer with custom click-based popups (matching point feature format)
                # NOTE: Do NOT add 'name' parameter - environmental layers should not appear in default LayerControl
                geojson_layer = folium.GeoJson(
                    gdf,
                    style_function=style_function,
                    highlight_function=highlight_function
                )

                # Add custom popup to each feature in the layer
                for feature in geojson_layer.data['features']:
                    props = feature['properties']

                    # Get name value from configured area_name_field, fallback to searching for 'name'
                    name_value = None
                    area_name_field = layer_config.get('area_name_field')

                    if area_name_field and area_name_field in props:
                        # Use configured area_name_field
                        name_value = props[area_name_field]
                    else:
                        # Fallback: search for first field containing 'name' (case-insensitive)
                        for key in props.keys():
                            if 'name' in key.lower():
                                name_value = props[key]
                                break

                    # Build popup HTML (same format as point features)
                    popup_html = f"<div style='font-size: 10px;'><i>{layer_name}</i></div>"
                    if name_value:
                        popup_html += f"<div style='font-size: 14px; font-weight: bold; margin: 5px 0;'>{name_value}</div>"
                    popup_html += "<hr style='margin: 5px 0;'>"

                    for key, value in props.items():
                        popup_html += f"<b>{key}:</b> {format_popup_value(key, value)}<br>"

                    # Store popup HTML in feature properties for Folium to use
                    feature['properties']['popup_html'] = popup_html

                # Now add popup field to the GeoJson layer
                geojson_layer.add_child(
                    folium.GeoJsonPopup(fields=['popup_html'], labels=False, style="max-width: 400px;")
                )

                geojson_layer.add_to(m)
                layer_var_names[layer_name] = 'geojson'
                logger.info(f"    ✓ Added {len(gdf)} features as GeoJSON layer")

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

    # Add custom basemap control with thumbnails
    logger.info("  - Adding basemap control...")
    basemaps = get_basemap_config()
    basemap_template = env.get_template('basemap_control.html')
    basemap_html = basemap_template.render(basemaps=basemaps)
    m.get_root().html.add_child(Element(basemap_html))

    # Add popup scrollbar fix for seamless integration
    # Applies max-height and overflow to Leaflet's content container instead of Folium's wrapper
    # This ensures scrollbars only appear when content overflows and integrate within the popup border
    popup_css_fix = Element("""
        <style>
            .leaflet-popup-content {
                max-height: 600px;
                overflow-y: auto;
            }
        </style>
    """)
    m.get_root().html.add_child(popup_css_fix)

    # Render download control template
    logger.info("  - Adding download control...")
    download_template = env.get_template('download_control.html')
    download_html = download_template.render(
        layer_sections=generate_layer_download_sections(layer_results, config, input_filename),
        layer_data=generate_layer_data_mapping(layer_results, polygon_gdf)
    )
    m.get_root().html.add_child(Element(download_html))

    # Count features per category for unique value symbology layers
    category_counts = {}
    for layer_config in config['layers']:
        layer_name = layer_config['name']

        # Skip layers without features or without unique value symbology
        if layer_name not in layer_results or len(layer_results[layer_name]) == 0:
            continue
        if 'symbology' not in layer_config or layer_config['symbology'].get('type') != 'unique_values':
            continue

        symbology = layer_config['symbology']
        gdf = layer_results[layer_name]
        category_counts[layer_name] = {}

        # Initialize counts for each category
        for category in symbology['categories']:
            category_counts[layer_name][category['label']] = 0

        # Initialize count for default category if present
        if 'default_category' in symbology:
            category_counts[layer_name][symbology['default_category']['label']] = 0

        # Count features by category (case-insensitive matching)
        for _, row in gdf.iterrows():
            # Get the attribute value (support concatenated fields)
            if 'concat_fields' in symbology:
                concat_fields = symbology['concat_fields']
                separator = symbology.get('concat_separator', ',')
                field_values = [row.get(f, '') for f in concat_fields]
                attr_value = separator.join(str(v) for v in field_values if v)
            else:
                attr_value = row.get(symbology['field'])
            matched = False

            if attr_value is not None:
                for category in symbology['categories']:
                    # Case-insensitive matching
                    if any(str(attr_value).upper() == str(v).upper() for v in category['values']):
                        category_counts[layer_name][category['label']] += 1
                        matched = True
                        break

            # Count unmapped values in default category
            if not matched and 'default_category' in symbology:
                category_counts[layer_name][symbology['default_category']['label']] += 1

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
            # Point layer: check for symbology first
            if 'symbology' in layer_config and layer_config['symbology'].get('type') == 'unique_values':
                # Point layer with unique value symbology
                symbology = layer_config['symbology']

                # Add header entry with total count
                legend_items_html += f"""
                <div class="legend-item legend-header" data-layer-name="{layer_name}">
                    <span style="font-weight: bold;">{layer_name} ({feature_count} total)</span>
                </div>
                """

                # Get feature counts per category
                category_counts_point = {}
                field_name = symbology['field']

                # Use layer_results[layer_name] instead of stale gdf variable
                layer_gdf = layer_results[layer_name]
                for _, row in layer_gdf.iterrows():
                    field_value = str(row.get(field_name, '')).strip().lower()
                    category_counts_point[field_value] = category_counts_point.get(field_value, 0) + 1

                # Display each category with its icon and color
                for category in symbology.get('categories', []):
                    label = category['label']
                    values = [str(v).strip().lower() for v in category.get('values', [])]

                    # Count features in this category
                    count = sum(category_counts_point.get(val, 0) for val in values)

                    if count > 0:  # Only show categories with features
                        icon = category.get('icon', layer_config.get('icon', 'circle'))
                        icon_color = category.get('icon_color', layer_config.get('icon_color', 'blue'))

                        legend_items_html += f"""
                        <div class="legend-item legend-category" data-layer-name="{layer_name}">
                            <i class="fa fa-{icon}" style="color: {icon_color}; margin-right: 8px;"></i>
                            <span>{label} ({count})</span>
                        </div>
                        """

                # Handle default category if present
                if 'default_category' in symbology:
                    default_category = symbology['default_category']
                    default_label = default_category['label']

                    # Count features not in any explicit category
                    matched_values = set()
                    for category in symbology.get('categories', []):
                        matched_values.update([str(v).strip().lower() for v in category.get('values', [])])

                    default_count = sum(count for value, count in category_counts_point.items() if value not in matched_values)

                    if default_count > 0:
                        default_icon = default_category.get('icon', layer_config.get('icon', 'circle'))
                        default_icon_color = default_category.get('icon_color', layer_config.get('icon_color', 'blue'))

                        legend_items_html += f"""
                        <div class="legend-item legend-category" data-layer-name="{layer_name}">
                            <i class="fa fa-{default_icon}" style="color: {default_icon_color}; margin-right: 8px;"></i>
                            <span>{default_label} ({default_count})</span>
                        </div>
                        """
            else:
                # Point layer without symbology: use default icon/color
                icon = layer_config['icon']
                icon_color = layer_config['icon_color']
                legend_items_html += f"""
                <div class="legend-item" data-layer-name="{layer_name}">
                    <i class="fa fa-{icon}" style="color: {icon_color}; margin-right: 8px;"></i>
                    <span>{layer_name} ({feature_count})</span>
                </div>
                """
        elif geometry_type == 'line':
            # Line layer: show line sample (with unique value symbology support)
            color = layer_config['color']

            # Check for unique value symbology
            if 'symbology' in layer_config and layer_config['symbology'].get('type') == 'unique_values':
                symbology = layer_config['symbology']

                # Layer header (non-collapsible)
                legend_items_html += f"""
                <div class="legend-item legend-header" data-layer-name="{layer_name}">
                    <span style="font-weight: bold;">{layer_name} ({feature_count} total)</span>
                </div>
                """

                # Category entries (flat list, no nesting)
                for category in symbology['categories']:
                    label = category['label']
                    line_color = category.get('color', color)
                    count = category_counts.get(layer_name, {}).get(label, 0)

                    if count > 0:  # Only show categories with features
                        legend_items_html += f"""
                        <div class="legend-item legend-category" data-layer-name="{layer_name}">
                            <svg width="30" height="15" style="margin-right: 8px; vertical-align: middle;">
                                <line x1="0" y1="7" x2="30" y2="7" style="stroke:{line_color}; stroke-width:3;" />
                            </svg>
                            <span>{label} ({count})</span>
                        </div>
                        """

                # Default category if present
                if 'default_category' in symbology:
                    default = symbology['default_category']
                    label = default['label']
                    count = category_counts.get(layer_name, {}).get(label, 0)

                    if count > 0:
                        line_color = default.get('color', color)

                        legend_items_html += f"""
                        <div class="legend-item legend-category" data-layer-name="{layer_name}">
                            <svg width="30" height="15" style="margin-right: 8px; vertical-align: middle;">
                                <line x1="0" y1="7" x2="30" y2="7" style="stroke:{line_color}; stroke-width:3;" />
                            </svg>
                            <span>{label} ({count})</span>
                        </div>
                        """
            else:
                # Simple line symbology (no categories)
                legend_items_html += f"""
                <div class="legend-item" data-layer-name="{layer_name}">
                    <svg width="30" height="15" style="margin-right: 8px; vertical-align: middle;">
                        <line x1="0" y1="7" x2="30" y2="7" style="stroke:{color}; stroke-width:3;" />
                    </svg>
                    <span>{layer_name} ({feature_count})</span>
                </div>
                """
        elif geometry_type == 'polygon':
            # Polygon layer: show filled rectangle (solid, hatched, or unique value symbology)
            border_color = layer_config['color']

            # Check for unique value symbology
            if 'symbology' in layer_config and layer_config['symbology'].get('type') == 'unique_values':
                symbology = layer_config['symbology']

                # Layer header (non-collapsible)
                legend_items_html += f"""
                <div class="legend-item legend-header" data-layer-name="{layer_name}">
                    <span style="font-weight: bold;">{layer_name} ({feature_count} total)</span>
                </div>
                """

                # Category entries (flat list, no nesting)
                for category in symbology['categories']:
                    label = category['label']
                    fill_color = category.get('fill_color', border_color)
                    fill_opacity = category.get('fill_opacity', 0.6)
                    cat_border = category.get('border_color', border_color)
                    count = category_counts.get(layer_name, {}).get(label, 0)

                    if count > 0:  # Only show categories with features
                        # Check if category has a pattern fill
                        if 'fill_pattern' in category and category['fill_pattern'].get('type') == 'stripe':
                            pattern_cfg = category['fill_pattern']
                            pattern_angle = pattern_cfg.get('angle', -45)
                            pattern_weight = pattern_cfg.get('weight', 3)
                            pattern_space = pattern_cfg.get('space_weight', 3)
                            pattern_opacity = pattern_cfg.get('opacity', 0.75)
                            pattern_id = f"legend-hatch-{sanitized_name}-{label.replace(' ', '-').lower()}"

                            legend_items_html += f"""
                            <div class="legend-item legend-category" data-layer-name="{layer_name}">
                                <svg width="20" height="15" style="margin-right: 8px; vertical-align: middle;">
                                    <defs>
                                        <pattern id="{pattern_id}" patternUnits="userSpaceOnUse"
                                                 width="{pattern_weight + pattern_space}" height="{pattern_weight + pattern_space}"
                                                 patternTransform="rotate({pattern_angle} 0 0)">
                                            <line x1="0" y1="0" x2="0" y2="{pattern_weight + pattern_space}"
                                                  style="stroke:{fill_color}; stroke-width:{pattern_weight}; opacity:{pattern_opacity};" />
                                        </pattern>
                                    </defs>
                                    <rect width="20" height="15" style="fill:url(#{pattern_id}); stroke:{cat_border}; stroke-width:1;" />
                                </svg>
                                <span>{label} ({count})</span>
                            </div>
                            """
                        else:
                            # Solid fill
                            legend_items_html += f"""
                            <div class="legend-item legend-category" data-layer-name="{layer_name}">
                                <svg width="20" height="15" style="margin-right: 8px; vertical-align: middle;">
                                    <rect width="20" height="15" style="fill:{fill_color}; fill-opacity:{fill_opacity}; stroke:{cat_border}; stroke-width:1;" />
                                </svg>
                                <span>{label} ({count})</span>
                            </div>
                            """

                # Default category if present
                if 'default_category' in symbology:
                    default = symbology['default_category']
                    label = default['label']
                    count = category_counts.get(layer_name, {}).get(label, 0)

                    if count > 0:
                        fill_color = default.get('fill_color', '#CCCCCC')
                        fill_opacity = default.get('fill_opacity', 0.4)
                        cat_border = default.get('border_color', border_color)

                        # Check if default category has a pattern fill
                        if 'fill_pattern' in default and default['fill_pattern'].get('type') == 'stripe':
                            pattern_cfg = default['fill_pattern']
                            pattern_angle = pattern_cfg.get('angle', -45)
                            pattern_weight = pattern_cfg.get('weight', 3)
                            pattern_space = pattern_cfg.get('space_weight', 3)
                            pattern_opacity = pattern_cfg.get('opacity', 0.75)
                            pattern_id = f"legend-hatch-{sanitized_name}-{label.replace(' ', '-').lower()}"

                            legend_items_html += f"""
                            <div class="legend-item legend-category" data-layer-name="{layer_name}">
                                <svg width="20" height="15" style="margin-right: 8px; vertical-align: middle;">
                                    <defs>
                                        <pattern id="{pattern_id}" patternUnits="userSpaceOnUse"
                                                 width="{pattern_weight + pattern_space}" height="{pattern_weight + pattern_space}"
                                                 patternTransform="rotate({pattern_angle} 0 0)">
                                            <line x1="0" y1="0" x2="0" y2="{pattern_weight + pattern_space}"
                                                  style="stroke:{fill_color}; stroke-width:{pattern_weight}; opacity:{pattern_opacity};" />
                                        </pattern>
                                    </defs>
                                    <rect width="20" height="15" style="fill:url(#{pattern_id}); stroke:{cat_border}; stroke-width:1;" />
                                </svg>
                                <span>{label} ({count})</span>
                            </div>
                            """
                        else:
                            # Solid fill
                            legend_items_html += f"""
                            <div class="legend-item legend-category" data-layer-name="{layer_name}">
                                <svg width="20" height="15" style="margin-right: 8px; vertical-align: middle;">
                                    <rect width="20" height="15" style="fill:{fill_color}; fill-opacity:{fill_opacity}; stroke:{cat_border}; stroke-width:1;" />
                                </svg>
                                <span>{label} ({count})</span>
                            </div>
                            """

            # Check if layer uses hatched pattern
            elif 'fill_pattern' in layer_config and layer_config['fill_pattern'].get('type') == 'stripe':
                # Generate hatched pattern legend
                pattern_cfg = layer_config['fill_pattern']
                pattern_angle = pattern_cfg.get('angle', -45)
                pattern_color = border_color
                pattern_opacity = pattern_cfg.get('opacity', 0.75)

                # Create unique pattern ID for this layer
                pattern_id = f"legend-hatch-{layer_name.replace(' ', '-').lower()}"

                legend_items_html += f"""
                <div class="legend-item" data-layer-name="{layer_name}">
                    <svg width="20" height="15" style="margin-right: 8px; vertical-align: middle;">
                        <defs>
                            <pattern id="{pattern_id}" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate({pattern_angle})">
                                <line x1="0" y1="0" x2="0" y2="4" stroke="{pattern_color}" stroke-width="1.5" opacity="{pattern_opacity}"/>
                            </pattern>
                        </defs>
                        <rect width="20" height="15" style="fill:url(#{pattern_id}); stroke:{border_color}; stroke-width:1;" />
                    </svg>
                    <span>{layer_name} ({feature_count})</span>
                </div>
                """
            else:
                # Solid fill
                fill_color = layer_config.get('fill_color', border_color)
                fill_opacity = layer_config.get('fill_opacity', 0.6)
                legend_items_html += f"""
                <div class="legend-item" data-layer-name="{layer_name}">
                    <svg width="20" height="15" style="margin-right: 8px; vertical-align: middle;">
                        <rect width="20" height="15" style="fill:{fill_color}; fill-opacity:{fill_opacity}; stroke:{border_color}; stroke-width:1;" />
                    </svg>
                    <span>{layer_name} ({feature_count})</span>
                </div>
                """

    # Render side panel template
    side_panel_template = env.get_template('side_panel.html')
    # Use US Central timezone (UTC-6) for consistent date across local and Modal environments
    us_central = timezone(timedelta(hours=-6))
    now_central = datetime.now(us_central)
    side_panel_html = side_panel_template.render(
        legend_items=legend_items_html,
        xlsx_file=xlsx_relative_path,
        pdf_file=pdf_relative_path,
        creation_date=f"{now_central.month}/{now_central.day}/{now_central.year}"
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

    # Add centralized point layer identifier script (if there are point layers)
    if point_layer_info:
        logger.info("  - Adding point layer identifiers...")
        # Build identifier function calls
        identifier_assignments = []
        for info in point_layer_info:
            escaped_name = info['name'].replace("'", "\\'").replace('"', '\\"')
            if info['type'] == 'cluster':
                identifier_assignments.append(f"            identifyCluster('{escaped_name}');")
            else:
                identifier_assignments.append(f"            identifyFeatureGroup('{escaped_name}');")

        assignments_js = "\n".join(identifier_assignments)

        point_identifier_script = f"""
    <script>
    (function() {{
        // Find and tag point layers with custom identifiers
        // This runs after Folium has added all layers to the Leaflet map
        function identifyCluster(name) {{
            try {{
                var clusters = [];
                // Find map object
                var mapObj = null;
                for (var key in window) {{
                    if (window[key] && typeof L !== 'undefined' && typeof L.Map !== 'undefined' && window[key] instanceof L.Map) {{
                        mapObj = window[key];
                        break;
                    }}
                }}

                if (!mapObj) return;

                // Collect unidentified clusters (with defensive check)
                if (typeof L.MarkerClusterGroup === 'undefined') {{
                    console.warn('MarkerClusterGroup not loaded, skipping cluster identification');
                    return;
                }}

                mapObj.eachLayer(function(layer) {{
                    if (layer instanceof L.MarkerClusterGroup && !layer._appeitLayerName) {{
                        clusters.push(layer);
                    }}
                }});

                // Tag the first unidentified cluster
                if (clusters.length > 0) {{
                    clusters[0]._appeitLayerName = name;
                    console.log('Added identifier to MarkerCluster:', name);
                }}
            }} catch (error) {{
                console.error('Error in identifyCluster:', error);
            }}
        }}

        function identifyFeatureGroup(name) {{
            try {{
                var groups = [];
                // Find map object
                var mapObj = null;
                for (var key in window) {{
                    if (window[key] && typeof L !== 'undefined' && typeof L.Map !== 'undefined' && window[key] instanceof L.Map) {{
                        mapObj = window[key];
                        break;
                    }}
                }}

                if (!mapObj) return;

                // Defensive check for FeatureGroup
                if (typeof L.FeatureGroup === 'undefined') {{
                    console.warn('FeatureGroup not loaded, skipping feature group identification');
                    return;
                }}

                // Collect unidentified feature groups (excluding clusters and input polygon)
                mapObj.eachLayer(function(layer) {{
                    var isFeatureGroup = layer instanceof L.FeatureGroup;
                    var isMarkerCluster = (typeof L.MarkerClusterGroup !== 'undefined') && (layer instanceof L.MarkerClusterGroup);

                    if (isFeatureGroup && !isMarkerCluster && !layer._appeitLayerName) {{
                        // Check if this is the input polygon wrapper by looking for className
                        var isInputPolygon = false;

                        if (layer._layers) {{
                            for (var layerId in layer._layers) {{
                                var subLayer = layer._layers[layerId];
                                if (subLayer._path && subLayer._path.classList &&
                                    subLayer._path.classList.contains('appeit-input-polygon')) {{
                                    isInputPolygon = true;
                                    console.log('Skipping input polygon wrapper during identification');
                                    break;
                                }}
                            }}
                        }}

                        if (!isInputPolygon) {{
                            groups.push(layer);
                        }}
                    }}
                }});

                // Tag the first unidentified feature group
                if (groups.length > 0) {{
                    groups[0]._appeitLayerName = name;
                    console.log('Added identifier to FeatureGroup:', name);
                }}
            }} catch (error) {{
                console.error('Error in identifyFeatureGroup:', error);
            }}
        }}

        // Wait for map to be ready, then add identifiers in order
        function addIdentifiers() {{
{assignments_js}
        }}

        // Run after DOM is loaded with delay to ensure plugins are loaded
        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', function() {{
                setTimeout(addIdentifiers, 300);
            }});
        }} else {{
            setTimeout(addIdentifiers, 300);
        }}
    }})();
    </script>
    """
        m.get_root().html.add_child(Element(point_identifier_script))

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
    const layerNames = {json.dumps(list(layer_results.keys()))};
    let layerIndex = 0;

    // Function to find and store map object
    function initializeLayerControl() {{
        try {{
            // Find the Leaflet map object
            const mapElement = document.querySelector('.folium-map');
            if (!mapElement) {{
                console.error('Map element not found');
                return;
            }}

            // Verify Leaflet is loaded
            if (typeof L === 'undefined') {{
                console.error('Leaflet library not loaded');
                return;
            }}

            // Store map reference globally
            window.mapObject = null;

            // Find map in Folium's generated variables (with defensive check)
            for (let key in window) {{
                if (window[key] && typeof L.Map !== 'undefined' && window[key] instanceof L.Map) {{
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
            const geojsonLayers = [];     // For lines/polygons (use className)
            const pointLayerObjects = []; // For clusters/featuregroups (use order)

            window.mapObject.eachLayer(function(layer) {{
                // Skip tile layers (with defensive check)
                if (typeof L.TileLayer !== 'undefined' && layer instanceof L.TileLayer) return;

                // Identify input polygon by className 'appeit-input-polygon'
                if (typeof L.GeoJSON !== 'undefined' && layer instanceof L.GeoJSON) {{
                const layerElements = Object.values(layer._layers || {{}});

                // Check if this is the input polygon
                const hasInputClass = layerElements.some(function(l) {{
                    return l._path &&
                           l._path.classList &&
                           l._path.classList.contains('appeit-input-polygon');
                }});

                if (hasInputClass) {{
                    window.inputPolygonLayer = layer;
                    console.log('Found input polygon by className');
                    return;
                }}

                // This is an environmental GeoJson layer (line/polygon)
                geojsonLayers.push(layer);
                console.log('Found GeoJson layer (will match by className)');
            }}

            // Collect point layers (MarkerCluster, FeatureGroup) with custom identifier (with defensive checks)
            var isMarkerCluster = (typeof L.MarkerClusterGroup !== 'undefined') && (layer instanceof L.MarkerClusterGroup);
            var isFeatureGroup = (typeof L.FeatureGroup !== 'undefined') && (layer instanceof L.FeatureGroup);

            if (isMarkerCluster || isFeatureGroup) {{
                // Only collect layers that have our custom _appeitLayerName property
                // This filters out phantom layers and Folium internal layers
                if (layer._appeitLayerName) {{
                    pointLayerObjects.push(layer);
                    console.log('Found point layer:', layer.constructor.name, '- Name:', layer._appeitLayerName);
                }} else {{
                    console.log('Skipping point layer without identifier:', layer.constructor.name);
                }}
            }}
        }});

        // Match GeoJson layers by className
        geojsonLayers.forEach(function(layer) {{
            const layerElements = Object.values(layer._layers || {{}});

            // Try to match with each layer name
            for (let i = 0; i < layerNames.length; i++) {{
                const layerName = layerNames[i];
                const sanitized = layerName.replace(/\\s+/g, '-').replace(/'/g, '').toLowerCase();
                const className = 'appeit-layer-' + sanitized;

                const hasClass = layerElements.some(function(l) {{
                    return l._path &&
                           l._path.classList &&
                           l._path.classList.contains(className);
                }});

                if (hasClass) {{
                    mapLayers[layerName] = layer;
                    console.log('Mapped GeoJson layer by className:', layerName);
                    break;
                }}
            }}
        }});

        // Match point layers by custom property (not order)
        // This is reliable because each layer has been tagged with _appeitLayerName during creation
        pointLayerObjects.forEach(function(layer) {{
            const layerName = layer._appeitLayerName;
            // Verify this layer name is in our expected layer list
            if (layerNames.includes(layerName)) {{
                mapLayers[layerName] = layer;
                console.log('Mapped point layer by property:', layerName);
            }} else {{
                console.warn('Found point layer with unexpected name:', layerName);
            }}
        }});

        console.log('Layer control initialized with', Object.keys(mapLayers).length, 'layers');
        }} catch (error) {{
            console.error('Error in initializeLayerControl:', error);
        }}
    }}

    // Initialize when DOM is ready with longer delay to ensure plugins are loaded
    // Identifier script runs at 300ms, so we wait 500ms to ensure it completes
    if (document.readyState === 'loading') {{
        document.addEventListener('DOMContentLoaded', function() {{
            setTimeout(initializeLayerControl, 500);
        }});
    }} else {{
        setTimeout(initializeLayerControl, 500);
    }}

    // Comprehensive page refresh detection for all navigation scenarios
    // This ensures layer visibility and checkbox states are always in sync

    // Method 1: Detect bfcache restoration (standard approach)
    window.addEventListener('pageshow', function(event) {{
        if (event.persisted) {{
            console.log('Page restored from bfcache, refreshing...');
            window.location.reload();
        }}
    }});

    // Method 2: Detect back/forward navigation (works for file:// protocol)
    window.addEventListener('load', function() {{
        // Check if page was loaded via back/forward button
        if (performance.navigation && performance.navigation.type === 2) {{
            console.log('Back/forward navigation detected, refreshing...');
            window.location.reload();
        }}

        // Modern browsers: use Navigation Timing API Level 2
        if (performance.getEntriesByType) {{
            var navEntries = performance.getEntriesByType('navigation');
            if (navEntries.length > 0 && navEntries[0].type === 'back_forward') {{
                console.log('Back/forward navigation detected (Navigation API), refreshing...');
                window.location.reload();
            }}
        }}
    }});
    </script>
    """

    m.get_root().html.add_child(Element(layer_management_script))

    # Fit bounds to polygon
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

    # Set page title with project name
    title = f"PEIT Map - {project_name}" if project_name else "PEIT Map"
    m.get_root().title = title

    # Add inline SVG favicon (purple map layers icon matching app branding)
    # URL-encoded SVG for data URI compatibility
    favicon_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><rect fill="%237C3AED" width="48" height="48" rx="8"/><path fill="white" d="M12 16h24l-12 8zm0 8h24l-12 8z" opacity="0.9"/></svg>'
    favicon_element = Element(f'''
        <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,{favicon_svg}">
    ''')
    m.get_root().header.add_child(favicon_element)

    logger.info("  ✓ Map created successfully\n")

    return m
