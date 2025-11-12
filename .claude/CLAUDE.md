# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

APPEIT Map Creator replicates NTIA's APPEIT tool functionality without requiring an ArcGIS Pro license. It queries ESRI-hosted FeatureServer REST APIs and generates interactive Leaflet web maps showing environmental features that intersect with user-provided geometries.

## Architecture

### Project Structure

```
appeit_map_creator/
├── appeit_map_creator.py          # Main entry point
├── config/
│   ├── config_loader.py           # Configuration loading & validation
│   └── layers_config.json         # Layer definitions and settings
├── geometry_input/                # Enhanced geometry processing
│   ├── load_input.py              # Load files, detect geometry types
│   ├── dissolve.py                # Unify & repair geometries
│   ├── buffering.py               # CRS projection & buffering
│   └── pipeline.py                # Orchestrate geometry workflow
├── core/
│   ├── input_reader.py            # Legacy input reader (backward compatible)
│   ├── arcgis_query.py            # Query ArcGIS FeatureServers
│   ├── layer_processor.py         # Batch process layers
│   ├── map_builder.py             # Generate Folium/Leaflet maps
│   └── output_generator.py        # Save HTML, GeoJSON, metadata
├── utils/
│   ├── logger.py                  # Logging (console + file)
│   ├── geometry_converters.py     # ESRI JSON → GeoJSON
│   ├── layer_control_helpers.py   # Layer grouping and control data
│   ├── pdf_generator.py           # PDF reports (fpdf2)
│   └── xlsx_generator.py          # Excel reports
├── templates/
│   ├── download_control.html      # Download button UI
│   ├── side_panel.html            # Left legend panel
│   └── layer_control_panel.html   # Right layer control panel
├── logs/                           # Timestamped log files
├── outputs/                        # Generated maps and data
└── temp/                           # Temporary files
```

### Module Responsibilities

**Configuration:**
- `config/config_loader.py`: Loads `layers_config.json` and geometry settings

**Geometry Input:**
- `geometry_input/pipeline.py`: Main entry point - orchestrates complete workflow
- Supports point/line/polygon with automatic buffering
- UTM-based CRS selection for accurate buffering

**Core Modules:**
- `core/arcgis_query.py`: Queries FeatureServers with spatial intersection
- `core/map_builder.py`: Creates interactive maps with Jinja2 templates
- `core/layer_processor.py`: Batch processes all configured layers

**Utilities:**
- `utils/geometry_converters.py`: ESRI JSON → GeoJSON conversion
- `utils/pdf_generator.py`: PDF reports with hyperlinked resource areas
- `utils/xlsx_generator.py`: Excel reports

**Templates:**
- Jinja2 templates for UI components (separates presentation from logic)

## Key Design Decisions

### Enhanced Geometry Processing Pipeline
Supports **points, lines, and polygons** as input with automatic buffering.

**Workflow:**
1. Load geospatial file, detect CRS and geometry type
2. Dissolve multi-part geometries into single unified geometry
3. Buffer points/lines in projected CRS (polygons skip buffering)
4. Repair invalid geometries
5. Output single polygon in EPSG:4326

**Buffer Implementation:**
- Unit conversion: Feet → meters (0.3048 factor)
- CRS selection: Automatic UTM zone based on centroid
- Fallback: Albers (EPSG:5070) for CONUS, Web Mercator (EPSG:3857) globally
- Default: 500 feet (configurable via `geometry_settings.buffer_distance_feet`)

**Configuration:**
```json
{
  "geometry_settings": {
    "buffer_distance_feet": 500,
    "buffer_point_geometries": true,
    "buffer_line_geometries": true,
    "auto_repair_invalid": true,
    "fallback_crs": "EPSG:5070"
  }
}
```

**Backward Compatibility:**
- Legacy `core/input_reader.py` still available
- Main entry auto-detects which pipeline to use

### Bounding Box Queries with Client-Side Filtering
Two-stage approach for faster, more reliable results:

**Stage 1 - Server-side (Envelope):**
```python
{
    'xmin': bounds[0], 'ymin': bounds[1],
    'xmax': bounds[2], 'ymax': bounds[3],
    'spatialReference': {'wkid': 4326}
}
```

**Stage 2 - Client-side (Precise):**
```python
polygon_geometry = polygon_geom.geometry.iloc[0]
gdf = gdf[gdf.intersects(polygon_geometry)]
```

Uses POST requests (not GET) to avoid URI length limits. Timeout: 60 seconds.

### Smart Rendering Strategy
- **All Point Layers**: MarkerCluster for reliable custom layer control (scales to 60+ layers)
  - <50 features: `disableClusteringAtZoom: 15` (show individuals when zoomed in)
  - ≥50 features: Full clustering
- **Lines/Polygons**: GeoJSON with hover effects

Clustering threshold configurable: `settings.cluster_threshold` (default: 50)

### Custom Layer Control System
Uses **custom panel** instead of Folium's default LayerControl:

**Why?**
- No layer grouping support
- No search functionality
- Can't remember group-level checkbox states

**Implementation:**
1. Remove `name` parameter from layers (prevents Folium wrapping)
2. Hide overlay section with CSS (only basemap controls visible)
3. Custom JavaScript control in right panel
4. Layers stored in `mapLayers` object

**Point Layer Architecture - MarkerCluster Only:**
- ALL point layers use `plugins.MarkerCluster()` regardless of feature count
- No wrapper issues (MarkerCluster doesn't get wrapped like FeatureGroup)
- Scalable to dozens of layers

**JavaScript Layer Detection (Hybrid):**
1. **Input Polygon**: CSS className `'appeit-input-polygon'`
2. **GeoJSON (lines/polygons)**: CSS className `'appeit-layer-{sanitized-name}'`
3. **MarkerCluster (points)**: Custom `_appeitLayerName` property (injected at 100ms delay)

**Defensive JavaScript:** Always use `typeof` checks before `instanceof` to prevent TypeError

### Navigation State Management
**Problem:** Browser back button causes checkbox/layer desync (bfcache)

**Solution:** Multi-method navigation detection triggers page refresh:
1. **pageshow event** (`event.persisted`): bfcache restoration
2. **Performance Navigation API** (`performance.navigation.type === 2`): Works with `file://` protocol
3. **Navigation Timing API Level 2** (`navEntries[0].type === 'back_forward'`): Modern standard

All methods trigger `window.location.reload()` to ensure state consistency.

### PDF Report Generation
Professional reports using fpdf2:
- Cover page with project metadata
- Body table with features organized by category/layer
- Hyperlinked Resource Area codes
- BMP reference page with NTIA mitigation guidelines
- Two-pass rendering for accurate page numbers
- Landscape orientation

### Jinja2 Templates
UI components stored as Jinja2 templates (not embedded Python strings):
- Separates presentation from logic
- Easier editing and maintenance
- Proper syntax highlighting

## Configuration System

**File:** `config/layers_config.json`

**Layer structure:**
```json
{
  "name": "Layer Name",
  "url": "https://services.arcgis.com/.../FeatureServer",
  "layer_id": 0,
  "color": "#HEX_COLOR",
  "icon": "font-awesome-icon-name",
  "icon_color": "red|blue|green|purple|...",
  "description": "Layer description",
  "geometry_type": "point|line|polygon",
  "group": "Group Name"
}
```

**Layer Groups:**
Layers organized into groups (EPA Programs, Federal/Tribal Land, Historic Places, etc.). Groups only appear if they contain intersected features.

**Key Settings:**
- `max_features_per_layer`: Server-side limit (typically 1000)
- `enable_clustering`: Enable marker clustering
- `cluster_threshold`: Min features before clustering (default: 50)
- `default_zoom`: Initial zoom level (default: 10)
- `geocoder.enabled`: Enable address/coordinate search

## Development Tasks

### Running
```bash
conda activate claude
python appeit_map_creator.py
```

Output:
- Log file: `logs/appeit_YYYYMMDD_HHMMSS.log`
- Output: `outputs/appeit_map_YYYYMMDD_HHMMSS/`

### Adding a New Layer
1. Find FeatureServer REST API URL
2. Test: `{url}/0/query?where=1=1&f=json`
3. Choose Font Awesome icon and group name
4. Add to `layers_config.json` with `group` field
5. No code changes needed

### Testing

**Polygon input:** `pa045_mpb.gpkg`
**Point input:** Any point file → auto-buffered 500ft
**Line input:** Any line file → auto-buffered 500ft both sides

All geometry types automatically:
- Detect type
- Apply buffer if needed
- Dissolve to single geometry
- Output EPSG:4326

### Debugging

**Failed Queries:**
1. Check console for errors
2. Review `metadata.json` for stats (`bbox_count`, `filtered_count`, `query_time`)
3. Check `logs/appeit_TIMESTAMP.log` for DEBUG details
4. Test FeatureServer URL in browser
5. Check metadata: timeouts at 60 seconds

**Map Issues:**
1. Download button: Check browser console
2. Layers not toggling: Check `initializeLayerControl()` errors
3. Missing icons: Verify Font Awesome CDN accessible
4. Template errors: Verify `templates/` directory exists

## Output Structure

```
outputs/appeit_map_YYYYMMDD_HHMMSS/
├── index.html                    # Self-contained interactive map
├── metadata.json                 # Query statistics, feature counts
├── PEIT_Report_YYYYMMDD.pdf      # Formatted PDF report
├── PEIT_Report_YYYYMMDD.xlsx     # Excel spreadsheet
└── data/
    ├── input_polygon.geojson
    └── {layer_name}.geojson
```

## Interactive Map Features

### Download Control
- Bottom-right corner, shifts with right panel
- Formats: GeoJSON, Shapefile (ZIP), KMZ
- Download individual layers or all as ZIP
- Client-side conversion (shp-write, tokml)

### Dual Panel System

**Left Panel (Legend):**
- About section
- PDF/XLSX report links (open in new tab with `target="_blank"`)
- Dynamic legend (icons/colors matching layers)
- Feature counts
- Auto-updates to show only visible layers

**Right Panel (Layer Control):**
- Search box for filtering
- Grouped layer organization
- Group-level and individual checkboxes
- Feature counts
- Only shows groups with intersected features

### Map Controls
- **Base Layer Control**: Street/Light/Dark/Satellite
- **Geocoder**: Search by address or coordinates
- **Measure Control**: Distance/area measurement
- **Fullscreen**: Expand to full screen
- **Right-Click Menu**: Copy coordinates to clipboard

### Feature Interactions
- Click features for popups (attributes, URLs as clickable links)
- Hover effects on lines/polygons
- Clustering for point layers (smart thresholds)

## Important Implementation Details

### Metadata Tracking
Each query tracks:
- `feature_count`: Final count after filtering
- `bbox_count`: Initial count from bbox query
- `filtered_count`: Features removed by filtering
- `query_time`: Query time in seconds
- `warning`: Server limit warnings
- `error`: Error messages

### Coordinate Systems
- All inputs reprojected to EPSG:4326
- Buffering uses UTM zones (auto-selected by centroid)
- Query parameters: `'inSR': '4326', 'outSR': '4326'`

### Import Dependencies
Strict layering to avoid circular dependencies:
```
config/ → utils/ → core/ → appeit_map_creator.py
```

## Known Limitations

1. FeatureServer limits: 1000-2000 features max (warns, doesn't paginate)
2. Requires internet (no offline mode)
3. Multi-feature files dissolved to single geometry (by design)
4. Large buffers (>10k ft points, >5k ft lines) may timeout

## Input Format Support

**File Formats:** SHP, KML/KMZ, GPKG, GeoJSON, GDB

**Geometry Types:**
- Points/MultiPoint: Auto-buffered 500ft
- Lines/MultiLineString: Auto-buffered 500ft both sides
- Polygons/MultiPolygon: Used as-is (no buffer)

All outputs standardized to EPSG:4326.

## Git Workflow

- Only commit/push when explicitly requested
- No "Generated with Claude Code" attribution
- No "Co-Authored-By: Claude" lines
- Clean, descriptive commit messages

## Best Practices

### When Modifying Core Modules
1. Update docstrings if signatures change
2. Maintain logging (INFO for users, DEBUG for details)
3. Test independently before integration
4. Keep single responsibility

### When Adding Layers
1. Test FeatureServer URL in browser first
2. Identify correct `layer_id` (usually 0)
3. Choose appropriate `geometry_type`
4. Select contrasting icon/color
5. Assign to appropriate group

### VSCode Configuration for Jinja2
To avoid false TypeScript/JavaScript errors:

**1. Install Better Jinja Extension:** `samuelcolvin.jinjahtml`

**2. Configure File Associations:**
```json
{
  "files.associations": {
    "**/templates/*.html": "jinja-html"
  }
}
```

**3. Use `// @ts-nocheck` in Script Tags:**
```javascript
<script>
    // @ts-nocheck
    const data = {{ jinja_variable|safe }};
</script>
```

### Code Organization
- One module = one responsibility
- Helper functions in utils/
- Business logic in core/
- Configuration in config/
- UI templates in templates/
- Keep main file minimal

### Error Handling
- All modules use try/except with logging
- Errors propagate to main() for centralized handling
- Log files capture full stack traces
- Users see clean console messages

## Module Quick Reference

### geometry_input.pipeline
- `process_input_geometry(file_path, buffer_distance_feet)`: Main entry point
- Returns: (GeoDataFrame, metadata_dict)

### core.arcgis_query
- `query_arcgis_layer(layer_url, layer_id, polygon_geom, layer_name)`: Query single layer
- Returns: GeoDataFrame with features

### core.map_builder
- `create_web_map(polygon_gdf, layer_results, metadata, config, input_filename)`: Build complete map
- Returns: Folium map object

### core.output_generator
- `generate_output(map_obj, polygon_gdf, layer_results, metadata, output_name)`: Save all outputs
- Returns: Path to output directory

### utils.pdf_generator
- `generate_pdf_report(layer_results, config, output_path, timestamp, project_name, project_id)`: PDF generation
- Two-pass rendering for accurate page numbers
- Hyperlinked resource areas

### utils.xlsx_generator
- `generate_xlsx_report(layer_results, config, output_path, timestamp, project_name, project_id)`: Excel generation
- Tabular format with category/layer/area/resources columns

### utils.layer_control_helpers
- `organize_layers_by_group(config, layer_results)`: Group layers by configured group
- `generate_layer_control_data(groups, layer_results, config)`: Data for template rendering
- `generate_layer_geojson_data(layer_results, polygon_gdf)`: Embedded GeoJSON as JavaScript

### config.config_loader
- `load_config()`: Load layers_config.json
- `load_geometry_settings(config)`: Load geometry settings with defaults
