"""
Output generation module for APPEIT Map Creator.

This module handles saving the generated map and data files to the output directory.
Creates a timestamped directory structure with HTML map, GeoJSON data files, and metadata.

Functions:
    generate_output: Save map, data files, and metadata to output directory
"""

import folium
import geopandas as gpd
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple
from config.config_loader import OUTPUT_DIR
from utils.logger import get_logger
from utils.xlsx_generator import generate_xlsx_report
from utils.pdf_generator import generate_pdf_report

logger = get_logger(__name__)


def generate_output(
    map_obj: folium.Map,
    polygon_gdf: gpd.GeoDataFrame,
    layer_results: Dict[str, gpd.GeoDataFrame],
    metadata: Dict[str, Dict],
    config: Dict,
    output_name: Optional[str] = None,
    input_geometry_metadata: Optional[Dict] = None
) -> Tuple[Path, Optional[str], Optional[str]]:
    """
    Generate output directory with HTML map, GeoJSON data files, XLSX and PDF reports.

    Creates a timestamped output directory containing:
    - index.html: Interactive Leaflet map
    - metadata.json: Summary statistics and query information
    - data/: GeoJSON files for input polygon and all layers
    - PEIT_Report_YYYYMMDD_HHMMSS.xlsx: Summary report with hyperlinked resource areas
    - PEIT_Report_YYYYMMDD_HHMMSS.pdf: PDF version with cover page and BMP links

    Parameters:
    -----------
    map_obj : folium.Map
        Folium map object to save
    polygon_gdf : gpd.GeoDataFrame
        Input polygon
    layer_results : Dict[str, gpd.GeoDataFrame]
        Dictionary of layer results (layer name -> GeoDataFrame)
    metadata : Dict[str, Dict]
        Layer metadata
    config : Dict
        Configuration dictionary with layer definitions
    output_name : Optional[str]
        Custom output directory name (defaults to timestamped name)

    Returns:
    --------
    Tuple[Path, Optional[str], Optional[str]]
        Tuple of (output_path, xlsx_relative_path, pdf_relative_path)
        - output_path: Path to output directory
        - xlsx_relative_path: Relative path to XLSX file, or None if generation failed
        - pdf_relative_path: Relative path to PDF file, or None if generation failed

    Example:
        >>> output_path, xlsx_file, pdf_file = generate_output(map_obj, polygon_gdf, results, metadata, config)
        >>> output_path
        Path('outputs/appeit_map_20250108_143022')
        >>> xlsx_file
        'PEIT_Report_20250108_143022.xlsx'
        >>> pdf_file
        'PEIT_Report_20250108_143022.pdf'
    """
    logger.info("=" * 80)
    logger.info("Generating Output Files")
    logger.info("=" * 80)

    # Create timestamped output directory
    if output_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"appeit_map_{timestamp}"
    else:
        # Extract timestamp from output_name (e.g., "appeit_map_20250110_143022" -> "20250110_143022")
        if "_" in output_name:
            timestamp = "_".join(output_name.split("_")[-2:])
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_path = OUTPUT_DIR / output_name
    output_path.mkdir(exist_ok=True)

    # Create data subdirectory
    data_path = output_path / 'data'
    data_path.mkdir(exist_ok=True)

    logger.info(f"Output directory: {output_path}")

    # Save input polygon
    logger.info("  - Saving input polygon...")
    polygon_file = data_path / 'input_polygon.geojson'
    polygon_gdf.to_file(polygon_file, driver='GeoJSON')

    # Save each layer's features
    for layer_name, gdf in layer_results.items():
        logger.info(f"  - Saving {layer_name} features...")
        # Sanitize filename
        safe_name = layer_name.replace(' ', '_').replace('/', '_').lower()
        layer_file = data_path / f'{safe_name}.geojson'
        gdf.to_file(layer_file, driver='GeoJSON')

    # Save map HTML
    logger.info("  - Saving interactive map...")
    map_file = output_path / 'index.html'
    map_obj.save(str(map_file))

    # Save metadata JSON
    logger.info("  - Saving metadata...")
    metadata_file = output_path / 'metadata.json'

    summary = {
        'generated_at': datetime.now().isoformat(),
        'input_polygon': {
            'bounds': polygon_gdf.total_bounds.tolist(),
            'crs': str(polygon_gdf.crs)
        },
        'layers': metadata,
        'total_features': sum(m['feature_count'] for m in metadata.values()),
        'layers_with_data': sum(1 for m in metadata.values() if m['feature_count'] > 0)
    }

    # Add input geometry metadata if provided (from new pipeline)
    if input_geometry_metadata:
        summary['input_geometry'] = input_geometry_metadata

    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    # Generate XLSX report
    logger.info("  - Generating XLSX report...")
    xlsx_path = generate_xlsx_report(layer_results, config, output_path, timestamp)

    # Get relative path for template linking (just the filename)
    xlsx_relative_path = None
    if xlsx_path:
        xlsx_relative_path = xlsx_path.name

    # Generate PDF report
    logger.info("  - Generating PDF report...")
    pdf_path = generate_pdf_report(layer_results, config, output_path, timestamp)

    # Get relative path for template linking (just the filename)
    pdf_relative_path = None
    if pdf_path:
        pdf_relative_path = pdf_path.name

    logger.info("")
    logger.info("=" * 80)
    logger.info("✓ Output Generation Complete")
    logger.info("=" * 80)
    logger.info(f"Files saved to: {output_path}")
    logger.info("  - index.html (interactive map)")
    logger.info("  - metadata.json (summary statistics)")
    logger.info(f"  - data/ ({len(layer_results) + 1} GeoJSON files)")
    if xlsx_relative_path:
        logger.info(f"  - {xlsx_relative_path} (PEIT report - XLSX)")
    if pdf_relative_path:
        logger.info(f"  - {pdf_relative_path} (PEIT report - PDF)")
    logger.info("")
    logger.info(f"To view the map, open: {map_file}")
    logger.info("=" * 80)

    return output_path, xlsx_relative_path, pdf_relative_path
