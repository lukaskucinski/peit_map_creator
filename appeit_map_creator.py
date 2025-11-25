#!/usr/bin/env python
"""
APPEIT Map Creator
==================
A Python tool to replicate NTIA's APPEIT functionality by querying ArcGIS FeatureServers
and generating interactive Leaflet web maps showing environmental layer intersections.

Author: Lukas Kucinski
Repository: https://github.com/lukaskucinski/appeit_map_creator.git
License: MIT
"""

from pathlib import Path
from typing import Optional
import warnings
import time

# Import logging first
from utils.logger import setup_logging, get_logger

# Import configuration
from config.config_loader import load_config, load_geometry_settings

# Import core modules
from core.layer_processor import process_all_layers
from core.map_builder import create_web_map
from core.output_generator import generate_output

# Try to import new geometry processing pipeline, fallback to legacy input_reader
try:
    from geometry_input.pipeline import process_input_geometry
    USE_NEW_PIPELINE = True
except ImportError:
    from core.input_reader import read_input_polygon
    USE_NEW_PIPELINE = False

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')


def main(input_file: str, output_name: Optional[str] = None) -> Optional[Path]:
    """
    Main execution workflow for APPEIT Map Creator.

    Orchestrates the complete workflow from reading input polygons to generating
    the final interactive map and data files.

    Workflow Steps:
    1. Setup logging to console and file
    2. Load configuration
    3. Read and reproject input polygon
    4. Query all FeatureServer layers
    5. Create interactive web map
    6. Generate output files

    Parameters:
    -----------
    input_file : str
        Path to input polygon file (supports .shp, .kml, .gpkg, .geojson, .gdb)
    output_name : Optional[str]
        Custom name for output directory (defaults to timestamped name)

    Returns:
    --------
    Optional[Path]
        Path to output directory if successful, None if failed

    Example:
        >>> output_path = main('project_area.gpkg')
        >>> print(f"Map saved to: {output_path / 'index.html'}")
    """
    # Start overall execution timer
    workflow_start_time = time.time()

    # Setup logging - returns log file path
    log_file = setup_logging()
    logger = get_logger(__name__)

    logger.info("=" * 80)
    logger.info("APPEIT MAP CREATOR - Environmental Layer Intersection Tool")
    logger.info("=" * 80)
    logger.info(f"Log file: {log_file}")
    logger.info("")

    try:
        # Load configuration
        config = load_config()
        logger.info(f"Configuration loaded: {len(config['layers'])} layers defined")
        logger.info("")

        # Step 1: Read input polygon (use new pipeline if available)
        input_geometry_metadata = {}

        if USE_NEW_PIPELINE:
            logger.info("Using enhanced geometry processing pipeline")
            geometry_settings = load_geometry_settings(config)
            polygon_gdf, input_geometry_metadata = process_input_geometry(
                input_file,
                buffer_distance_feet=geometry_settings['buffer_distance_feet']
            )
        else:
            logger.info("Using legacy input reader")
            from core.input_reader import read_input_polygon
            polygon_gdf = read_input_polygon(input_file)

        input_filename = Path(input_file).stem

        # Step 2: Process all layers
        layer_results, metadata = process_all_layers(polygon_gdf, config)

        # Check if any results found
        if not layer_results:
            logger.warning("⚠ WARNING: No intersecting features found in any layer.")
            logger.warning("The output map will only show the input polygon.")
            logger.info("")

        # Generate timestamp for consistent naming across map, xlsx, and pdf
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        xlsx_filename = f"PEIT_Report_{timestamp}.xlsx"
        pdf_filename = f"PEIT_Report_{timestamp}.pdf"

        # Step 3: Create web map (with XLSX and PDF filenames for About section links)
        map_obj = create_web_map(
            polygon_gdf, layer_results, metadata, config, input_filename,
            xlsx_relative_path=xlsx_filename,
            pdf_relative_path=pdf_filename
        )

        # Calculate total execution time (before generate_output so it's included in metadata.json)
        total_execution_time = time.time() - workflow_start_time

        # Add execution time to layer metadata (will be saved to metadata.json)
        # Note: This goes into the 'layers' section of metadata, but we'll add a top-level one too
        metadata['_execution_time'] = {
            'total_seconds': total_execution_time,
            'formatted': f"{total_execution_time:.2f} seconds"
        }

        # Step 4: Generate output (uses same timestamp)
        if output_name is None:
            output_name = f"appeit_map_{timestamp}"

        output_path, xlsx_file, pdf_file = generate_output(
            map_obj, polygon_gdf, layer_results, metadata, config, output_name,
            input_geometry_metadata=input_geometry_metadata
        )

        logger.info("")
        logger.info("✓ WORKFLOW COMPLETE")
        logger.info(f"✓ Total execution time: {total_execution_time:.2f} seconds")
        logger.info(f"✓ Output directory: {output_path}")
        logger.info(f"✓ Log file: {log_file}")
        logger.info("")

        return output_path

    except Exception as e:
        # Calculate elapsed time for error reporting
        elapsed_time = time.time() - workflow_start_time

        logger.error("")
        logger.error("=" * 80)
        logger.error("✗ WORKFLOW FAILED")
        logger.error("=" * 80)
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Workflow failed after {elapsed_time:.2f} seconds")
        logger.error("")
        logger.error(f"See log file for details: {log_file}")
        logger.error("=" * 80)
        return None


if __name__ == "__main__":
    # Example: Process the Vermont Project Area (PA) test file
    INPUT_FILE = r"C:\Users\lukas\Downloads\peit_testing_inputs\pa045_mpb.gpkg"

    # Run the workflow
    output_dir = main(INPUT_FILE)

    if output_dir:
        print(f"\n✓ Success! Open {output_dir / 'index.html'} in your browser.")
    else:
        print("\n✗ Failed to generate map. Check log file for details.")
