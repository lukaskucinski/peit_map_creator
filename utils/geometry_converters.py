"""
Geometry conversion utilities for APPEIT Map Creator.

This module provides functions to convert ESRI JSON geometry formats to GeoJSON.
ArcGIS FeatureServers return geometries in ESRI JSON format, which needs to be
converted to standard GeoJSON for use with GeoPandas and Folium.

Functions:
    convert_esri_point: Convert ESRI point geometry to GeoJSON
    convert_esri_linestring: Convert ESRI paths to GeoJSON LineString
    convert_esri_polygon: Convert ESRI rings to GeoJSON Polygon
    convert_esri_to_geojson: Main dispatcher for ESRI to GeoJSON conversion
"""

from typing import Dict, Optional


def convert_esri_point(geom: Dict, props: Dict) -> Optional[Dict]:
    """
    Convert ESRI point geometry to GeoJSON Feature.

    Parameters:
    -----------
    geom : Dict
        ESRI geometry with 'x' and 'y' keys
    props : Dict
        Feature attributes/properties

    Returns:
    --------
    Optional[Dict]
        GeoJSON Feature dict or None if conversion fails

    Example:
        >>> geom = {'x': -73.9857, 'y': 40.7484}
        >>> props = {'name': 'New York'}
        >>> convert_esri_point(geom, props)
        {'type': 'Feature', 'geometry': {...}, 'properties': {...}}
    """
    if not geom or 'x' not in geom or 'y' not in geom:
        return None

    return {
        'type': 'Feature',
        'geometry': {
            'type': 'Point',
            'coordinates': [geom['x'], geom['y']]
        },
        'properties': props
    }


def convert_esri_linestring(geom: Dict, props: Dict) -> Optional[Dict]:
    """
    Convert ESRI paths geometry to GeoJSON LineString or MultiLineString.

    ESRI represents polylines as arrays of paths, where each path is an array
    of coordinate pairs. Single path becomes LineString, multiple paths become
    MultiLineString.

    Parameters:
    -----------
    geom : Dict
        ESRI geometry with 'paths' key
    props : Dict
        Feature attributes/properties

    Returns:
    --------
    Optional[Dict]
        GeoJSON Feature dict or None if conversion fails
    """
    if not geom or 'paths' not in geom or not geom['paths']:
        return None

    # Single path = LineString, multiple paths = MultiLineString
    if len(geom['paths']) == 1:
        coords = geom['paths'][0]
        geom_type = 'LineString'
    else:
        coords = geom['paths']
        geom_type = 'MultiLineString'

    return {
        'type': 'Feature',
        'geometry': {
            'type': geom_type,
            'coordinates': coords
        },
        'properties': props
    }


def convert_esri_polygon(geom: Dict, props: Dict) -> Optional[Dict]:
    """
    Convert ESRI rings geometry to GeoJSON Polygon.

    ESRI represents polygons as arrays of rings, where each ring is an array
    of coordinate pairs. The first ring is the exterior, subsequent rings are holes.

    Parameters:
    -----------
    geom : Dict
        ESRI geometry with 'rings' key
    props : Dict
        Feature attributes/properties

    Returns:
    --------
    Optional[Dict]
        GeoJSON Feature dict or None if conversion fails
    """
    if not geom or 'rings' not in geom or not geom['rings']:
        return None

    return {
        'type': 'Feature',
        'geometry': {
            'type': 'Polygon',
            'coordinates': geom['rings']
        },
        'properties': props
    }


def convert_esri_to_geojson(esri_feature: Dict) -> Optional[Dict]:
    """
    Main converter dispatcher for ESRI JSON to GeoJSON.

    Detects the geometry type and calls the appropriate conversion function.

    Parameters:
    -----------
    esri_feature : Dict
        ESRI JSON feature with 'geometry' and 'attributes' keys

    Returns:
    --------
    Optional[Dict]
        GeoJSON Feature dict or None if conversion fails

    Example:
        >>> esri_feature = {
        ...     'geometry': {'x': -73.9857, 'y': 40.7484},
        ...     'attributes': {'name': 'New York', 'population': 8000000}
        ... }
        >>> convert_esri_to_geojson(esri_feature)
        {'type': 'Feature', 'geometry': {...}, 'properties': {...}}
    """
    geom = esri_feature.get('geometry')
    props = esri_feature.get('attributes', {})

    if not geom:
        return None

    # Detect geometry type by structure
    if 'x' in geom and 'y' in geom:
        # Point geometry
        return convert_esri_point(geom, props)
    elif 'paths' in geom:
        # LineString/MultiLineString geometry
        return convert_esri_linestring(geom, props)
    elif 'rings' in geom:
        # Polygon geometry
        return convert_esri_polygon(geom, props)

    # Unknown geometry type
    return None
