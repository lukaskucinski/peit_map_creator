# PEIT Map Creator

A powerful geospatial tool that replicates NTIA's APPEIT (ArcGIS Pro Permitting and Environmental Information Tool) functionality without requiring an ArcGIS Pro license. Query ESRI-hosted FeatureServer REST APIs and generate interactive web maps showing environmental features that intersect with your project area.

## Live Demo

**[peit-map-creator.com](https://peit-map-creator.com)** - Try the web version instantly, no installation required.

## Features

### Core Capabilities
- **No ArcGIS License Required** - Direct REST API queries to ESRI FeatureServers
- **Multiple Input Formats** - Supports Shapefile, KML, KMZ, GeoPackage, GeoJSON, and FileGDB
- **All Geometry Types** - Points, lines, and polygons with automatic buffering for non-polygon inputs
- **Draw Your Own** - Interactive map drawing tool to create custom project areas
- **Smart Query Optimization** - Automatic polygon vs envelope query selection based on geometry characteristics
- **State-Based Filtering** - Only queries relevant layers based on which states your geometry intersects

### Interactive Maps
- **Leaflet-Based** - Fast, responsive web maps that work offline
- **Multiple Base Maps** - Street, Light, Dark, and Satellite imagery options
- **Marker Clustering** - Automatic clustering for large point datasets
- **Dual Panel UI** - Left panel (legend/about) and right panel (layer controls)
- **Search Functionality** - Filter layers by name, description, or group
- **Right-Click Coordinates** - Google Maps-style coordinate copy

### Reports & Downloads
- **PDF Reports** - Professional formatted reports with hyperlinked resource areas
- **Excel Reports** - Tabular data export for analysis
- **GeoJSON Export** - Individual layer files
- **Shapefile Export** - Browser-based conversion
- **KMZ Export** - Google Earth compatible format
- **Bulk Download** - ZIP file with all outputs

### Advanced Features
- **Unique Value Symbology** - Attribute-based styling for categorized features
- **Pattern Fills** - Hatched/striped polygon fills matching ArcGIS Pro symbology
- **Result Clipping** - Clip features to configurable buffer distance
- **Geometry Simplification** - Automatic simplification for complex polygons

## Deployment Options

### 1. Web Application (Recommended)

The easiest way to use PEIT Map Creator:

1. Visit **[peit-map-creator.com](https://peit-map-creator.com)**
2. Upload a geospatial file or draw your project area
3. Configure buffer distance and project details
4. Process and receive your interactive map with reports

**Web Features:**
- User accounts with map history
- Shareable map URLs (7-day retention)
- Real-time processing status via SSE
- Rate limiting: 20 runs/day per user

### 2. Local CLI

Run the tool locally for unlimited processing:

```bash
# Clone repository
git clone https://github.com/lukaskucinski/peit_map_creator.git
cd peit_map_creator

# Create conda environment
conda create -n peit python=3.12
conda activate peit

# Install dependencies
pip install -r requirements.txt

# Run with your input file
python peit_map_creator.py
```

Edit `peit_map_creator.py` to specify your input file:
```python
if __name__ == "__main__":
    INPUT_FILE = r"path/to/your/polygon.gpkg"
    output_dir = main(INPUT_FILE)
```

## Architecture

```
peit_map_creator/
├── peit_map_creator.py          # CLI entry point
├── modal_app.py                 # Modal.com serverless backend
│
├── peit-app-homepage/           # Next.js web frontend
│   ├── app/                     # App Router pages
│   ├── components/              # React components
│   └── lib/                     # API client and utilities
│
├── config/
│   └── layers_config.json       # Layer definitions and settings
│
├── geometry_input/              # Geometry processing pipeline
│   ├── load_input.py            # File loading and type detection
│   ├── dissolve.py              # Geometry merging and repair
│   ├── buffering.py             # CRS projection and buffering
│   ├── pipeline.py              # Workflow orchestration
│   └── clipping.py              # Result geometry clipping
│
├── core/
│   ├── arcgis_query.py          # FeatureServer queries
│   ├── layer_processor.py       # Batch layer processing
│   ├── map_builder.py           # Folium map generation
│   └── output_generator.py      # File output handling
│
├── utils/
│   ├── logger.py                # Dual-output logging
│   ├── geometry_converters.py   # ESRI JSON to GeoJSON
│   ├── pdf_generator.py         # PDF report generation
│   ├── xlsx_generator.py        # Excel report generation
│   └── ...                      # Additional utilities
│
├── templates/                   # Jinja2 HTML templates
├── static/                      # Bundled JavaScript
├── fonts/                       # DejaVu fonts for PDF Unicode
└── outputs/                     # Generated maps and data
```

## Configuration

### Layer Configuration

Layers are defined in `config/layers_config.json`. Example layer entry:

```json
{
  "name": "RCRA Sites",
  "enabled": true,
  "url": "https://services.arcgis.com/.../FeatureServer",
  "layer_id": 0,
  "color": "#FF0000",
  "icon": "recycle",
  "icon_color": "red",
  "description": "Resource Conservation and Recovery Act facilities",
  "geometry_type": "point",
  "group": "EPA Programs",
  "area_name_field": "FACILITY_NAME",
  "states": ["Vermont", "New Hampshire"]
}
```

### Geometry Settings

Configure processing behavior in the `geometry_settings` section:

```json
{
  "geometry_settings": {
    "buffer_distance_feet": 500,
    "buffer_point_geometries": true,
    "buffer_line_geometries": true,
    "clip_results_to_buffer": true,
    "clip_buffer_miles": 1.0,
    "state_filter_enabled": true,
    "polygon_query_enabled": true,
    "polygon_query_max_vertices": 1000,
    "max_input_area_sq_miles": 5000
  }
}
```

### Adding New Layers

1. Find the ArcGIS FeatureServer REST API URL
2. Test in browser: `{url}/0/query?where=1=1&f=json`
3. Add entry to `layers_config.json` with appropriate configuration
4. No code changes required

## Output

Each run creates a timestamped directory:

```
outputs/peit_map_20250122_143022/
├── index.html                      # Interactive map
├── metadata.json                   # Processing statistics
├── PEIT_Report_20250122_143022.pdf # PDF report
├── PEIT_Report_20250122_143022.xlsx# Excel report
└── data/
    ├── input_polygon.geojson
    ├── rcra_sites.geojson
    └── ...
```

## Technology Stack

### Backend
- **Python 3.12** with GeoPandas, Shapely, Folium
- **Modal.com** for serverless processing
- **FastAPI** with SSE for real-time progress

### Frontend
- **Next.js 16** with App Router
- **Tailwind CSS** + shadcn/ui
- **Supabase** for authentication
- **Vercel** for hosting and blob storage

### Key Libraries
- `geopandas` - Geospatial data processing
- `folium` - Leaflet map generation
- `fpdf2` - PDF report generation
- `openpyxl` - Excel report generation
- `@geoman-io/leaflet-geoman-free` - Map drawing tools

## Known Limitations

1. **Server Feature Limits** - Most FeatureServers return max 1000-2000 features
2. **Internet Required** - No offline mode for FeatureServer queries
3. **Area Limits** - Web version limited to 5,000 sq mi input areas
4. **Data Retention** - Web-generated maps expire after 7 days

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is open source and available under the MIT License.

## Acknowledgments

- **NTIA** - Original APPEIT tool concept and layer definitions
- **ESRI** - Public FeatureServer REST APIs
- **Folium** - Python-to-Leaflet mapping
- **GeoPandas** - Geospatial data processing

## Links

- **Web App**: [peit-map-creator.com](https://peit-map-creator.com)
- **GitHub**: [github.com/lukaskucinski/peit_map_creator](https://github.com/lukaskucinski/peit_map_creator)
- **Issues**: [GitHub Issues](https://github.com/lukaskucinski/peit_map_creator/issues)
- **Support**: [Buy Me a Coffee](https://buymeacoffee.com/kucimaps)

## References

- [NTIA NBAM APPEIT](https://nbam.ntia.gov/content/37fa42c6313e4bdb9d8a9c05d2624891/about)
- [ArcGIS REST API Documentation](https://developers.arcgis.com/rest/)
- [Folium Documentation](https://python-visualization.github.io/folium/)
- [GeoPandas Documentation](https://geopandas.org/)