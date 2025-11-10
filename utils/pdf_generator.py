"""
PDF report generator for APPEIT Map Creator.

This module generates a PDF version of the PEIT report with:
    - Cover page with title and metadata
    - Body table with environmental layer data (4 columns)
    - End page with BMP resource links

The PDF includes clickable hyperlinks for all resource area codes.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

import geopandas as gpd
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS

# Get logger
logger = logging.getLogger(__name__)


def load_resource_areas(config_dir: Path) -> Dict[str, Dict[str, str]]:
    """
    Load resource area mappings from JSON file.

    Args:
        config_dir: Path to configuration directory

    Returns:
        Dictionary mapping resource area codes to data
        Example: {"1.4": {"name": "Water Resources", "url": "https://..."}}
    """
    resource_areas_file = config_dir / 'resource_areas.json'

    try:
        with open(resource_areas_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Convert list of dicts to code -> {name, URL} mapping
        mapping = {}
        for item in data:
            code = item['resource_area'].replace('Resource Area ', '')
            mapping[code] = {
                'name': item['name'],
                'url': item['url']
            }

        logger.debug(f"Loaded {len(mapping)} resource area mappings")
        return mapping

    except Exception as e:
        logger.error(f"Failed to load resource areas: {e}")
        return {}


def get_category_resource_areas() -> Dict[str, List[str]]:
    """
    Define mapping from category (group) to resource area codes.

    Returns:
        Dictionary mapping category names to lists of resource area codes
    """
    return {
        'EPA Programs': ['1.4', '1.9', '1.11'],
        'Federal/Tribal Land': ['1.7', '1.8'],
        'Historic Places': ['1.8'],
        'Floodplains/Wetlands': ['1.5'],
        'Infrastructure': ['1.1'],
        'Critical Habitats': ['1.6', '1.10']
    }


def prepare_table_rows(
    layer_results: Dict[str, gpd.GeoDataFrame],
    config: Dict,
    url_mapping: Dict[str, Dict[str, str]],
    category_resources: Dict[str, List[str]]
) -> List[Dict]:
    """
    Prepare table rows for PDF from layer results.

    Each row contains category, layer name, area name, and consolidated
    resource areas as list of {code, url} dicts.

    Args:
        layer_results: Dictionary mapping layer names to GeoDataFrames
        config: Configuration dictionary with layer definitions
        url_mapping: Resource area code to URL/name mapping
        category_resources: Category to resource area codes mapping

    Returns:
        List of row dictionaries ready for template rendering
    """
    rows = []
    layer_config_map = {layer['name']: layer for layer in config['layers']}

    for layer_name, gdf in layer_results.items():
        if gdf.empty:
            continue

        layer_config = layer_config_map.get(layer_name)
        if not layer_config:
            continue

        category = layer_config.get('group', 'Other')
        area_name_field = layer_config.get('area_name_field')

        if not area_name_field or area_name_field not in gdf.columns:
            continue

        # Get resource area codes for this category
        resource_codes = category_resources.get(category, [])

        # Build resource areas list with URLs
        resource_areas = []
        for code in resource_codes:
            if code in url_mapping:
                resource_areas.append({
                    'code': code,
                    'url': url_mapping[code]['url']
                })

        # Add one row per feature
        for idx, row in gdf.iterrows():
            area_name = row.get(area_name_field, 'N/A')

            if area_name is None or (isinstance(area_name, str) and not area_name.strip()):
                area_name = 'N/A'

            rows.append({
                'category': category,
                'layer_name': layer_name,
                'area_name': str(area_name),
                'resource_areas': resource_areas if resource_areas else None
            })

    return rows


def prepare_resource_links(url_mapping: Dict[str, Dict[str, str]]) -> List[Dict]:
    """
    Prepare resource area links for end page table.

    Args:
        url_mapping: Resource area code to URL/name mapping

    Returns:
        List of dicts with code, name, url for each resource area
    """
    links = []
    for code in sorted(url_mapping.keys(), key=lambda x: float(x)):
        links.append({
            'code': f'Resource Area {code}',
            'name': url_mapping[code]['name'],
            'url': url_mapping[code]['url']
        })
    return links


def generate_pdf_report(
    layer_results: Dict[str, gpd.GeoDataFrame],
    config: Dict,
    output_path: Path,
    timestamp: str,
    project_name: str = "",
    project_id: str = ""
) -> Optional[Path]:
    """
    Generate a PDF report summarizing intersected environmental features.

    Creates a PDF with:
        - Cover page with title and metadata
        - Body table (Category, Layer Name, Area Name, Resource Areas)
        - End page with BMP resource links

    All resource area codes are hyperlinked to NTIA documentation.

    Args:
        layer_results: Dictionary mapping layer names to GeoDataFrames
        config: Configuration dictionary with layer definitions
        output_path: Directory where report should be saved
        timestamp: Timestamp string for filename (YYYYMMDD_HHMMSS)
        project_name: Optional project name for cover page
        project_id: Optional project ID for cover page

    Returns:
        Path to generated PDF file, or None if generation fails
    """
    logger.info("Generating PDF report...")

    try:
        # Load resource area URL mappings
        config_dir = Path(__file__).parent.parent / 'config'
        url_mapping = load_resource_areas(config_dir)

        # Get category -> resource areas mapping
        category_resources = get_category_resource_areas()

        # Prepare table data
        table_rows = prepare_table_rows(
            layer_results,
            config,
            url_mapping,
            category_resources
        )

        # Prepare resource links for end page
        resource_links = prepare_resource_links(url_mapping)

        # Format timestamps
        # Parse timestamp string: "20250110_143022" -> datetime
        dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
        report_date = dt.strftime("%m/%d/%Y %H:%M:%S")

        # Prepare template context
        context = {
            'project_name': project_name or '—',
            'project_id': project_id or '—',
            'report_date': report_date,
            'table_rows': table_rows,
            'bmp_master_url': 'https://broadbandusa.ntia.gov/sites/default/files/2025-08/EHP_NTIA_BMPs_and_Mitigation_Measures_2025.pdf',
            'resource_area_links': resource_links
        }

        # Load Jinja2 template
        template_dir = Path(__file__).parent.parent / 'templates' / 'pdf_report'
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template('report_template.html')

        # Render HTML
        html_content = template.render(**context)

        # Load CSS
        css_path = template_dir / 'report.css'

        # Generate PDF
        filename = f"PEIT_Report_{timestamp}.pdf"
        pdf_path = output_path / filename

        HTML(string=html_content, base_url=str(template_dir)).write_pdf(
            pdf_path,
            stylesheets=[CSS(filename=str(css_path))]
        )

        logger.info(f"✓ PDF report saved: {filename} ({len(table_rows)} features)")

        return pdf_path

    except Exception as e:
        logger.error(f"Failed to generate PDF report: {e}", exc_info=True)
        return None
