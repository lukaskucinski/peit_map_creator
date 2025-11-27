"""
Geometry Input Processing Package

This package provides enhanced geometry processing capabilities for APPEIT Map Creator,
supporting points, lines, and polygons with automatic buffering and CRS standardization.

Modules:
    load_input: Read geospatial files and detect geometry types
    dissolve: Unify multi-part geometries and repair invalid geometries
    buffering: Buffer point/line geometries in projected CRS, return EPSG:4326
    pipeline: Orchestrate complete geometry processing workflow
    clipping: Clip query result geometries to buffer boundary

Usage:
    from geometry_input.pipeline import process_input_geometry
    from geometry_input.clipping import create_clip_boundary, clip_geodataframe

    polygon_gdf = process_input_geometry(
        file_path='path/to/input.gpkg',
        buffer_distance_feet=500
    )
"""

from geometry_input.pipeline import process_input_geometry
from geometry_input.clipping import (
    create_clip_boundary,
    clip_geodataframe,
    aggregate_clip_metadata
)

__all__ = [
    'process_input_geometry',
    'create_clip_boundary',
    'clip_geodataframe',
    'aggregate_clip_metadata'
]
