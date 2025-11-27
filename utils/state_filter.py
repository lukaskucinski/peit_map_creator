"""
State-based layer filtering for geographic optimization.

This module determines which US states an input geometry intersects
and filters layers to only process those relevant to those states.

Functions:
    load_state_boundaries: Load bundled US state boundaries GeoJSON
    get_intersecting_states: Determine which states intersect the geometry
    filter_layers_by_state: Filter layer configs to relevant states
"""

import geopandas as gpd
from pathlib import Path
from pyproj import CRS
from utils.logger import get_logger

logger = get_logger(__name__)

# Complete list of US states + territories for validation
US_STATES = {
    'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado',
    'Connecticut', 'Delaware', 'Florida', 'Georgia', 'Hawaii', 'Idaho',
    'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky', 'Louisiana',
    'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota',
    'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada',
    'New Hampshire', 'New Jersey', 'New Mexico', 'New York',
    'North Carolina', 'North Dakota', 'Ohio', 'Oklahoma', 'Oregon',
    'Pennsylvania', 'Rhode Island', 'South Carolina', 'South Dakota',
    'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia', 'Washington',
    'West Virginia', 'Wisconsin', 'Wyoming', 'District of Columbia',
    'Puerto Rico'
}

# Cache for state boundaries GeoDataFrame
_state_boundaries_cache = None


def load_state_boundaries():
    """
    Load bundled US state boundaries GeoJSON.

    Returns cached data if already loaded.

    Returns:
        gpd.GeoDataFrame: US state boundaries with NAME column
    """
    global _state_boundaries_cache

    if _state_boundaries_cache is not None:
        return _state_boundaries_cache

    # Find the GeoJSON file relative to project root
    module_path = Path(__file__).parent.parent
    geojson_path = module_path / 'static' / 'data' / 'us_states_simplified.geojson'

    if not geojson_path.exists():
        logger.warning(f"US states GeoJSON not found: {geojson_path}")
        return None

    try:
        _state_boundaries_cache = gpd.read_file(geojson_path)
        logger.debug(f"Loaded {len(_state_boundaries_cache)} state boundaries")
        return _state_boundaries_cache
    except Exception as e:
        logger.warning(f"Failed to load state boundaries: {e}")
        return None


def get_intersecting_states(polygon_gdf, buffer_miles=1.0):
    """
    Determine which US states intersect the buffered input geometry.

    Parameters:
        polygon_gdf (gpd.GeoDataFrame): Input polygon geometry in EPSG:4326
        buffer_miles (float): Buffer distance in miles for state detection

    Returns:
        set: Set of state names that intersect the buffered geometry
    """
    states_gdf = load_state_boundaries()

    if states_gdf is None:
        logger.warning("State boundaries not available - returning empty set")
        return set()

    try:
        # Get the input geometry
        input_geom = polygon_gdf.geometry.iloc[0]

        # Buffer the geometry for state detection
        # Convert miles to degrees (approximate: 1 degree ~ 69 miles at equator)
        # This is a rough approximation, but sufficient for state detection
        buffer_degrees = buffer_miles / 69.0
        buffered_geom = input_geom.buffer(buffer_degrees)

        # Find intersecting states
        intersecting = states_gdf[states_gdf.intersects(buffered_geom)]

        # Extract state names
        state_names = set(intersecting['NAME'].tolist())

        logger.debug(f"Input geometry intersects {len(state_names)} state(s): {state_names}")
        return state_names

    except Exception as e:
        logger.warning(f"Error detecting intersecting states: {e}")
        return set()


def filter_layers_by_state(layers, intersecting_states):
    """
    Filter layer configs to only those relevant to intersecting states.

    Filtering logic:
    - Layers WITHOUT 'states' field: Always included (national/federal layers)
    - Layers WITH 'states' field: Included only if ANY state matches

    Parameters:
        layers (list): List of layer configuration dictionaries
        intersecting_states (set): Set of state names from input geometry

    Returns:
        tuple: (filtered_layers, skipped_count, skipped_layers)
            - filtered_layers: List of layer configs to process
            - skipped_count: Number of layers skipped
            - skipped_layers: List of skipped layer names (for logging)
    """
    if not intersecting_states:
        # No state filtering possible - include all layers
        return layers, 0, []

    filtered_layers = []
    skipped_layers = []

    for layer in layers:
        layer_states = layer.get('states')

        if layer_states is None:
            # No states field - always include (national/federal layer)
            filtered_layers.append(layer)
        else:
            # Check if any layer state matches intersecting states
            layer_state_set = set(layer_states) if isinstance(layer_states, list) else {layer_states}

            if layer_state_set & intersecting_states:
                # At least one state matches - include layer
                filtered_layers.append(layer)
            else:
                # No matching states - skip layer
                skipped_layers.append(layer['name'])

    skipped_count = len(skipped_layers)

    if skipped_count > 0:
        logger.info(f"State filter: Skipping {skipped_count} irrelevant state layer(s)")
        logger.debug(f"Skipped layers: {skipped_layers[:5]}{'...' if len(skipped_layers) > 5 else ''}")

    return filtered_layers, skipped_count, skipped_layers
