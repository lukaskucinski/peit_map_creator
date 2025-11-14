# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

APPEIT Map Creator replicates NTIA's APPEIT tool functionality without requiring an ArcGIS Pro license. It queries ESRI-hosted FeatureServer REST APIs and generates interactive Leaflet web maps showing environmental features that intersect with user-provided polygons.

## Architecture

The tool uses a **modular architecture** with separate packages for configuration, core functionality, utilities, and templates.

### Project Structure

```
appeit_map_creator/
├── appeit_map_creator.py          # Main entry point (~150 lines)
├── appeit_map_creator_legacy.py   # Original monolithic version (backup)
│
├── config/
│   ├── __init__.py
│   ├── config_loader.py           # Configuration loading & validation
│   └── layers_config.json         # Layer definitions and settings
│
├── geometry_input/                # Enhanced geometry processing package
│   ├── __init__.py
│   ├── load_input.py              # Load files, detect geometry types
│   ├── dissolve.py                # Unify & repair geometries
│   ├── buffering.py               # CRS projection & buffering
│   └── pipeline.py                # Orchestrate geometry workflow
│
├── core/
│   ├── __init__.py
│   ├── input_reader.py            # Legacy: Read and reproject input polygons
│   ├── arcgis_query.py            # Query ArcGIS FeatureServers
│   ├── layer_processor.py         # Batch process all layers
│   ├── map_builder.py             # Generate Folium/Leaflet maps
│   └── output_generator.py        # Save HTML, GeoJSON files, metadata
│
├── utils/
│   ├── __init__.py
│   ├── logger.py                  # Logging configuration (console + file)
│   ├── geometry_converters.py     # ESRI JSON → GeoJSON conversion
│   ├── html_generators.py         # HTML/JS generation helpers
│   ├── popup_formatters.py        # Popup value formatting
│   ├── layer_control_helpers.py   # Layer grouping and control data generation
│   ├── pdf_generator.py           # PDF report generation using fpdf2
│   └── xlsx_generator.py          # Excel report generation
│
├── templates/
│   ├── __init__.py
│   ├── download_control.html      # Download button UI (Jinja2)
│   ├── side_panel.html            # Left side panel with legend (Jinja2)
│   └── layer_control_panel.html   # Right side panel with grouped layer controls (Jinja2)
│
├── logs/                           # Log files (timestamped)
├── images/                         # Images to be used in project
│   ├──/basemap_thumbnails          # Basemap thumbnails folder
├── outputs/                        # Generated maps and data
└── temp/                          # Temporary files
```

### Module Responsibilities

**Main Entry Point:**
- `appeit_map_creator.py`: Orchestrates workflow, sets up logging, handles errors

**Configuration:**
- `config/config_loader.py`: Loads and validates `layers_config.json`, loads geometry settings

**Geometry Input (Enhanced):**
- `geometry_input/load_input.py`: Load files, detect geometry types (point/line/polygon)
- `geometry_input/dissolve.py`: Dissolve multi-part geometries, repair invalid geometries
- `geometry_input/buffering.py`: Buffer point/line geometries in projected CRS
- `geometry_input/pipeline.py`: Main entry point - orchestrates complete geometry workflow

**Core Modules:**
- `core/input_reader.py`: Legacy input reader (still available for backward compatibility)
- `core/arcgis_query.py`: Queries FeatureServers with spatial intersection
- `core/layer_processor.py`: Processes multiple layers in batch
- `core/map_builder.py`: Creates interactive maps with Jinja2 templates
- `core/output_generator.py`: Saves output files and metadata

**Utilities:**
- `utils/logger.py`: Console (INFO) + file (DEBUG) logging
- `utils/geometry_converters.py`: ESRI point/line/polygon → GeoJSON
- `utils/html_generators.py`: Generate download menus and data mappings
- `utils/popup_formatters.py`: Format attribute values (URLs → links)
- `utils/layer_control_helpers.py`: Organize layers by group, generate control data, create GeoJSON mappings
- `utils/pdf_generator.py`: Generate formatted PDF reports with fpdf2
- `utils/xlsx_generator.py`: Generate Excel reports with feature data

**Templates:**
- `templates/download_control.html`: Download UI with embedded JavaScript
- `templates/side_panel.html`: Left collapsible panel with legend (syncs with layer visibility)
- `templates/layer_control_panel.html`: Right collapsible panel with grouped layer controls and search

## Key Design Decisions

### Modular Architecture
The code is organized into single-responsibility modules rather than a monolithic script. This improves:
- **Maintainability**: Each module focuses on one aspect
- **Testability**: Functions can be tested independently
- **Reusability**: Utilities can be imported by other tools
- **Readability**: Main file is ~134 lines vs. original 1,418 lines

### Logging System
Dual-output logging provides visibility at different levels:
- **Console**: INFO-level messages for user feedback
- **File**: DEBUG-level details for troubleshooting
- Log files: `logs/appeit_YYYYMMDD_HHMMSS.log`

All modules use `utils.logger.get_logger(__name__)` for consistent logging.

### POST Requests Over GET
The tool uses HTTP POST requests to query FeatureServers (not GET) to avoid 414 "URI too long" errors when geometry parameters are complex.

Implementation: `requests.post(query_url, data=params, timeout=60)`

### Bounding Box (Envelope) Queries with Client-Side Filtering
Uses bounding box for initial FeatureServer queries, then performs client-side filtering for precise polygon intersection. This two-stage approach is faster and more reliable across different FeatureServer implementations.

**Stage 1 - Server-side (Envelope):**
```python
{
    'xmin': bounds[0],
    'ymin': bounds[1],
    'xmax': bounds[2],
    'ymax': bounds[3],
    'spatialReference': {'wkid': 4326}
}
```

**Stage 2 - Client-side (Precise):**
```python
polygon_geometry = polygon_geom.geometry.iloc[0]
gdf = gdf[gdf.intersects(polygon_geometry)]
```

This ensures only features that truly intersect the input polygon are included in final results.

### ESRI JSON to GeoJSON Conversion
The tool converts three ESRI geometry types to GeoJSON using `utils/geometry_converters.py`:
- **Point**: `{x, y}` → GeoJSON Point with coordinates `[x, y]`
- **LineString**: `{paths: [[coords]]}` → GeoJSON LineString/MultiLineString
- **Polygon**: `{rings: [[[coords]]]}` → GeoJSON Polygon

This happens in `core/arcgis_query.py` which calls the converter functions.

### Smart Rendering Strategy
- **All Point Layers**: MarkerCluster for reliable custom layer control (scales to 60+ layers)
  - Layers with <50 features use `disableClusteringAtZoom: 15` to show individual markers when zoomed in
  - Layers with ≥50 features use full clustering for performance
  - All point markers use Font Awesome icons with custom colors
- **Lines**: GeoJSON polylines with hover effects
- **Polygons**: GeoJSON filled areas with borders

Clustering threshold configurable in `config/layers_config.json` under `settings.cluster_threshold` (default: 50).

### Enhanced Geometry Processing Pipeline
The tool supports **points, lines, and polygons** as input geometries with automatic buffering for non-polygon types.

**Workflow:**
1. **Load**: Read geospatial file, detect CRS and geometry type
2. **Dissolve**: Merge multi-part geometries into single unified geometry
3. **Buffer** (points/lines only): Convert to projected CRS → buffer in meters → convert back to EPSG:4326
4. **Validate**: Repair invalid geometries, ensure output is valid polygon
5. **Output**: Single-row GeoDataFrame in EPSG:4326

**Geometry Type Support:**
- **Polygon/MultiPolygon**: Dissolved → single polygon (no buffer applied)
- **LineString/MultiLineString**: Dissolved → buffered in projected CRS → polygon
- **Point/MultiPoint**: Dissolved → buffered in projected CRS → polygon

**Buffer Implementation:**
- **Unit Conversion**: Feet → meters (0.3048 conversion factor)
- **CRS Selection**: Automatic UTM zone selection based on centroid longitude/latitude
- **Fallback CRS**: Albers Equal Area (EPSG:5070) for CONUS, Web Mercator (EPSG:3857) globally
- **Default Buffer**: 500 feet (configurable in `geometry_settings.buffer_distance_feet`)
- **Final Output**: Always EPSG:4326 regardless of intermediate projections

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
- Legacy `core/input_reader.py` still available if `geometry_input/` not found
- Main entry point auto-detects which pipeline to use
- Old polygon-only workflow continues working unchanged

**Metadata Tracking:**
Enhanced metadata captures geometry transformations in `metadata.json`:
```json
{
  "input_geometry": {
    "original_file": "point.gpkg",
    "original_crs": "EPSG:2272",
    "geometry_type": "point",
    "buffer_applied": true,
    "buffer_distance_feet": 500,
    "buffer_distance_meters": 152.4,
    "final_crs": "EPSG:4326"
  }
}
```

### Jinja2 Templates for UI
HTML/CSS/JavaScript for UI components are stored as Jinja2 templates, not embedded in Python strings. This:
- Separates presentation from logic
- Makes HTML easier to edit and maintain
- Allows proper syntax highlighting in editors
- Reduces Python file sizes significantly

### PDF Report Generation
The tool generates professional PDF reports using fpdf2 (pure Python PDF library):

**Key Features:**
- **Cover Page**: Centered metadata (Project Name, ID, Report Date)
- **Body Table**: All intersected features organized by category and layer
- **Hyperlinked Resource Areas**: Blue clickable links for each resource code
- **BMP Reference Page**: Links to NTIA mitigation guidelines
- **Accurate Page Numbering**: Gray page numbers excluding cover page

**Technical Implementation:**
- **Two-Pass Rendering**: First pass calculates total pages, second pass generates final PDF with correct page numbers
- **Manual Table Rendering**: Required for markdown hyperlink support in cells
- **Text Truncation**: Long area names truncated with ellipsis for uniform row heights
- **Landscape Orientation**: Letter size in landscape mode for wider tables
- **Optimized Margins**: Reduced vertical margins to fit 3-4 more rows per page
- **Unicode Font Support**: Uses DejaVu Sans TrueType fonts to support full Unicode character range including en-dashes (–), em-dashes (—), smart quotes (""), and international characters

**Unicode Character Support:**
The PDF generator uses DejaVu Sans fonts (bundled in `fonts/` directory) to support:
- En-dash (–, U+2013) and em-dash (—, U+2014)
- Smart quotes ("", U+201C/201D) and apostrophes (', U+2019)
- Accented characters (é, ñ, ü, etc.)
- Full Unicode range for 200+ languages

This ensures official names from ArcGIS FeatureServers (like Federal land names) are preserved exactly as they appear in source data.

**Resource Area Mapping:**
The PDF uses a category-to-resource-area mapping system:
```python
{
    'EPA Programs': ['1.4', '1.9', '1.11'],
    'Federal/Tribal Land': ['1.7', '1.8'],
    'Historic Places': ['1.8'],
    'Floodplains/Wetlands': ['1.5'],
    'Infrastructure': ['1.1'],
    'Critical Habitats': ['1.6', '1.10']
}
```

Each resource area code links to the NTIA BMP Master PDF with appropriate section anchors.

### Custom Layer Control System
The tool uses a **custom layer control panel** instead of Folium's default LayerControl for overlay layers:

**Why custom control?**
- Folium's LayerControl doesn't support layer grouping
- No search/filter functionality in default control
- Cannot remember group-level checkbox states
- Limited styling and customization options

**Implementation approach:**
1. **Remove layer names**: Environmental layers are added to map WITHOUT the `name` parameter to prevent them from appearing in Folium's LayerControl
2. **Position LayerControl after layers**: LayerControl is added AFTER all environmental layers to ensure proper Leaflet initialization (prevents `setZIndex` errors)
3. **Hide overlays with CSS**: `.leaflet-control-layers-overlays` section is hidden, so only base map radio buttons are visible
4. **Custom JavaScript control**: Layers are stored in `mapLayers` object and controlled via custom checkboxes in the right panel
5. **State synchronization**: Custom events (`layerVisibilityChanged`) sync layer visibility between right panel and left legend

**Point Layer Architecture - MarkerCluster Only:**
All point layers use MarkerCluster (not FeatureGroup) to eliminate Folium wrapper layer issues:

- **Universal Clustering**: ALL point layers use `plugins.MarkerCluster()` regardless of feature count
- **Smart Clustering Behavior**: Layers with <50 features use `disableClusteringAtZoom: 15` to show individual markers when zoomed in
- **Scalability**: This approach reliably handles dozens of layers across multiple groups
- **No Wrapper Issues**: MarkerCluster doesn't get wrapped by Folium like FeatureGroup does, ensuring reliable layer identification

**JavaScript layer detection (Hybrid Strategy):**
Layers are identified using a hybrid approach to ensure reliability:

1. **Input Polygon**: Identified by CSS className `'appeit-input-polygon'` in the GeoJSON style
2. **GeoJSON Layers (lines/polygons)**: Identified by CSS className `'appeit-layer-{sanitized-name}'`
   - Example: "Navigable Waterways" → `'appeit-layer-navigable-waterways'`
3. **Point Layers (MarkerCluster)**: Identified by custom `_appeitLayerName` property
   - Injected via centralized script after map rendering
   - Uses "first unidentified" strategy to tag layers in creation order
   - Filters out input polygon wrapper (detects `appeit-input-polygon` className in sub-layers)

**Why hybrid approach?**
- Folium's `name` parameter is NOT JavaScript-accessible (only used by LayerControl internally)
- Order-based matching is unreliable due to unpredictable `eachLayer()` iteration order
- CSS className works for GeoJSON but not for MarkerCluster
- Custom property injection ensures deterministic identification for point layers
- Input polygon filtering prevents misidentification of wrapper layers

**Implementation details:**
- Point layer identifiers injected at 100ms delay to ensure Folium has rendered layers
- Layer control initialization runs at 200ms delay to wait for identifiers
- All layers stored in global `mapLayers` object for visibility toggling
- Defensive `typeof` checks before all `instanceof` operations to prevent TypeError

### Navigation State Management
The tool implements robust page refresh detection to maintain layer visibility state consistency:

**Challenge:**
When users navigate away from the map (e.g., to Google Maps) and return via browser back button, checkbox states can desynchronize from actual layer visibility due to browser form state caching (bfcache).

**Solution - Multi-Method Navigation Detection:**
Three complementary detection methods ensure page refresh on all navigation scenarios:

1. **pageshow Event** (`event.persisted`): Detects bfcache restoration (standard approach)
2. **Performance Navigation API** (`performance.navigation.type === 2`): Detects back/forward button (works with `file://` protocol)
3. **Navigation Timing API Level 2** (`navEntries[0].type === 'back_forward'`): Modern browser standard

**Why multiple methods?**
- Different browsers and protocols (http://, https://, file://) handle navigation events differently
- Local `file://` protocol doesn't reliably trigger `event.persisted`
- Performance API provides fallback for edge cases
- Multiple detection layers ensure 100% coverage

**Implementation:**
```javascript
// Method 1: bfcache restoration
window.addEventListener('pageshow', function(event) {
    if (event.persisted) {
        window.location.reload();
    }
});

// Method 2: Legacy Navigation API (file:// compatible)
window.addEventListener('load', function() {
    if (performance.navigation && performance.navigation.type === 2) {
        window.location.reload();
    }

    // Method 3: Modern Navigation Timing API
    if (performance.getEntriesByType) {
        var navEntries = performance.getEntriesByType('navigation');
        if (navEntries.length > 0 && navEntries[0].type === 'back_forward') {
            window.location.reload();
        }
    }
});
```

**Result:** Page automatically refreshes on browser back/forward navigation, ensuring layer visibility and checkbox states are always synchronized.

## Configuration System

Configuration file: `config/layers_config.json`

**Default layers included**:
1. **RCRA Sites** - Resource Conservation and Recovery Act regulated facilities (points, red recycle icon)
2. **NPDES Sites** - National Pollutant Discharge Elimination System sites (points, blue tint icon)
3. **Navigable Waterways** - USACE Navigable Waterway Network (lines, green ship icon)
4. **Historic Places** - National Register of Historic Places (points, purple landmark icon)

**Layer structure**:
```json
{
  "name": "Layer Name",
  "url": "https://services.arcgis.com/.../FeatureServer",
  "layer_id": 0,
  "color": "#HEX_COLOR",
  "icon": "font-awesome-icon-name",
  "icon_color": "red|blue|green|purple|orange|darkred|lightred|beige|darkblue|darkgreen|cadetblue|darkpurple|white|pink|lightblue|lightgreen|gray|black|lightgray",
  "fill_color": "#HEX_COLOR",
  "fill_opacity": 0.5,
  "description": "Layer description",
  "geometry_type": "point|line|polygon",
  "group": "Group Name"
}
```

**Field descriptions**:
- `name`: Display name for the layer (required)
- `url`: ArcGIS FeatureServer REST API endpoint (required)
- `layer_id`: Layer ID within the FeatureServer (required, typically 0)
- `color`: Border/stroke color for lines and polygons (required, hex format)
- `icon`: Font Awesome icon name (required for point layers only)
- `icon_color`: Marker color (required for point layers only)
- `fill_color`: Fill color for polygon layers (optional, defaults to `color` value)
- `fill_opacity`: Fill transparency for polygon layers (optional, 0.0-1.0, defaults to 0.6)
- `description`: Human-readable description (required)
- `geometry_type`: Feature geometry type (required: "point", "line", or "polygon")
- `group`: Category for layer organization (required)
- `area_name_field`: Attribute field containing primary name (optional but recommended, used for popup headers and reports)

**Notes**:
- `icon` and `icon_color` are only used for point layers
- `fill_color` and `fill_opacity` are only used for polygon layers (when not using patterns)
- If `fill_color` is not specified for polygons, the `color` value will be used for both border and fill
- Fill opacity of 0.0 = fully transparent, 1.0 = fully opaque
- `area_name_field` is used for popup headers in the map; if not specified, falls back to first field containing 'name'

### Pattern Fill Support for Polygons

Polygon layers can use **hatched/striped pattern fills** instead of solid colors to match ArcGIS Pro symbology. This is useful for distinguishing overlapping polygon layers or matching official cartographic standards.

**Pattern Configuration:**
Add optional `fill_pattern` object to polygon layer configuration:

```json
{
  "name": "BIA AIAN LAR Supplemental",
  "color": "#CDAA66",
  "fill_pattern": {
    "type": "stripe",
    "angle": -45,
    "weight": 3,
    "space_weight": 3,
    "opacity": 0.75,
    "space_opacity": 0.0
  },
  "geometry_type": "polygon"
}
```

**Pattern Parameters:**
- `type`: Pattern type (`"stripe"` currently supported)
- `angle`: Stripe rotation angle in degrees (default: -45)
  - `-45`: Diagonal bottom-left to top-right (standard hatching)
  - `0`: Horizontal stripes
  - `90`: Vertical stripes
- `weight`: Stripe line width in pixels (default: 3)
- `space_weight`: Spacing between stripes in pixels (default: 3)
- `opacity`: Stripe opacity 0.0-1.0 (default: 0.75)
- `space_opacity`: Background opacity 0.0-1.0 (default: 0.0 for transparent)
- `space_color`: Background color hex (default: "#ffffff", optional)

**Implementation Details:**
- Uses Folium's built-in `StripePattern` plugin (no external dependencies)
- Patterns are rendered as SVG for sharp, scalable display
- Legend automatically shows hatched symbols for patterned layers
- Solid fill layers and patterned layers can coexist in same map
- When `fill_pattern` is present, `fill_color` and `fill_opacity` are ignored

**Backward Compatibility:**
- Polygon layers without `fill_pattern` continue using solid fills
- Existing configurations remain unchanged

**Layer Groups:**
Layers are organized into groups for the custom layer control panel:
- **EPA Programs**: RCRA Sites, NPDES Sites
- **Federal/Tribal Land**: Navigable Waterways
- **Historic Places**: Historic Places
- **Other**: Default group for layers without explicit group assignment

Groups only appear in the UI if they contain layers with intersected features.

**Settings**:
- `max_features_per_layer`: Server-side limit (typically 1000)
- `enable_clustering`: Enable marker clustering for points
- `cluster_threshold`: Minimum features before clustering activates (default: 50)
- `default_zoom`: Initial map zoom level (default: 10)
- `tile_layer`: Base map provider (default: "OpenStreetMap")
- `geocoder`: Configuration for address/coordinate search control
  - `enabled`: Enable geocoder control (default: true)
  - `collapsed`: Start collapsed (default: true)
  - `position`: Control position (default: "topright")
  - `search_zoom`: Zoom level for search results (default: 15)

## Development Tasks

### Running the Script
```bash
# Activate conda environment
conda activate claude

# Run complete workflow
python appeit_map_creator.py
```

The script will:
1. Create a log file in `logs/appeit_YYYYMMDD_HHMMSS.log`
2. Display INFO-level progress messages on console
3. Generate output in `outputs/appeit_map_YYYYMMDD_HHMMSS/`

### Adding a New Environmental Layer
1. Find ArcGIS FeatureServer REST API URL
2. Test URL in browser: `{url}/0/query?where=1=1&f=json`
3. Choose icon from Font Awesome (prefix='fa')
4. Choose an appropriate group name (e.g., "EPA Programs", "Water Resources", "Infrastructure")
5. Add to `config/layers_config.json` layers array with `group` field
6. No code changes needed - configuration drives everything

### Working with Multi-Layer FeatureServers

Some ArcGIS FeatureServers contain **multiple sublayers** at different layer IDs (0, 1, 2, etc.). Each sublayer may have:
- Different geographic extents
- Different feature types
- Different attribute schemas

**Example:** BIA AIAN LAR Layers FeatureServer
- **Layer 0**: National LAR (CONUS-wide extent)
- **Layer 1**: LAR Supplemental (Western/Central US only)
- **Layer 2**: Tribal Statistical Areas (Oklahoma/Texas region only)

**How to handle:**
1. **Identify sublayers**: Visit the FeatureServer base URL in browser to see all available layers
2. **Create separate entries**: Add one configuration entry per sublayer to `layers_config.json`
3. **Same URL, different layer_id**: All entries use the same base URL but different `layer_id` values
4. **Different names and colors**: Give each sublayer a distinct name and color for UI clarity

**Example configuration:**
```json
{
  "name": "BIA AIAN National LAR",
  "url": "https://services3.arcgis.com/.../BIA_AIAN_LAR_Layers/FeatureServer",
  "layer_id": 0,
  "color": "#F5CA7A",
  ...
},
{
  "name": "BIA AIAN LAR Supplemental",
  "url": "https://services3.arcgis.com/.../BIA_AIAN_LAR_Layers/FeatureServer",
  "layer_id": 1,
  "color": "#D4A574",
  ...
}
```

**Query behavior:**
- Each sublayer is queried independently using `{url}/{layer_id}/query` endpoint
- Sublayers outside the input polygon's geographic extent will return "No features found"
- Only sublayers with intersecting features appear in the final map
- This is the correct and recommended ArcGIS REST API pattern

**Important notes:**
- Don't append `/0`, `/1`, `/2` to the URL in configuration - use `layer_id` field instead
- Geographic extent differences are normal - not all sublayers cover the same areas
- The tool automatically handles layers with no results

### Testing

#### Test with Polygon Input (Backward Compatibility)
Test with Vermont project area polygon: `C:\Users\lukas\Downloads\pa045_mpb.gpkg`

Expected results vary by location:
- RCRA Sites (clustered if >50 features)
- NPDES Sites (clustered if >50 features)
- Navigable Waterways (lines, if in area)
- Historic Places (points, if in area)

#### Test with Point Input (NEW)
Create a test point file or use existing point data:
```python
import geopandas as gpd
from shapely.geometry import Point

# Create test point (Vermont coordinates)
point = Point(-72.5778, 44.2601)  # Montpelier, VT
gdf = gpd.GeoDataFrame([{'geometry': point}], crs='EPSG:4326')
gdf.to_file('test_point.gpkg', driver='GPKG')
```

Expected behavior:
1. Point detected automatically
2. 500-foot buffer applied
3. Circular search area created
4. Intersection query performed
5. Metadata shows `buffer_applied: true`

#### Test with Line Input (NEW)
Create a test line file or use existing road/stream data:
```python
from shapely.geometry import LineString

# Create test line
line = LineString([(-72.5778, 44.2601), (-72.5678, 44.2701)])
gdf = gpd.GeoDataFrame([{'geometry': line}], crs='EPSG:4326')
gdf.to_file('test_line.gpkg', driver='GPKG')
```

Expected behavior:
1. Line detected automatically
2. 500-foot buffer applied on both sides
3. Elongated search area created
4. Intersection query performed
5. Metadata shows `buffer_applied: true`

#### Verify Enhanced Metadata
Check `outputs/appeit_map_TIMESTAMP/metadata.json` for new fields:
```json
{
  "input_geometry": {
    "original_file": "test_point.gpkg",
    "original_crs": "EPSG:4326",
    "geometry_type": "point",
    "buffer_applied": true,
    "buffer_distance_feet": 500,
    "buffer_distance_meters": 152.4,
    "buffer_area": {
      "area_sq_miles_approx": 0.02
    },
    "final_crs": "EPSG:4326"
  }
}
```

### Debugging Failed Queries
1. Check console output for layer-specific error messages
2. Review `outputs/appeit_map_TIMESTAMP/metadata.json` for query statistics
3. Check log file: `logs/appeit_TIMESTAMP.log` for DEBUG-level details
4. Verify FeatureServer is accessible: Test URL directly in browser
   - Example: `https://services3.arcgis.com/.../FeatureServer/0/query?where=1=1&f=json`
5. Check `query_time` in metadata - timeouts occur at 60 seconds
6. Examine metadata for client-side filtering stats:
   - `bbox_count` - Features returned from server
   - `filtered_count` - Features removed (outside polygon)
   - `feature_count` - Final count in results

### Debugging Map Issues
1. **Download button not working**: Check browser console for JavaScript errors
2. **Clustering not appearing**: Verify `enable_clustering: true` and feature count ≥ threshold
3. **Side panels not toggling**: Check for JavaScript errors in browser console
4. **Missing icons**: Ensure Font Awesome CDN is accessible
5. **Geocoder not working**: Requires internet connection to Nominatim service
6. **Template rendering errors**: Check `templates/` directory exists and contains all 3 HTML files
7. **Layers not appearing**: Check browser console for `initializeLayerControl()` errors
8. **Layer control search not working**: Verify JavaScript is enabled, check for console errors
9. **Base maps showing overlay layers**: Check that CSS is hiding `.leaflet-control-layers-overlays`

## Logging System

### Console Output (INFO Level)
Clean, user-friendly messages showing workflow progress:
```
================================================================================
APPEIT MAP CREATOR - Environmental Layer Intersection Tool
================================================================================
Log file: logs/appeit_20250108_143022.log

Configuration loaded: 4 layers defined

Reading input polygon from: C:\Users\lukas\Downloads\pa045_mpb.gpkg
  - Original CRS: EPSG:2272
  - Reprojecting to EPSG:4326...
  ✓ Polygon loaded successfully
...
```

### Log File Output (DEBUG Level)
Detailed information for troubleshooting:
```
2025-01-08 14:30:22 - appeit.core.input_reader - INFO - Reading input polygon from: ...
2025-01-08 14:30:22 - appeit.core.input_reader - DEBUG - File format: GPKG
2025-01-08 14:30:23 - appeit.core.arcgis_query - DEBUG - Querying: https://services3...
2025-01-08 14:30:25 - appeit.core.arcgis_query - INFO - Found 152 intersecting features
...
```

### Log File Location
- Directory: `logs/`
- Filename format: `appeit_YYYYMMDD_HHMMSS.log`
- Encoding: UTF-8
- Retention: Manual (old logs are not automatically deleted)

## Output Structure

Each run creates timestamped directory in `outputs/`:
```
outputs/appeit_map_20250108_143022/
├── index.html                      # Self-contained interactive map (open in browser)
├── metadata.json                   # Query statistics, feature counts, timing
├── PEIT_Report_20250108_143022.pdf # Formatted PDF report
├── PEIT_Report_20250108_143022.xlsx # Excel spreadsheet with feature data
└── data/
    ├── input_polygon.geojson
    ├── rcra_sites.geojson
    ├── npdes_sites.geojson
    ├── navigable_waterways.geojson
    └── historic_places.geojson
```

Timestamped directories prevent overwriting previous runs.

### Report Files

**PDF Report (`PEIT_Report_YYYYMMDD_HHMMSS.pdf`):**
- Professional formatted report using fpdf2
- Cover page with project metadata (name, ID, date)
- Body table with all intersected features organized by category and layer
- Blue hyperlinked Resource Area codes (e.g., 1.4, 1.9, 1.11)
- BMP reference page with clickable URLs to NTIA mitigation guidelines
- Gray page numbers in format "Page X of Y" (excluding cover page)
- Landscape Letter orientation for wide tables
- Text truncation for long area names

**Excel Report (`PEIT_Report_YYYYMMDD_HHMMSS.xlsx`):**
- Tabular format with all feature data
- Columns: Category, Layer Name, Area Name, Resource Areas
- Easy to filter, sort, and analyze in spreadsheet applications

## Interactive Map Features

The generated HTML map includes several interactive features:

### Download Control
- **Location**: Fixed bottom-right corner, shifts with right panel
- **Formats**: GeoJSON, Shapefile (ZIP), KMZ
- **Functionality**:
  - Download individual layers in any format
  - Download all layers at once as a ZIP file
  - Uses embedded GeoJSON data (no CORS issues)
  - Client-side conversion using @mapbox/shp-write and tokml libraries
- **Positioning**: Menu offsets 45px from button in both panel states to prevent overlap

**Shapefile Download Implementation:**
- Uses `@mapbox/shp-write@0.4.3` (official Mapbox fork, JSZip 3.x compatible)
- Requires `outputType: 'blob'` option which returns a Promise
- Both `downloadShapefile()` and `downloadAll()` use `async`/`await` pattern
- Defensive type checking with `instanceof Blob` verification
- Error handling with user-friendly alerts
- Technical details:
  - `shpwrite.zip(geojson, {outputType: 'blob', compression: 'DEFLATE'})` returns Promise<Blob>
  - Must await the Promise before passing to `saveAs()` or `JSZip.file()`
  - Version 0.4.0+ fixed JSZip 3.0 compatibility (old `generate()` → new `generateAsync()`)
  - Fallback error messages show `constructor.name` for debugging

### Dual Collapsible Panel System

#### Left Panel (Legend)
- **Location**: Left side of map
- **Contents**:
  - About section with project information
  - PDF and XLSX report download links (open in new tab with `target="_blank"`)
  - Dynamic legend showing active layers with appropriate symbols:
    - Points: Font Awesome icons with colors
    - Lines: SVG line samples with layer colors
    - Polygons: SVG filled rectangles with layer colors
  - Feature counts for each layer
- **Toggle button**: 20px wide arrow icon (◄/►) to expand/collapse panel
- **Synchronization**: Legend automatically updates to show only visible layers (controlled by right panel)
- **Auto-adjusts**: Left-side Leaflet controls shift 350px when panel is expanded
- **Navigation Handling**: Report links open in new tabs to prevent navigation away from map

#### Right Panel (Layer Control)
- **Location**: Right side of map
- **Contents**:
  - Search box for filtering layers by name, description, or group
  - Grouped layer organization with collapsible groups
  - Group-level checkboxes with state memory
  - Individual layer checkboxes with drag handles (⋮⋮)
  - Feature counts displayed next to layer names
  - Icons and colors matching layer configuration
- **Toggle button**: 20px wide arrow icon (◄/►) to expand/collapse panel
- **Smart visibility**: Only shows groups that contain intersected layers
- **Default state**: All layers visible, all groups expanded, panel open
- **Search functionality**: Real-time filtering across all metadata
- **State management**: Group checkboxes remember individual layer states when toggled
- **Auto-adjusts**: Right-side Leaflet controls shift 350px when panel is expanded

### Map Controls
- **Base Layer Control**: Custom-named base maps (top-right)
  - **Street Map** (OpenStreetMap)
  - **Light Theme** (CartoDB Positron)
  - **Dark Theme** (CartoDB Dark Matter)
  - **Satellite Imagery** (Esri WorldImagery)
  - Uses CSS to hide overlay layers from Folium's LayerControl
  - Only base map radio buttons are visible (human-friendly names)
- **Geocoder**: Search by address or coordinates (top-right, collapsible)
- **Measure Control**: Distance and area measurement (bottom-left)
- **Fullscreen**: Expand map to full screen (top-left)
- **Mouse Position**: Shows current coordinates at cursor location
- **Scale Bar**: Displays in miles
- **Right-Click Coordinate Menu**: Google Maps-style context menu
  - Right-click anywhere on map to show coordinates
  - Click to copy coordinates to clipboard
  - Toast notification confirms copy action
  - Format: `latitude, longitude` (6 decimal places)

### Feature Interactions
- **Popups**: Click features to view all attributes
  - Layer name displayed in italics at top
  - Name field shown in bold below layer name (uses `area_name_field` from config, falls back to first field containing 'name')
  - URLs are automatically converted to clickable links
  - Long URLs are truncated for display
- **Clustering**: Point layers with ≥50 features automatically cluster
- **Hover Effects**: Lines and polygons highlight on mouseover
- **Tooltips**: Non-clustered features show tooltips on hover
- **Layer Z-Index**: Input polygon uses custom pane with z-index 350 (lower than environmental layers at 400)
  - Environmental layers render on top for click priority
  - Users can click environmental polygons directly without toggling off input polygon
  - Input polygon remains visible but doesn't block clicks to overlapping features

### Download Menu Enhancements
- Click header or whitespace to close menu (in addition to clicking outside)
- `event.stopPropagation()` prevents accidental menu closure when clicking buttons
- Menu positioning adapts to right panel state (45px offset)

## ArcGIS REST API Query Parameters

Standard query sent to FeatureServers:
```python
{
    'where': '1=1',                          # No attribute filtering
    'geometry': json.dumps(envelope),        # Bounding box
    'geometryType': 'esriGeometryEnvelope',
    'spatialRel': 'esriSpatialRelIntersects',
    'outFields': '*',                        # All attributes
    'returnGeometry': 'true',
    'f': 'json',                             # JSON format (not geojson)
    'inSR': '4326',                          # Input spatial reference
    'outSR': '4326'                          # Output spatial reference
}
```

Note: Uses `'f': 'json'` (ESRI JSON) not `'f': 'geojson'` because conversion is handled in Python for better control.

## Important Implementation Details

### Metadata Tracking
The `core/arcgis_query.py` module tracks detailed metadata for each query:
- `feature_count`: Final count after client-side filtering
- `bbox_count`: Initial count from bounding box query
- `filtered_count`: Number of features removed by client-side filtering
- `query_time`: Total query time in seconds
- `warning`: Server limit warnings (e.g., "exceededTransferLimit")
- `error`: Error messages if query fails

### File Naming
- Output directories: `appeit_map_YYYYMMDD_HHMMSS`
- GeoJSON files: Layer names sanitized (spaces→underscores, lowercase, special chars removed)
- Example: "RCRA Sites" → `rcra_sites.geojson`
- Log files: `appeit_YYYYMMDD_HHMMSS.log`

### Coordinate System Handling
All data is standardized to EPSG:4326 (WGS84):
- Input polygons auto-reprojected if needed
- Query parameters use `'inSR': '4326', 'outSR': '4326'`
- Web map uses standard Leaflet coordinate system ([lat, lon])

### Import Dependencies
Modules follow strict layering to avoid circular dependencies:
```
config/ → utils/ → core/ → appeit_map_creator.py
```

- Config modules can't import from utils or core
- Utils can't import from core
- Core modules can import from utils and config
- Main file imports from all packages

## Known Limitations

1. **Server Feature Limits**: Most FeatureServers return max 1000-2000 features. Tool displays warning but doesn't paginate.
2. **Internet Required**: No offline mode - requires connection to FeatureServers.
3. **Single Unified Geometry**: Multi-feature files are dissolved into single unified geometry (by design).
4. **No Attribute Filtering**: Downloads all attributes from FeatureServer.
5. **Client-Side Downloads**: Browser-based conversion for SHP/KMZ may have limitations with very large datasets.
6. **Buffer Distance Limits**: Very large buffers (>10,000 feet for points, >5,000 feet for lines) may cause long query times or incomplete results.

## Input Format Support

### File Formats
Automatically handles:
- `.shp` (Shapefile with .shx, .dbf, .prj)
- `.kml` / `.kmz` (Google Earth)
- `.gpkg` (GeoPackage)
- `.geojson` (GeoJSON)
- `.gdb` (FileGeodatabase)

### Geometry Types (NEW)
Enhanced support for multiple geometry types:
- **Points** - Single point or MultiPoint features
- **Lines** - LineString or MultiLineString features
- **Polygons** - Polygon or MultiPolygon features

**Automatic Processing:**
- Points and lines are automatically buffered to create search polygons
- Default buffer: 500 feet (configurable)
- Polygons are used as-is (no buffer applied)
- All outputs standardized to EPSG:4326 (WGS84)

**Multi-Feature Handling:**
- Multiple features automatically dissolved into single unified geometry
- Ensures consistent single-polygon output for intersection queries

## Dependencies

### Python Packages (requirements.txt)
- `geopandas>=0.14.0` - Geospatial data processing
- `folium>=0.15.0` - Interactive Leaflet map generation
- `requests>=2.31.0` - HTTP requests to ArcGIS REST APIs
- `shapely>=2.0.0` - Geometry operations
- `pyproj>=3.6.0` - Coordinate system transformations
- `fiona>=1.9.0` - File format support (SHP, GeoJSON, GPKG, KML, GDB)
- `matplotlib>=3.8.0` - Plotting support
- `branca>=0.7.0` - HTML/JavaScript templating for Folium
- `jinja2>=3.1.0` - Template rendering for UI components
- `fpdf2>=2.8.0` - PDF report generation with Unicode support
- `openpyxl>=3.1.0` - Excel report generation

### Fonts (Bundled)
- **DejaVu Sans family** (Regular, Bold, Oblique, Bold-Oblique)
- Location: `fonts/` directory (~1.5 MB total)
- License: Free license (redistributable)
- Used for: PDF reports with full Unicode character support
- Supports: En-dashes, em-dashes, smart quotes, accented characters, 200+ languages

### Client-Side JavaScript Libraries (CDN)
The HTML map includes these external libraries:
- `@mapbox/shp-write@0.4.3` - Browser-based Shapefile generation (JSZip 3.x compatible)
- `tokml@0.4.0` - GeoJSON to KML conversion
- `jszip@3.10.1` - ZIP file creation for multi-file downloads
- `file-saver@2.0.5` - Browser file downloads
- Font Awesome (via Folium) - Icon fonts for markers

## Git Workflow

- Only push commits to the GitHub remote when explicitly requested
- Only create a commit and push to remote if explicitly requested

## Commit Message Format

- Do NOT include "Generated with Claude Code" attribution
- Do NOT include "Co-Authored-By: Claude" lines
- Keep commit messages clean and professional
- Use clear, descriptive commit messages that explain what changed and why

## Best Practices for Development

### When Modifying Core Modules
1. Update module docstrings if function signatures change
2. Maintain logging statements (INFO for user feedback, DEBUG for details)
3. Test module independently before integration
4. Keep single responsibility - don't mix concerns

### When Modifying Templates
1. Test rendering with sample data
2. Verify JavaScript functionality in browser
3. Check responsive design at different screen sizes
4. Maintain Jinja2 variable naming consistency

### When Adding New Layers
1. Test the FeatureServer URL in browser first
2. Identify correct `layer_id` (usually 0, but can be higher)
3. Choose appropriate `geometry_type` (point/line/polygon)
4. Select Font Awesome icon that matches layer purpose
5. Pick color that contrasts with other layers
6. Assign to an appropriate group (or create a new group)

### VSCode Configuration for Jinja2 Templates
To avoid false TypeScript/JavaScript errors in Jinja2 templates:

**1. Install Better Jinja Extension**
- Extension ID: `samuelcolvin.jinjahtml`
- Provides proper syntax highlighting for `{{ }}` and `{% %}` tags
- Prevents false errors on Jinja2 template variables

**2. Configure File Associations**
Add to VSCode `settings.json`:
```json
{
  "files.associations": {
    "**/templates/*.html": "jinja-html"
  }
}
```

**3. Use `// @ts-nocheck` in Script Tags**
For JavaScript blocks containing Jinja2 syntax, add comment:
```javascript
<script>
    // @ts-nocheck
    const data = {{ jinja_variable|safe }};
</script>
```

This prevents VSCode from showing red squiggles on template syntax while maintaining JavaScript validation for the rest of the code.

### When Updating Dependencies
1. Test with existing test file after updates
2. Verify all geometry types still render correctly
3. Check download functionality (shp-write compatibility)
4. Ensure clustering still works with updated Folium
5. Test Jinja2 template rendering

### Code Organization
- One module = one responsibility
- Helper functions in utils/
- Business logic in core/
- Configuration in config/
- UI templates in templates/
- Keep main file minimal (orchestration only)

### Performance Considerations
- Client-side filtering is fast for <10,000 features
- Clustering prevents browser slowdown with large point datasets
- Embedded GeoJSON avoids CORS but increases HTML file size
- Consider pagination if regularly hitting server feature limits
- Log files can grow large - implement rotation if needed

### Error Handling
- All modules use try/except with proper logging
- Errors propagate to main() for centralized handling
- Log files capture full stack traces
- User sees clean error messages on console

## Module Reference

### config.config_loader
**Purpose**: Load and validate configuration

**Functions**:
- `load_config()`: Load layers_config.json

**Constants**:
- `PROJECT_ROOT`, `CONFIG_DIR`, `OUTPUT_DIR`, `TEMP_DIR`

### core.input_reader
**Purpose**: Read and preprocess input polygons

**Functions**:
- `read_input_polygon(file_path)`: Read polygon and reproject to WGS84

### core.arcgis_query
**Purpose**: Query ArcGIS FeatureServers

**Functions**:
- `query_arcgis_layer(layer_url, layer_id, polygon_geom, layer_name)`: Query single layer

### core.layer_processor
**Purpose**: Batch process multiple layers

**Functions**:
- `process_all_layers(polygon_gdf, config)`: Query all configured layers

### core.map_builder
**Purpose**: Generate interactive Leaflet maps

**Functions**:
- `create_web_map(polygon_gdf, layer_results, metadata, config, input_filename)`: Build complete map

### core.output_generator
**Purpose**: Save output files

**Functions**:
- `generate_output(map_obj, polygon_gdf, layer_results, metadata, output_name)`: Save all outputs

### utils.logger
**Purpose**: Logging configuration

**Functions**:
- `setup_logging(log_dir)`: Initialize logging handlers
- `get_logger(name)`: Get logger instance for module

### utils.geometry_converters
**Purpose**: ESRI JSON to GeoJSON conversion

**Functions**:
- `convert_esri_point(geom, props)`: Convert point geometry
- `convert_esri_linestring(geom, props)`: Convert line geometry
- `convert_esri_polygon(geom, props)`: Convert polygon geometry
- `convert_esri_to_geojson(esri_feature)`: Main converter dispatcher

### utils.html_generators
**Purpose**: Generate HTML/JavaScript code

**Functions**:
- `generate_layer_download_sections(layer_results, config, input_filename)`: Download menu HTML
- `generate_layer_data_mapping(layer_results, polygon_gdf)`: Embedded GeoJSON data

### utils.popup_formatters
**Purpose**: Format popup values

**Functions**:
- `format_popup_value(col, value)`: Format value for HTML popup (handles URLs)

### utils.layer_control_helpers
**Purpose**: Layer grouping and control data generation

**Functions**:
- `organize_layers_by_group(config, layer_results)`: Group layers by their configured group, only including layers with features
- `generate_layer_control_data(groups, layer_results, config)`: Generate structured data for layer control template rendering
- `generate_layer_geojson_data(layer_results, polygon_gdf)`: Create embedded GeoJSON data as JavaScript object for layer management

### utils.pdf_generator
**Purpose**: Generate formatted PDF reports using fpdf2

**Classes**:
- `ReportPDF(FPDF)`: Custom PDF class with landscape orientation, gray page numbers, and footer handling

**Functions**:
- `load_resource_areas(config_dir)`: Load resource area URL mappings from JSON
- `get_category_resource_areas()`: Get mapping of layer categories to resource area codes
- `create_cover_page(pdf, project_name, project_id, report_date)`: Generate cover page with centered metadata
- `create_body_table(pdf, table_rows, url_mapping, category_resources)`: Generate main feature table with hyperlinked resource areas
- `create_bmp_end_page(pdf, resource_links, bmp_master_url)`: Generate BMP reference page with clickable URLs
- `prepare_table_rows(layer_results, config, category_resources)`: Prepare table data from layer results
- `prepare_resource_links(url_mapping)`: Prepare resource area links for BMP page
- `generate_pdf_report(layer_results, config, output_path, timestamp, project_name, project_id)`: Main entry point for PDF generation

**Key Implementation Details**:
- Uses two-pass rendering: first pass calculates total pages, second pass generates final PDF with accurate page numbers
- Manual table rendering allows markdown hyperlinks in cells: `[1.4](url), [1.9](url)`
- Text truncation helper ensures uniform row heights
- Alternating row colors for readability
- Automatic page breaks with header repetition

### utils.xlsx_generator
**Purpose**: Generate Excel reports with feature data

**Functions**:
- `generate_xlsx_report(layer_results, config, output_path, timestamp, project_name, project_id)`: Generate Excel spreadsheet with all feature data

**Features**:
- Tabular format with columns: Category, Layer Name, Area Name, Resource Areas
- Easy to filter and sort in Excel/LibreOffice
- Includes project metadata in first rows

### templates.layer_control_panel
**Purpose**: Right side collapsible panel with grouped layer controls

**Features**:
- Search box for filtering layers
- Grouped layer organization with collapsible groups
- Group-level and individual layer checkboxes
- State management for checkbox states
- Drag handles for visual consistency
- Real-time search filtering
- Chevron icons for expand/collapse
- Synchronized with left panel legend

### templates.side_panel
**Purpose**: Left side collapsible panel with legend

**Features**:
- About section with project information
- Dynamic legend with icons/colors
- Synchronizes with layer visibility from right panel
- Shows only visible layers
- Feature counts for each layer

### templates.download_control
**Purpose**: Download button and menu interface

**Features**:
- Download individual layers (GeoJSON, Shapefile, KMZ)
- Download all layers as ZIP
- Client-side format conversion
- Right-click coordinate copy functionality
- Copy notification toast
- Responsive positioning with panel states
- `// @ts-nocheck` comment to suppress Jinja2 template syntax warnings
