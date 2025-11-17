"""
Layer Control Helper Functions

This module provides utility functions for organizing layers into groups
and preparing data for the custom layer control panel.

Functions:
    organize_layers_by_group: Group layers with features by their configured group
    generate_layer_control_data: Prepare structured data for the layer control template
    generate_layer_geojson_data: Create embedded GeoJSON data for JavaScript layer creation
"""

import json
import logging
from collections import OrderedDict

logger = logging.getLogger(__name__)


def organize_layers_by_group(config, layer_results):
    """
    Organize layers by their configured groups, only including layers with features.

    Args:
        config (dict): Configuration dictionary with layers list
        layer_results (dict): Dictionary of layer_name -> GeoDataFrame for intersected layers

    Returns:
        OrderedDict: Groups as keys, list of layer configs as values
                     Only includes groups that have at least one layer with features
    """
    groups = OrderedDict()

    for layer_config in config['layers']:
        layer_name = layer_config['name']

        # Only include layers that have intersected features
        if layer_name in layer_results and len(layer_results[layer_name]) > 0:
            group_name = layer_config.get('group', 'Other')

            if group_name not in groups:
                groups[group_name] = []

            # Add layer config with feature count
            layer_data = layer_config.copy()
            layer_data['feature_count'] = len(layer_results[layer_name])
            groups[group_name].append(layer_data)

    logger.debug(f"Organized {len(layer_results)} layers into {len(groups)} groups")
    return groups


def generate_layer_control_data(groups, layer_results, config):
    """
    Generate structured data for the layer control panel template.

    Args:
        groups (OrderedDict): Organized groups from organize_layers_by_group
        layer_results (dict): Dictionary of layer_name -> GeoDataFrame
        config (dict): Configuration dictionary

    Returns:
        dict: Structured data ready for template rendering with group info and layer details
    """
    control_data = {
        'groups': [],
        'total_layers': 0,
        'total_features': 0
    }

    for group_name, layers in groups.items():
        group_info = {
            'name': group_name,
            'layers': [],
            'layer_count': len(layers),
            'feature_count': sum(layer['feature_count'] for layer in layers)
        }

        for layer in layers:
            layer_info = {
                'name': layer['name'],
                'description': layer.get('description', ''),
                'group': group_name,
                'feature_count': layer['feature_count'],
                'geometry_type': layer['geometry_type'],
                'icon': layer.get('icon', 'circle'),
                'icon_color': layer.get('icon_color', 'blue'),
                'color': layer.get('color', '#3388ff'),
                'fill_color': layer.get('fill_color', layer.get('color', '#3388ff')),
                'fill_opacity': layer.get('fill_opacity', 0.6)
            }

            # Add fill_pattern if present (for hatched polygon symbols)
            if 'fill_pattern' in layer:
                layer_info['fill_pattern'] = layer['fill_pattern']

            # Add symbology category symbols if unique value symbology is used
            if 'symbology' in layer and layer['symbology'].get('type') == 'unique_values':
                symbology = layer['symbology']
                field = symbology['field']
                layer_name = layer['name']
                category_symbols = []

                # Get GeoDataFrame for this layer to count features per category
                gdf = layer_results.get(layer_name)

                if gdf is not None and not gdf.empty:
                    # Count features per category
                    for category in symbology.get('categories', []):
                        label = category['label']
                        values = category['values']

                        # Count features matching this category (case-insensitive)
                        count = 0
                        for _, row in gdf.iterrows():
                            attr_value = row.get(field)
                            if attr_value is not None:
                                if any(str(attr_value).upper() == str(v).upper() for v in values):
                                    count += 1

                        category_symbols.append({
                            'label': label,
                            'fill_color': category.get('fill_color', layer.get('color', '#3388ff')),
                            'fill_opacity': category.get('fill_opacity', 0.6),
                            'border_color': category.get('border_color', layer.get('color', '#333333')),
                            'count': count
                        })

                    # Add default category if present
                    if 'default_category' in symbology:
                        default = symbology['default_category']
                        label = default['label']

                        # Count unmapped features
                        count = 0
                        for _, row in gdf.iterrows():
                            attr_value = row.get(field)
                            matched = False

                            if attr_value is not None:
                                for category in symbology.get('categories', []):
                                    if any(str(attr_value).upper() == str(v).upper() for v in category['values']):
                                        matched = True
                                        break

                            if not matched:
                                count += 1

                        if count > 0:  # Only add if there are unmapped features
                            category_symbols.append({
                                'label': label,
                                'fill_color': default.get('fill_color', '#CCCCCC'),
                                'fill_opacity': default.get('fill_opacity', 0.4),
                                'border_color': default.get('border_color', layer.get('color', '#333333')),
                                'count': count
                            })

                layer_info['category_symbols'] = category_symbols

            group_info['layers'].append(layer_info)
            control_data['total_features'] += layer['feature_count']

        control_data['groups'].append(group_info)
        control_data['total_layers'] += len(layers)

    logger.info(f"Generated control data: {control_data['total_layers']} layers in {len(groups)} groups")
    return control_data


def generate_layer_geojson_data(layer_results, polygon_gdf):
    """
    Generate embedded GeoJSON data for JavaScript layer creation.

    Creates a JavaScript object mapping layer names to GeoJSON FeatureCollections
    that can be embedded in the HTML template.

    Args:
        layer_results (dict): Dictionary of layer_name -> GeoDataFrame
        polygon_gdf (GeoDataFrame): Input polygon GeoDataFrame

    Returns:
        str: JavaScript object definition string ready for HTML embedding
    """
    geojson_data = {}

    # Add input polygon
    geojson_data['Input Polygon'] = json.loads(polygon_gdf.to_json())

    # Add each layer
    for layer_name, gdf in layer_results.items():
        if len(gdf) > 0:
            geojson_data[layer_name] = json.loads(gdf.to_json())

    # Convert to JavaScript object format
    js_object = "const layerGeoJSON = " + json.dumps(geojson_data, indent=2) + ";"

    logger.debug(f"Generated GeoJSON data for {len(geojson_data)} layers")
    return js_object
