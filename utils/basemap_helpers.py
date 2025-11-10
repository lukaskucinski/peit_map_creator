"""
Basemap utility functions for generating basemap controls.

This module provides functions to:
- Encode thumbnail images as Base64 data URIs
- Generate basemap configuration with embedded thumbnails
"""

import base64
from pathlib import Path
from typing import List, Dict
from utils.logger import get_logger

logger = get_logger(__name__)


def encode_image_to_base64(image_path: Path) -> str:
    """
    Convert image file to base64 data URI.

    Args:
        image_path: Path to the image file

    Returns:
        Data URI string (e.g., "data:image/jpeg;base64,...")

    Raises:
        FileNotFoundError: If image file doesn't exist
        IOError: If image cannot be read
    """
    if not image_path.exists():
        raise FileNotFoundError(f"Thumbnail image not found: {image_path}")

    try:
        with open(image_path, 'rb') as img_file:
            encoded = base64.b64encode(img_file.read()).decode('utf-8')

        # Detect MIME type from extension
        ext = image_path.suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        mime = mime_types.get(ext, 'image/jpeg')

        return f"data:{mime};base64,{encoded}"

    except Exception as e:
        logger.error(f"Failed to encode image {image_path}: {e}")
        raise IOError(f"Cannot read image file: {image_path}") from e


def get_basemap_config() -> List[Dict]:
    """
    Generate basemap configuration with embedded thumbnails.

    Returns list of basemap dictionaries containing:
    - display_name: Human-friendly name for UI
    - tile_name: Folium tile layer identifier
    - tile_url: Leaflet tile URL template
    - thumbnail: Base64-encoded data URI for thumbnail image
    - thumbnail_file: Original filename (for reference)

    Returns:
        List of basemap configuration dictionaries
    """
    # Get path to thumbnail images directory
    images_dir = Path(__file__).parent.parent / 'images' / 'basemap_thumbnails'

    # Define basemap configurations - 4 basemaps matching available thumbnails
    # Order matches the order they will appear in the UI
    basemaps = [
        {
            'display_name': 'Satellite Imagery',
            'tile_name': 'Esri WorldImagery',
            'tile_url': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            'attribution': 'Tiles &copy; Esri',
            'thumbnail_file': 'satellite_canvas.jpeg'
        },
        {
            'display_name': 'Street Map',
            'tile_name': 'OpenStreetMap',
            'tile_url': 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            'attribution': '&copy; <a href=\'https://www.openstreetmap.org/copyright\'>OpenStreetMap</a> contributors',
            'thumbnail_file': 'street_map_canvas.jpg'
        },
        {
            'display_name': 'Dark Gray Canvas',
            'tile_name': 'CartoDB dark_matter',
            'tile_url': 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
            'attribution': '&copy; <a href=\'https://www.openstreetmap.org/copyright\'>OpenStreetMap</a> contributors &copy; <a href=\'https://carto.com/attributions\'>CARTO</a>',
            'thumbnail_file': 'dark_them_canvas.png'  # Note: typo in original filename
        },
        {
            'display_name': 'Light Gray Canvas',
            'tile_name': 'CartoDB positron',
            'tile_url': 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
            'attribution': '&copy; <a href=\'https://www.openstreetmap.org/copyright\'>OpenStreetMap</a> contributors &copy; <a href=\'https://carto.com/attributions\'>CARTO</a>',
            'thumbnail_file': 'light_gray_canvas.jpg'
        }
    ]

    # Encode thumbnails as base64 data URIs
    for basemap in basemaps:
        thumbnail_path = images_dir / basemap['thumbnail_file']
        try:
            basemap['thumbnail'] = encode_image_to_base64(thumbnail_path)
            logger.debug(f"Encoded thumbnail for {basemap['display_name']}: {basemap['thumbnail_file']}")
        except (FileNotFoundError, IOError) as e:
            logger.warning(f"Could not load thumbnail for {basemap['display_name']}: {e}")
            # Use a placeholder or skip this basemap
            # For now, use a simple grey placeholder data URI
            basemap['thumbnail'] = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iODAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHJlY3Qgd2lkdGg9IjgwIiBoZWlnaHQ9IjYwIiBmaWxsPSIjY2NjIi8+PC9zdmc+'

    return basemaps
