"""
PDF report generator for APPEIT Map Creator.

This module generates a PDF version of the PEIT report with:
    - Cover page with title and metadata
    - Body table with environmental layer data (4 columns)
    - End page with BMP resource links

The PDF includes clickable hyperlinks for all resource area codes.
Uses fpdf2 for pure Python PDF generation with automatic table header repetition.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

import geopandas as gpd
from fpdf import FPDF
from fpdf.fonts import FontFace
from fpdf.enums import TableCellFillMode

# Get logger
logger = logging.getLogger(__name__)


class ReportPDF(FPDF):
    """Custom PDF class with landscape orientation and page numbers."""

    def __init__(self):
        """Initialize PDF with landscape Letter orientation and custom margins."""
        super().__init__(orientation="landscape", format="letter")

        # Set margins: 0.5in left/right, 0.5in top (converted to mm) - reduced for more content
        self.set_margins(left=12.7, top=12.7, right=12.7)

        # Set metadata
        self.set_title("Permitting & Environmental Information (PEIT) Report")
        self.set_author("APPEIT Map Creator")
        self.set_subject("Environmental Layer Intersection Analysis")

        # Load Unicode fonts for special character support
        self._load_unicode_fonts()

        # Store total pages for footer (will be set before output)
        self.total_pages_excluding_cover = None

    def _load_unicode_fonts(self):
        """Load DejaVu Sans Unicode fonts for all styles to support special characters."""
        from pathlib import Path

        # Get project root directory
        project_root = Path(__file__).parent.parent
        fonts_dir = project_root / 'fonts'

        # Define font paths for all styles
        font_files = {
            '': 'DejaVuSans.ttf',              # Regular
            'B': 'DejaVuSans-Bold.ttf',         # Bold
            'I': 'DejaVuSans-Oblique.ttf',      # Italic
            'BI': 'DejaVuSans-BoldOblique.ttf'  # Bold Italic
        }

        # Load each font style
        for style, filename in font_files.items():
            font_path = fonts_dir / filename
            if font_path.exists():
                self.add_font(family='DejaVuSans', style=style, fname=str(font_path))
                logger.debug(f"Loaded font: DejaVuSans {style or 'Regular'} from {filename}")
            else:
                logger.warning(f"Font file not found: {font_path} - PDF may fail with Unicode characters")

    def footer(self):
        """Add gray page numbers to footer (skip cover page)."""
        # Skip footer on cover page (page 1)
        if self.page_no() > 1:
            self.set_y(-15)
            self.set_font("DejaVuSans", size=8)
            self.set_text_color(128, 128, 128)  # Gray
            # Format: "Page 2 of 24" (excluding cover page from both counts)
            page_num = self.page_no() - 1
            # Use stored total if available, otherwise show placeholder
            if self.total_pages_excluding_cover is not None:
                total_str = str(self.total_pages_excluding_cover)
            else:
                total_str = "..."  # Placeholder during first pass
            self.cell(0, 10, f"Page {page_num} of {total_str}", align="C")
            self.set_text_color(0, 0, 0)  # Reset to black


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


def create_cover_page(
    pdf: ReportPDF,
    project_name: str,
    project_id: str,
    report_date: str
) -> None:
    """
    Create cover page with title and metadata.

    Args:
        pdf: ReportPDF instance
        project_name: Project name for metadata
        project_id: Project ID for metadata
        report_date: Formatted report date string
    """
    pdf.add_page()

    # Title (18pt, bold, centered)
    pdf.set_font("DejaVuSans", style="B", size=18)
    pdf.ln(50)  # Space from top
    pdf.cell(
        0, 10,
        "Permitting & Environmental Information (PEIT) Report",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT"
    )

    pdf.ln(40)  # Spacing after title

    # Metadata section (10pt, centered)
    metadata_fields = [
        ("Project Name:", project_name or "-"),
        ("Project ID:", project_id or "-"),
        ("Report Date:", report_date),
    ]

    for label, value in metadata_fields:
        pdf.set_font("DejaVuSans", size=10)
        # Combine label and value, center the entire line
        combined_text = f"{label} {value}"
        pdf.cell(0, 6, combined_text, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)  # Spacing between rows


def render_table_header(
    pdf: ReportPDF,
    col_widths: tuple,
    row_height: int
) -> None:
    """
    Render table header row with black background and white text.

    Args:
        pdf: ReportPDF instance
        col_widths: Tuple of column widths (Category, Layer, Area, Resource)
        row_height: Height of header row
    """
    # Header styling
    pdf.set_font("DejaVuSans", style="B", size=10)
    pdf.set_fill_color(0, 0, 0)  # Black background
    pdf.set_text_color(255, 255, 255)  # White text

    # Header cells
    headers = ["Category", "Layer Name", "Area Name", "Resource Areas"]
    x_start = pdf.l_margin
    y_start = pdf.get_y()

    for i, (header, width) in enumerate(zip(headers, col_widths)):
        pdf.set_xy(x_start + sum(col_widths[:i]), y_start)
        pdf.cell(width, row_height, header, border=1, fill=True, align="L")

    pdf.ln(row_height)
    pdf.set_text_color(0, 0, 0)  # Reset to black


def render_table_row(
    pdf: ReportPDF,
    row_data: Dict,
    col_widths: tuple,
    row_height: int,
    url_mapping: Dict,
    category_resources: Dict,
    row_index: int
) -> None:
    """
    Render a single table row with markdown hyperlinks in Resource Areas column.

    Args:
        pdf: ReportPDF instance
        row_data: Dict with 'category', 'layer_name', 'area_name'
        col_widths: Column widths
        row_height: Row height
        url_mapping: Resource area code -> URL mapping
        category_resources: Category -> resource codes mapping
        row_index: Row number for alternating colors
    """
    # Alternating row colors
    if row_index % 2 == 0:
        pdf.set_fill_color(249, 249, 249)  # Light gray
    else:
        pdf.set_fill_color(255, 255, 255)  # White

    # Get data
    category = row_data['category']
    layer_name = row_data['layer_name']
    area_name = row_data['area_name']
    resource_codes = category_resources.get(category, [])

    # Row starting position
    x_start = pdf.l_margin
    y_start = pdf.get_y()

    # Font for regular cells
    pdf.set_font("DejaVuSans", style="B", size=10)

    # Helper function to truncate text if it exceeds column width
    def truncate_text(text, width):
        """Truncate text to fit within column width."""
        max_chars = int(width / 2.5)  # Approximate chars that fit
        if len(text) > max_chars:
            return text[:max_chars-3] + "..."
        return text

    # Column 1: Category (truncated if needed)
    pdf.set_xy(x_start, y_start)
    pdf.cell(col_widths[0], row_height, truncate_text(category, col_widths[0]), border=1, fill=True)

    # Column 2: Layer Name (truncated if needed)
    pdf.set_xy(x_start + col_widths[0], y_start)
    pdf.cell(col_widths[1], row_height, truncate_text(layer_name, col_widths[1]), border=1, fill=True)

    # Column 3: Area Name (truncated if needed)
    pdf.set_xy(x_start + col_widths[0] + col_widths[1], y_start)
    pdf.cell(col_widths[2], row_height, truncate_text(area_name, col_widths[2]), border=1, fill=True)

    # Column 4: Resource Areas (markdown links)
    pdf.set_xy(x_start + col_widths[0] + col_widths[1] + col_widths[2], y_start)

    if resource_codes:
        # Build markdown links: [1.4](url1), [1.9](url2), [1.11](url3)
        links = []
        for code in resource_codes:
            url = url_mapping.get(code, {}).get('url', '')
            if url:
                links.append(f"[{code}]({url})")
            else:
                links.append(code)  # Plain text if no URL

        resource_text = ", ".join(links)

        # Set link color to blue and enable markdown
        pdf.set_text_color(0, 0, 255)  # Blue

        # Use multi_cell with markdown for clickable links
        pdf.multi_cell(
            col_widths[3],
            row_height,
            resource_text,
            border=1,
            fill=True,
            markdown=True,
            align="L"
        )

        # Reset text color
        pdf.set_text_color(0, 0, 0)
    else:
        # No resource areas
        pdf.cell(col_widths[3], row_height, "-", border=1, fill=True)
        pdf.ln(row_height)


def create_body_table(
    pdf: ReportPDF,
    table_rows: List[Dict],
    url_mapping: Dict[str, Dict[str, str]],
    category_resources: Dict[str, List[str]]
) -> None:
    """
    Create main data table with manually rendered rows and markdown hyperlinks.

    Automatically adapts to any number of rows (10 to 10,000+).
    Handles page breaks and header repetition automatically.

    Args:
        pdf: ReportPDF instance
        table_rows: List of row dictionaries with category, layer_name, area_name
        url_mapping: Resource area code to URL/name mapping
        category_resources: Category to resource area codes mapping
    """
    pdf.add_page()

    # Table configuration
    col_widths = (60, 80, 70, 50)  # Category, Layer, Area, Resource
    row_height = 7
    page_bottom_margin = 15  # Space to leave at bottom for footer (reduced for more rows)

    # Set body font
    pdf.set_font("DejaVuSans", style="B", size=10)

    # Render initial header
    render_table_header(pdf, col_widths, row_height)

    # Render data rows (automatically handles ANY number of rows)
    for i, row_data in enumerate(table_rows):
        # Check if we need a page break
        if pdf.will_page_break(row_height + page_bottom_margin):
            pdf.add_page()
            render_table_header(pdf, col_widths, row_height)

        # Render row
        render_table_row(
            pdf,
            row_data,
            col_widths,
            row_height,
            url_mapping,
            category_resources,
            i
        )


def create_bmp_end_page(
    pdf: ReportPDF,
    resource_links: List[Dict],
    bmp_master_url: str
) -> None:
    """
    Create BMP end page with resource links table.

    Args:
        pdf: ReportPDF instance
        resource_links: List of dicts with code, name, url for each resource area
        bmp_master_url: URL to master BMP document
    """
    pdf.add_page()

    # Section title (14pt, bold, centered)
    pdf.set_font("DejaVuSans", style="B", size=14)
    pdf.ln(10)
    pdf.cell(0, 10, "Best Management Practices (BMP) Resource Links", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Master BMP URL (centered, clickable)
    pdf.set_font("DejaVuSans", style="U", size=10)
    pdf.set_text_color(0, 0, 255)  # Blue

    # Center the link
    link_width = pdf.get_string_width(bmp_master_url)
    x_position = (pdf.w - link_width) / 2
    pdf.set_x(x_position)
    pdf.cell(link_width, 6, bmp_master_url, link=bmp_master_url, align="C", new_x="LMARGIN", new_y="NEXT")

    # Reset text color
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)

    # Resource table header styling
    headings_style = FontFace(
        emphasis="BOLD",
        color=(255, 255, 255),
        fill_color=(0, 0, 0)
    )

    # Create resource table
    with pdf.table(
        headings_style=headings_style,
        cell_fill_color=(249, 249, 249),
        cell_fill_mode=TableCellFillMode.ROWS,
        col_widths=(45, 90, 125),  # Resource Area, Name, URL
        borders_layout="SINGLE_TOP_LINE",
        line_height=6,
        repeat_headings=1,
        text_align=("LEFT", "LEFT", "LEFT"),
    ) as table:
        # Header
        header = table.row()
        header.cell("Resource Area")
        header.cell("Resource Area Name")
        header.cell("URL")

        # Data rows (each resource area gets individual hyperlink)
        for link in resource_links:
            row = table.row()
            row.cell(link['code'])
            row.cell(link['name'])
            # Make entire URL cell clickable with blue color
            pdf.set_text_color(0, 0, 255)  # Blue
            row.cell(link['url'], link=link['url'])
            pdf.set_text_color(0, 0, 0)  # Reset to black


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


def prepare_table_rows(
    layer_results: Dict[str, gpd.GeoDataFrame],
    config: Dict,
    category_resources: Dict[str, List[str]]
) -> List[Dict]:
    """
    Prepare table rows for PDF from layer results.

    Each row contains category, layer name, and area name.
    Resource areas are determined by category mapping.

    Args:
        layer_results: Dictionary mapping layer names to GeoDataFrames
        config: Configuration dictionary with layer definitions
        category_resources: Category to resource area codes mapping

    Returns:
        List of row dictionaries ready for rendering
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

        # Add one row per feature
        for idx, row in gdf.iterrows():
            area_name = row.get(area_name_field, 'N/A')

            if area_name is None or (isinstance(area_name, str) and not area_name.strip()):
                area_name = 'N/A'

            # Check if layer uses unique value symbology
            layer_display_name = layer_name
            if 'symbology' in layer_config and layer_config['symbology'].get('type') == 'unique_values':
                symbology = layer_config['symbology']
                field = symbology['field']
                attr_value = row.get(field)

                # Find category label (case-insensitive)
                category_label = None
                if attr_value is not None:
                    for sym_category in symbology['categories']:
                        if any(str(attr_value).upper() == str(v).upper() for v in sym_category['values']):
                            category_label = sym_category['label']
                            break

                # If not matched, check default category
                if not category_label and 'default_category' in symbology:
                    category_label = symbology['default_category']['label']

                # Append category label to layer name
                if category_label:
                    layer_display_name = f"{layer_name} ({category_label})"
                else:
                    layer_display_name = f"{layer_name} (Unclassified)"

            rows.append({
                'category': category,
                'layer_name': layer_display_name,
                'area_name': str(area_name)
            })

    return rows


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

    All resource area codes in BMP table are hyperlinked to NTIA documentation.

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
            category_resources
        )

        # Prepare resource links for end page
        resource_links = prepare_resource_links(url_mapping)

        # Format timestamps
        dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
        report_date = dt.strftime("%m/%d/%Y %H:%M:%S")

        # Create PDF
        pdf = ReportPDF()

        # Cover page
        create_cover_page(pdf, project_name, project_id, report_date)

        # Body table (automatically handles page breaks and header repetition)
        create_body_table(pdf, table_rows, url_mapping, category_resources)

        # BMP end page
        bmp_master_url = 'https://broadbandusa.ntia.gov/sites/default/files/2025-08/EHP_NTIA_BMPs_and_Mitigation_Measures_2025.pdf'
        create_bmp_end_page(pdf, resource_links, bmp_master_url)

        # Calculate total pages excluding cover page
        total_pages = pdf.page_no()
        total_pages_excluding_cover = total_pages - 1

        # Set the total in the PDF object (this will be used by footer on re-render)
        pdf.total_pages_excluding_cover = total_pages_excluding_cover

        # Re-create the PDF with the known total
        # We need to rebuild because footers are already rendered with placeholder
        pdf2 = ReportPDF()
        pdf2.total_pages_excluding_cover = total_pages_excluding_cover

        # Rebuild all pages with correct total
        create_cover_page(pdf2, project_name, project_id, report_date)
        create_body_table(pdf2, table_rows, url_mapping, category_resources)
        create_bmp_end_page(pdf2, resource_links, bmp_master_url)

        # Save PDF
        filename = f"PEIT_Report_{timestamp}.pdf"
        pdf_path = output_path / filename
        pdf2.output(str(pdf_path))

        logger.info(f"✓ PDF report saved: {filename} ({len(table_rows)} features)")

        return pdf_path

    except Exception as e:
        logger.error(f"Failed to generate PDF report: {e}", exc_info=True)
        return None
