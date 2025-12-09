"""
Configuration loading for PEIT Map Creator.

This module handles loading and validation of the layer configuration JSON file.

Constants:
    PROJECT_ROOT: Root directory of the project
    CONFIG_DIR: Configuration files directory
    OUTPUT_DIR: Output files directory
    TEMP_DIR: Temporary files directory

Functions:
    load_config: Load and validate layer configuration from JSON
"""

import json
from pathlib import Path
from typing import Dict

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / 'config'
OUTPUT_DIR = PROJECT_ROOT / 'outputs'
TEMP_DIR = PROJECT_ROOT / 'temp'


def load_config() -> Dict:
    """
    Load layer configuration from JSON file.

    Reads the layers_config.json file and validates basic structure.

    Returns:
    --------
    Dict
        Configuration dictionary with 'layers' and 'settings' keys

    Raises:
    -------
    FileNotFoundError
        If configuration file doesn't exist
    json.JSONDecodeError
        If configuration file contains invalid JSON
    KeyError
        If required configuration keys are missing
    """
    config_path = CONFIG_DIR / 'layers_config.json'

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # Validate required keys
    if 'layers' not in config:
        raise KeyError("Configuration missing required 'layers' key")
    if 'settings' not in config:
        raise KeyError("Configuration missing required 'settings' key")

    # Ensure output directories exist
    OUTPUT_DIR.mkdir(exist_ok=True)
    TEMP_DIR.mkdir(exist_ok=True)

    return config


def load_geometry_settings(config: Dict = None) -> Dict:
    """
    Load geometry processing settings from configuration.

    Args:
        config: Configuration dictionary (optional, will load if not provided)

    Returns:
        Dictionary with geometry settings

    Defaults:
        - buffer_distance_feet: 500
        - buffer_point_geometries: True
        - buffer_line_geometries: True
        - auto_repair_invalid: True
        - fallback_crs: 'EPSG:5070'
        - clip_results_to_buffer: True
        - clip_buffer_miles: 1.0
        - state_filter_enabled: True

    Note:
        Returns defaults if 'geometry_settings' section is missing,
        ensuring backward compatibility with older config files.
    """
    if config is None:
        config = load_config()

    # Default geometry settings
    defaults = {
        'buffer_distance_feet': 500,
        'buffer_point_geometries': True,
        'buffer_line_geometries': True,
        'auto_repair_invalid': True,
        'fallback_crs': 'EPSG:5070',
        'clip_results_to_buffer': True,
        'clip_buffer_miles': 1.0,
        'state_filter_enabled': True,
        'max_input_area_sq_miles': 5000
    }

    # Get geometry_settings from config, or use defaults
    geometry_settings = config.get('geometry_settings', {})

    # Merge with defaults (config values override defaults)
    result = {**defaults, **geometry_settings}

    return result
