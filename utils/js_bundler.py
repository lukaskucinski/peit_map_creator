"""
JavaScript bundling utilities for APPEIT Map Creator.

This module provides functions to load bundled JavaScript files for inline embedding
in generated HTML maps, eliminating external CDN dependencies.

Functions:
    get_leaflet_pattern_js: Load fixed leaflet.pattern.js for inline embedding
"""

from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent


def get_leaflet_pattern_js() -> str:
    """
    Load the fixed leaflet.pattern.js library for inline embedding.

    This version includes a fix for the L.Mixin.Events deprecation warning
    by using L.Evented.prototype || L.Mixin.Events for backward compatibility.

    Returns:
        str: Complete JavaScript code as a string

    Raises:
        FileNotFoundError: If the bundled JS file is not found
    """
    js_path = PROJECT_ROOT / 'static' / 'js' / 'leaflet.pattern.fixed.js'

    if not js_path.exists():
        raise FileNotFoundError(f"Bundled Leaflet.pattern JavaScript not found: {js_path}")

    return js_path.read_text(encoding='utf-8')
