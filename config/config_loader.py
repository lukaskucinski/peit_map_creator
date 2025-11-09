"""
Configuration loading for APPEIT Map Creator.

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
