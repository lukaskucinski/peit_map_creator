# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PEIT Map Creator (Permitting and Environmental Information Tool) replicates NTIA's APPEIT tool functionality without requiring an ArcGIS Pro license. It queries ESRI-hosted FeatureServer REST APIs and generates interactive Leaflet web maps showing environmental features that intersect with user-provided polygons.

The project has two deployment modes:
1. **Local CLI**: Run `peit_map_creator.py` directly with a local file
2. **Web Application**: Next.js frontend + Modal.com serverless backend for cloud-based processing

## Architecture

The tool uses a **modular architecture** with separate packages for configuration, core functionality, utilities, and templates.

### Project Structure

```
peit_map_creator/
├── peit_map_creator.py            # Main CLI entry point (~150 lines)
├── peit_map_creator_legacy.py     # Original monolithic version (backup)
├── modal_app.py                   # Modal.com serverless backend
│
├── peit-app-homepage/             # Next.js web frontend (see Web Frontend section)
│   ├── app/                       # Next.js App Router pages
│   ├── components/                # React components
│   ├── lib/                       # API client and utilities
│   └── public/                    # Static assets (icons, images)
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
│   ├── pipeline.py                # Orchestrate geometry workflow
│   └── clipping.py                # Clip result geometries to buffer boundary
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
│   ├── xlsx_generator.py          # Excel report generation
│   └── js_bundler.py              # JavaScript bundling for inline embedding
│
├── templates/
│   ├── __init__.py
│   ├── download_control.html      # Download button UI (Jinja2)
│   ├── side_panel.html            # Left side panel with legend (Jinja2)
│   └── layer_control_panel.html   # Right side panel with grouped layer controls (Jinja2)
│
├── static/                         # Bundled static assets
│   └── js/
│       └── leaflet.pattern.fixed.js  # Fixed Leaflet.pattern library (no CDN dependency)
│
├── logs/                           # Log files (timestamped)
├── images/                         # Images to be used in project
│   ├──/basemap_thumbnails          # Basemap thumbnails folder
├── outputs/                        # Generated maps and data
└── temp/                          # Temporary files
```

### Module Responsibilities

**Main Entry Points:**
- `peit_map_creator.py`: CLI entry point - orchestrates workflow, sets up logging, handles errors
- `modal_app.py`: Serverless backend - FastAPI endpoints for web-based processing

**Configuration:**
- `config/config_loader.py`: Loads and validates `layers_config.json`, loads geometry settings

**Geometry Input (Enhanced):**
- `geometry_input/load_input.py`: Load files, detect geometry types (point/line/polygon)
- `geometry_input/dissolve.py`: Dissolve multi-part geometries, repair invalid geometries
- `geometry_input/buffering.py`: Buffer point/line geometries in projected CRS
- `geometry_input/pipeline.py`: Main entry point - orchestrates complete geometry workflow
- `geometry_input/clipping.py`: Clip query result geometries to buffer boundary

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
- `utils/js_bundler.py`: Load bundled JavaScript files for inline embedding

**Templates:**
- `templates/download_control.html`: Download UI with embedded JavaScript
- `templates/side_panel.html`: Left collapsible panel with legend (syncs with layer visibility)
- `templates/layer_control_panel.html`: Right collapsible panel with grouped layer controls and search

**Static Assets:**
- `static/js/leaflet.pattern.fixed.js`: Fixed Leaflet.pattern library that eliminates L.Mixin.Events deprecation warning

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
- Log files: `logs/peit_YYYYMMDD_HHMMSS.log`

All modules use `utils.logger.get_logger(__name__)` for consistent logging.

### POST Requests Over GET
The tool uses HTTP POST requests to query FeatureServers (not GET) to avoid 414 "URI too long" errors when geometry parameters are complex.

Implementation: `requests.post(query_url, data=params, timeout=60)`

### Polygon Query Strategy (with Smart Heuristic)

The tool uses a **smart query strategy** that automatically selects between polygon queries and envelope (bounding box) queries based on input geometry characteristics. This optimization balances query accuracy with performance.

**Why Polygon Queries?**

With bounding box queries, a discontiguous polygon spanning a large area could return 1000 features (the server limit), but 600+ might be outside the actual polygon. This means features that truly intersect might never be returned because the server limit was hit prematurely.

Polygon queries tell the server exactly which features to return, dramatically reducing false positives and ensuring the server limit is used efficiently.

**Smart Query Selection Heuristic:**

The system automatically chooses the optimal query method based on:
1. **Input area size** (in square miles)
2. **Bounding box fill ratio** (polygon area / bbox area)

Small compact polygons use fast envelope queries; large sparse polygons use precise polygon queries.

| Input Area | Threshold | Behavior |
|------------|-----------|----------|
| < 100 sq mi | 5% | Use envelope for almost everything (fast, won't hit limits) |
| 100-500 sq mi | 5%→50% | Gradually require more compactness for envelope |
| 500-1500 sq mi | 50%→70% | Balanced approach |
| 1500-3000 sq mi | 70%→80% | Large areas need fairly compact shape for envelope |
| 3000-4000 sq mi | 80%→95% | Very large need near-rectangle for envelope |
| > 4000 sq mi | 95% | Only use envelope if nearly perfect rectangle |

**Decision Logic:**
- If `bbox_fill_ratio >= threshold` → Use envelope query (polygon is compact)
- If `bbox_fill_ratio < threshold` → Use polygon query (too much empty space in bbox)

**Query Strategy:**

1. **Polygon Query**: Sends actual polygon geometry in ESRI JSON format
   - Used for sparse/discontiguous polygons where envelope would return too many false positives
   - Automatic simplification if geometry exceeds `max_vertices` (default: 1000)
   - Progressive simplification with topology preservation
   - Falls back to envelope on timeout, error, or unsupported geometry

2. **Envelope Query**: Sends bounding box
   - Used for compact polygons where it's faster and won't hit server limits
   - Always available as fallback if polygon query fails
   - Used when `polygon_query_enabled: false`

3. **Client-side Filtering**: Applied after server query to catch edge cases
   ```python
   gdf = gdf[gdf.intersects(polygon_geometry)]
   ```

**Configuration:**
```json
{
  "geometry_settings": {
    "polygon_query_enabled": true,
    "polygon_query_max_vertices": 1000,
    "polygon_query_simplify_tolerance": 0.0001,
    "polygon_query_fallback_on_error": true
  }
}
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `polygon_query_enabled` | bool | `true` | Enable smart polygon/envelope selection |
| `polygon_query_max_vertices` | int | `1000` | Max vertices before simplification |
| `polygon_query_simplify_tolerance` | float | `0.0001` | Initial simplification tolerance (~11m) |
| `polygon_query_fallback_on_error` | bool | `true` | Fall back to envelope on failure |

Note: The bbox fill threshold is calculated dynamically based on area size - no configuration needed.

**Geometry Simplification:**

Complex polygons are automatically simplified to reduce server processing time:
- Uses Shapely's `simplify(tolerance, preserve_topology=True)`
- Progressive tolerance increase (2x per iteration, up to 5 iterations)
- Maximum tolerance cap at 0.01 degrees (~1.1km) to prevent over-simplification
- Invalid simplified geometries fall back to original
- Simplification is performed ONCE before processing all layers (optimization)

**Area Calculation:**

Area is calculated using latitude-dependent scaling for accuracy:
```python
lat_miles_per_deg = 69.0
lon_miles_per_deg = 69.0 * math.cos(math.radians(lat))
area_sq_miles = area_deg2 * lat_miles_per_deg * lon_miles_per_deg
```

This formula is used consistently in both `geometry_input/buffering.py` and `utils/geometry_converters.py`.

**Metadata Tracking:**

Query method and heuristic details are tracked in metadata:
```json
{
  "query_method": "polygon",
  "query_vertices": 156,
  "simplification_applied": true,
  "original_vertices": 2450,
  "area_sq_miles": 2915.0,
  "bbox_fill_ratio": 0.35,
  "dynamic_threshold": 0.77
}
```

Fallback scenarios include reason:
```json
{
  "query_method": "envelope_fallback",
  "query_fallback_reason": "timeout"
}
```

**Console Output:**
```
Polygon query: disabled (bbox fill 100.0% >= 79% threshold for 2915 sq mi)
  Using envelope queries (more efficient for compact geometries)

  Querying BIA AIAN National LAR...
    - Using envelope query
    - Server returned 45 features
    ✓ Found 45 intersecting features
```

Or for polygon queries:
```
Polygon query: enabled (bbox fill 35.0% < 77% threshold for 2915 sq mi)
  Simplified from 2450 to 156 vertices

  Querying BIA AIAN National LAR...
    - Using polygon query (156 vertices)
    - Server returned 45 features
    ✓ Found 45 intersecting features
```

### Pagination for Server Feature Limits

The tool automatically paginates queries when FeatureServers return the `exceededTransferLimit` flag, indicating that more features exist beyond the server's per-request limit (typically 1000-2000 features).

**How It Works:**

1. **Initial Query**: Normal query with spatial filter
2. **Limit Detection**: If `exceededTransferLimit: true` in response, pagination is triggered
3. **Metadata Check**: Fetches layer metadata to verify `advancedQueryCapabilities.supportsPagination`
4. **Paginated Fetching**: Uses `resultOffset` and `resultRecordCount` with `orderByFields` (ObjectID)
5. **Feature Aggregation**: Combines all pages into single result set

**Configuration:**
```json
{
  "geometry_settings": {
    "pagination_enabled": true,
    "pagination_max_iterations": 10,
    "pagination_total_timeout": 300
  }
}
```

| Setting | Default | Description |
|---------|---------|-------------|
| `pagination_enabled` | `true` | Enable automatic pagination when server limit exceeded |
| `pagination_max_iterations` | `10` | Maximum pages to fetch (10 × 1000 = up to 10,000 features) |
| `pagination_total_timeout` | `300` | Total seconds allowed for all pagination requests (5 min) |

**Console Output Example:**
```
  Querying RCRA Sites...
    - Using polygon query (156 vertices)
    - Page 1: 1000 features (more available)
    - Page 2: 1000 features (more available)
    - Page 3: 532 features (complete)
    ✓ Found 2532 intersecting features (3 pages)
```

**Incomplete Results Handling:**

When pagination is not supported or limits are reached, results are marked as incomplete:

- **Console**: `⚠ WARNING: Results may be INCOMPLETE for this layer`
- **Legend**: Layer name shows "(INCOMPLETE)" suffix in red
- **PDF/XLSX Reports**: Layer names marked with "(INCOMPLETE)"
- **Metadata**: `results_incomplete: true` with `incomplete_reason`

**Incomplete Reasons:**
- `pagination_not_supported`: FeatureServer doesn't support pagination (FileGDB/shapefile backend)
- `max_iterations_reached`: Safety limit hit before fetching all features
- `timeout_exceeded`: Total pagination time exceeded configured timeout
- `error_during_pagination`: Network or server error during page fetching

**Metadata Tracking:**
```json
{
  "layer_name": "RCRA Sites",
  "feature_count": 2532,
  "pagination": {
    "used": true,
    "supports_pagination": true,
    "oid_field": "OBJECTID",
    "max_record_count": 1000,
    "pages_fetched": 3,
    "stopped_reason": null
  },
  "results_incomplete": false
}
```

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
- **Mixed/FeatureCollection** (NEW): Separated by type → each type processed individually → merged into unified polygon

**Mixed Geometry Processing (FeatureCollections):**
When input contains multiple geometry types (e.g., points + lines + polygons from "Draw Your Own" feature):
1. **Separation**: `_separate_geometry_types()` extracts points, lines, and polygons into separate lists
2. **Individual Processing**:
   - Points are unioned and buffered
   - Lines are unioned and buffered
   - Polygons are unioned (no buffer)
3. **Merging**: All resulting polygons combined via `unary_union()` into single unified polygon
4. **Metadata**: `mixed_geometry_processing: true` flag added to track this processing path

This ensures users can draw any combination of geometry types and get proper buffering behavior.

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
    "fallback_crs": "EPSG:5070",
    "clip_results_to_buffer": true,
    "clip_buffer_miles": 0.2,
    "state_filter_enabled": true
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

# Result Geometry Clipping Summary

The Result Geometry Clipping feature automatically clips line and polygon features that extend beyond your input geometry to a configurable buffer distance (default: 1 mile). Point features are unaffected since they can't extend beyond boundaries.

## Configuration

Enable/disable clipping and adjust the buffer distance via `geometry_settings`:

```json
{
  "geometry_settings": {
    "clip_results_to_buffer": true,
    "clip_buffer_miles": 0.2
  }
}
```

## Tracking

The system tracks clipping statistics at both the per-layer level and globally in `metadata.json`, including counts of clipped features and vertex reduction percentages.

## Benefits

- 40-65% reduction in geometry data size
- Faster map loading times
- Smaller HTML output files
- Reduced storage requirements

### State-Based Layer Filtering
The tool optimizes layer processing by detecting which US state(s) the input geometry intersects and only querying layers relevant to those states.

**How it works:**
1. Input geometry is buffered using `clip_buffer_miles` setting (default: 0.2 mile)
2. Buffered geometry is intersected with bundled US state boundaries
3. Layers with a `states` field are filtered to only those matching intersecting states
4. Layers without `states` field (national/federal layers) always run

**Configuration:**
- `geometry_settings.state_filter_enabled`: Enable/disable filtering (default: true)
- Layer-level `states` field: Array of state names the layer applies to

**Performance:**
- Skips ~45-60 irrelevant state layers when input is in a single state
- Reduces total query time significantly for state-specific workflows
- Metadata tracks filter statistics in `state_filter` section

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
- **Timezone Handling**: Report Date converted to US Central (UTC-6) and displayed with timestamp (e.g., "12/15/2025 01:49:13")

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
    'Floodplains': ['1.4', '1.5'],
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

### User Inputs Group (Original Geometry Display)

When non-polygon inputs (points, lines, or mixed FeatureCollections) are processed, the original pre-buffer geometry is displayed on the map alongside the buffered polygon in a "User Inputs" group at the top of the layer control panel.

**Behavior:**
- **Polygon inputs**: Single entry showing `{input_filename}` with gold/orange polygon symbology (no buffer applied)
- **Point/Line/Mixed inputs**: Two entries:
  - `{input_filename}` - Original geometry (dashed lines for lines, star icons for points) - **hidden by default**
  - `{input_filename}_buffered` - Buffered polygon with gold fill
- **Group checkbox**: Toggles all User Inputs layers on/off (like other layer groups)
- **Collapsible**: Group can be collapsed/expanded by clicking the header
- **Searchable**: User Inputs layers appear in search results when filtering by layer name
- **Legend**: No "User Inputs" header in legend - items shown directly without group label

**Visual Design:**
- **Header**: Black text (#333) with gray separator line (#ddd), left-aligned matching other layer groups
- **Symbols**: Stroke width of 3px for better visibility matching map appearance
- **Line features**: Dashed stroke (`dashArray: '10, 5'`), 3px weight, orange color
- **Point features**: Star icon (Font Awesome `fa-star`), orange color
- **Buffered polygon**: Gold fill (#FFD700) with orange stroke (#FF8C00)
- **Mixed (GeometryCollection)**: Each geometry type uses its respective styling
- **Interactivity**: Non-interactive (`interactive: false`), clicks pass through to layers below
- **Z-order**: Original geometry renders ABOVE the buffered polygon (highest in hierarchy)

**Layer Identification:**
- **Original geometry**: Identified by CSS className `'appeit-original-input'` for lines/polygons and marker options `{icon: 'star', color: 'orange'}` for points
- **Buffered polygon**: Identified by CSS className `'appeit-input-polygon'`

**UI Structure (layer_control_panel.html):**
```html
<!-- User Inputs Group -->
<div class="input-geometry-section user-inputs-group">
    <div class="user-inputs-header" onclick="toggleUserInputsExpand()">
        <input type="checkbox" id="user-inputs-group-toggle" checked
               onclick="event.stopPropagation(); toggleUserInputsGroup(this.checked)">
        <label><span class="user-inputs-title">User Inputs</span></label>
        <span class="user-inputs-chevron">▼</span>
    </div>
    <div class="user-inputs-content">
        <!-- Original geometry (only when buffer applied) - unchecked by default -->
        {% if has_original_geometry %}
        <div class="layer-item" data-layer-type="original-input" data-layer-name="{{ input_filename }}">
            <input type="checkbox" id="original-geometry-toggle">
            <!-- SVG/icon for line/point/mixed -->
            <span>{{ input_filename }}</span>
        </div>
        <div class="layer-item" data-layer-type="buffered-input" data-layer-name="{{ buffered_layer_name }}">
            <input type="checkbox" id="input-geometry-toggle" checked>
            <svg><!-- Gold rectangle with stroke-width:3 --></svg>
            <span>{{ input_filename }}_buffered</span>
        </div>
        {% else %}
        <div class="layer-item" data-layer-type="input-polygon" data-layer-name="{{ input_filename }}">
            <input type="checkbox" id="input-geometry-toggle" checked>
            <svg><!-- Gold rectangle with stroke-width:3 --></svg>
            <span>{{ input_filename }}</span>
        </div>
        {% endif %}
    </div>
</div>
```

**JavaScript Functions:**
- `toggleUserInputsGroup(isChecked)`: Toggles all User Inputs layers on/off, remembers individual states
- `toggleUserInputsExpand()`: Toggles collapsed state of User Inputs group
- `filterLayers()`: Updated to include User Inputs items in search results using `data-layer-name` attributes

**Legend Synchronization:**
Legend items for User Inputs use `data-layer-type` attribute (`original-input`, `buffered-input`, `input-polygon`) to sync visibility with layer control toggles via `layerVisibilityChanged` events.

**Output Files:**
When original geometry is present, `data/original_geometry.geojson` is saved alongside `data/input_polygon.geojson`.

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

### Layer Z-Index Management

The tool maintains stable layer rendering order based on the layer list hierarchy in the right panel.

**Hierarchy Rule:**
- Layer list order (top to bottom) = visual hierarchy (top to bottom)
- Input polygon is first in the list → renders on top of all layers
- Environmental layers render in list order below the input polygon
- Last layer in the list renders at the bottom

**Challenge:**
Leaflet's `addLayer()` appends layers to the end of their parent pane's DOM, making re-added layers render on top regardless of their intended position.

**Solution - `restoreLayerOrder()` Function:**
After any layer toggle, the system iterates through all layers in reverse list order and calls `bringToFront()` on each visible layer:

```javascript
function restoreLayerOrder() {
    // Iterate in REVERSE order (bottom of list first)
    // so layers at TOP of list end up on TOP visually
    for (var i = layerOrderList.length - 1; i >= 0; i--) {
        var layer = mapLayers[layerOrderList[i]];
        if (layer && layerStates[layerOrderList[i]] && layer.bringToFront) {
            layer.bringToFront();
        }
    }
    // Input polygon brought to front last (it's first in list)
    if (window.inputPolygonLayer && inputToggle.checked) {
        window.inputPolygonLayer.bringToFront();
    }
}
```

**Implementation Details:**
- `layerOrderList` is built from DOM on initialization (reads layer items in display order)
- Called after `addLayer()` in `toggleLayer()` and `toggleInputGeometry()`
- Also called on initial page load (600ms delay) to ensure correct initial order
- Works with all layer types: GeoJSON, MarkerCluster, FeatureGroup

### JavaScript Initialization Retry Logic

The basemap control uses retry-based initialization to handle variable map rendering times:

- **Initial delay**: 1500ms, then up to 5 retries at 500ms intervals (total window: 1500-3500ms)
- **Purpose**: Prevents race condition where control tries to access `window.map_xxxxx` before Folium finishes rendering
- **Benefit**: Simple maps initialize quickly; complex maps with 60+ features get multiple attempts

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
  "enabled": true,
  "url": "https://services.arcgis.com/.../FeatureServer",
  "layer_id": 0,
  "color": "#HEX_COLOR",
  "icon": "font-awesome-icon-name",
  "icon_color": "red|blue|green|purple|orange|darkred|lightred|beige|darkblue|darkgreen|cadetblue|darkpurple|white|pink|lightblue|lightgreen|gray|black|lightgray",
  "fill_color": "#HEX_COLOR",
  "fill_opacity": 0.5,
  "description": "Layer description",
  "geometry_type": "point|line|polygon",
  "group": "Group Name",
  "states": ["State Name"]
}
```

**Field descriptions**:
- `name`: Display name for the layer (required)
- `enabled`: Whether to process this layer (optional, defaults to `true`). Set to `false` to temporarily disable a layer without removing it from config.
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
- `states`: Array of US state names this layer applies to (optional, used for state-based filtering optimization)

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
- Uses Folium's `StripePattern` plugin with bundled fixed JavaScript
- Bundled `static/js/leaflet.pattern.fixed.js` eliminates L.Mixin.Events deprecation warning
- Fix uses `L.Evented.prototype || L.Mixin.Events` for backward compatibility with Leaflet 2.0
- JavaScript is injected inline into generated HTML (works with `file://` protocol, no external CDN dependency)
- Patterns are rendered as SVG for sharp, scalable display
- Legend automatically shows hatched symbols for patterned layers
- Layer control panel shows hatched symbols matching legend display
- Solid fill layers and patterned layers can coexist in same map
- When `fill_pattern` is present, `fill_color` and `fill_opacity` are ignored

**Backward Compatibility:**
- Polygon layers without `fill_pattern` continue using solid fills
- Existing configurations remain unchanged

### Unique Value Symbology

Point, line, and polygon layers can use **attribute-based styling** to categorize features by field values and assign different icons/colors to each category. This matches ArcGIS Pro's "Unique Values" symbology.

**Use Case:**
Display different colors/icons for features based on an attribute field, such as:
- **Points**: Power plant energy source, facility type, status classification
- **Lines**: Waterway type, road classification, trail designation
- **Polygons**: Ownership classification, land use type, administrative status

**Configuration Examples:**

**Line Layer with Symbology:**
```json
{
  "name": "USACE Navigable Waterway Network",
  "url": "https://geospatial.sec.usace.army.mil/server/rest/services/CPW/CorpsWaterways/FeatureServer",
  "layer_id": 0,
  "color": "#333333",
  "geometry_type": "line",
  "symbology": {
    "type": "unique_values",
    "field": "WTWY_TYPE",
    "categories": [
      {
        "label": "Harbor, Bay",
        "values": ["1"],
        "color": "#4BD64D"
      },
      {
        "label": "River",
        "values": ["2"],
        "color": "#0070FF"
      }
    ],
    "default_category": {
      "label": "Other Waterway",
      "color": "#999999"
    }
  }
}
```

**Polygon Layer with Symbology:**
```json
{
  "name": "USFS Surface Ownership Parcels",
  "url": "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_BasicOwnership_01/MapServer",
  "layer_id": 0,
  "color": "#333333",
  "geometry_type": "polygon",
  "area_name_field": "NAME",
  "symbology": {
    "type": "unique_values",
    "field": "OWNERCLASSIFICATION",
    "categories": [
      {
        "label": "US Forest Service Land",
        "values": ["USDA FOREST SERVICE"],
        "fill_color": "#CCEBC4",
        "fill_opacity": 0.6
      },
      {
        "label": "Non-FS Land",
        "values": ["NON-FS", "UNPARTITIONED RIPARIAN INTEREST"],
        "fill_color": "#FFFFDE",
        "fill_opacity": 0.6
      }
    ],
    "default_category": {
      "label": "Other",
      "fill_color": "#CCCCCC",
      "fill_opacity": 0.4
    }
  }
}
```

**Point Layer with Symbology:**
```json
{
  "name": "EIA - Power Plants",
  "url": "https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/Power_Plants_in_the_US/FeatureServer",
  "layer_id": 0,
  "geometry_type": "point",
  "icon": "bolt",
  "icon_color": "white",
  "area_name_field": "Plant_Name",
  "symbology": {
    "type": "unique_values",
    "field": "PrimSource",
    "categories": [
      {
        "label": "Solar",
        "values": ["solar"],
        "icon": "sun",
        "icon_color": "orange"
      },
      {
        "label": "Natural Gas",
        "values": ["natural gas"],
        "icon": "fire",
        "icon_color": "red"
      },
      {
        "label": "Wind",
        "values": ["wind"],
        "icon": "wind",
        "icon_color": "lightblue"
      }
    ],
    "default_category": {
      "label": "Other",
      "icon": "bolt",
      "icon_color": "gray"
    }
  }
}
```

**Configuration Fields:**
- `symbology.type`: Must be `"unique_values"` for attribute-based styling
- `symbology.field`: Attribute field name to use for categorization
- `symbology.categories`: Array of category definitions
  - `label`: Display name for this category (used in legend and reports)
  - `values`: Array of attribute values that belong to this category
  - **For point layers:**
    - `icon`: Font Awesome icon name (overrides layer-level `icon`)
    - `icon_color`: Marker color (overrides layer-level `icon_color`)
  - **For line layers:**
    - `color`: Line color for this category (hex format, required)
    - `weight`: Line width in pixels (optional, defaults to 3)
    - `opacity`: Line opacity 0.0-1.0 (optional, defaults to 0.8)
  - **For polygon layers:**
    - `fill_color`: Fill color for features in this category (hex format, required)
    - `fill_opacity`: Fill opacity 0.0-1.0 (optional, defaults to 0.6)
    - `border_color`: Border color (optional, defaults to layer-level `color`)
- `symbology.default_category`: Styling for unmapped values (optional)
  - Same fields as regular categories
  - Applied to features whose attribute value doesn't match any category

**Behavior:**
- **Case-insensitive matching**: Attribute values are matched case-insensitively for robustness
- **Multi-value categories**: A single category can match multiple attribute values (e.g., `["NON-FS", "UNPARTITIONED RIPARIAN INTEREST"]`)
- **Default category**: Features with `null` or unmapped values use default category styling
- **No default category**: If no default is specified, unmapped features use layer-level styling (`icon`/`icon_color` for points, `fill_color`/`fill_opacity` for polygons)

**Legend Display:**
Unique value symbology layers show a **header entry** with total count followed by category entries:

**Line Layer Example:**
```
USACE Navigable Waterway Network (324 total)
    ━━━ Harbor, Bay (45)
    ━━━ River (267)
    ━━━ Other Waterway (12)
```

**Polygon Layer Example:**
```
USFS Surface Ownership Parcels (150 total)
    ◻️ US Forest Service Land (120)
    ◻️ Non-FS Land (25)
    ◻️ Other (5)
```

**Point Layer Example:**
```
EIA - Power Plants (89 total)
    ☀️ Solar (23)
    🔥 Natural Gas (45)
    💨 Wind (15)
    ⚡ Other (6)
```

- Header entry shows layer name and total feature count
- Sub-entries show category labels with individual counts (colored icons, lines, or filled rectangles)
- Only categories with features are displayed
- Point categories show Font Awesome icons, line categories show colored line samples, polygon categories show filled rectangles

**Report Integration:**
PDF and Excel reports include category labels in the layer name column:
- Example: `"USFS Surface Ownership Parcels (US Forest Service Land)"`
- Makes it easy to identify which category each feature belongs to

**Priority with Other Styling:**
When multiple styling configurations exist:
1. **Unique value symbology** (highest priority)
2. **Pattern fills**
3. **Solid fills** (lowest priority)

If a layer has both `symbology` and `fill_pattern`, unique value symbology takes precedence.

**Backward Compatibility:**
- Layers without `symbology` field continue using solid fill or pattern fill styling
- All existing layer configurations remain unchanged
- Unique value symbology is opt-in per layer

**Common Configuration Issues:**
- **Field name mismatch**: Verify field names in `concat_fields` match exactly the FeatureServer field names (e.g., `SOVInterest` not `SOVLegalInterest`). Query the FeatureServer metadata to confirm field names.
- **Empty legend categories**: If all category counts are 0, check that configured `values` match actual attribute data. Use the FeatureServer query endpoint to discover actual values.

**SVG Rendering Note:**
Legend and layer control SVG rectangles use `fill-opacity` (not `opacity`) for polygon symbology. This ensures the stroke remains fully opaque while only the fill is transparent, matching Folium/Leaflet map rendering behavior.

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

### Running the CLI Script
```bash
# Activate conda environment
conda activate claude

# Run complete workflow
python peit_map_creator.py
```

The script will:
1. Create a log file in `logs/peit_YYYYMMDD_HHMMSS.log`
2. Display INFO-level progress messages on console
3. Generate output in `outputs/peit_map_YYYYMMDD_HHMMSS/`

### Running the Web Application

**Backend (Modal):**
```bash
# Development (hot reload)
modal serve modal_app.py

# Production deployment
modal deploy modal_app.py
```

**Frontend (Next.js):**
```bash
cd peit-app-homepage

# Install dependencies
npm install

# Development server
npm run dev

# Production deployment to Vercel
npx vercel --prod
```

**Environment Setup:**
Create `peit-app-homepage/.env.local`:
```
NEXT_PUBLIC_MODAL_API_URL=https://lukaskucinski--peit-processor-fastapi-app.modal.run
```

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
Check `outputs/peit_map_TIMESTAMP/metadata.json` for new fields:
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
2. Review `outputs/peit_map_TIMESTAMP/metadata.json` for query statistics
3. Check log file: `logs/peit_TIMESTAMP.log` for DEBUG-level details
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

### Layer Flickering Issue (December 2024) - UNRESOLVED

**Issue:** Some maps (~50%) exhibit layer flickering on hover and side panel disappearing on first load. Manual zoom in/out consistently fixes it. Page refresh recreates the issue.

**Observed Correlation:**
The issue correlates with the ratio of clip buffer distance to input buffer distance:
- 500ft buffer + 1mi clip = issue occurs (ratio ~10.5x)
- 500ft buffer + 0.1mi clip = no issue (ratio ~1x)
- 2mi buffer + 1mi clip = no issue (ratio ~0.5x)

**Mitigation Applied:**
Reduced default clip buffer from 1.0mi to 0.2mi and maximum from 5.0mi to 0.5mi to constrain the ratio and reduce issue occurrence. This is a workaround, not a root cause fix.

**Ruled Out:**
- Hover `highlight_function` is NOT the cause (diagnostic test: disabling had no effect)

#### Attempted Fixes (All Failed)

1. **CSS Isolation for Side Panels** (`templates/side_panel.html`, `templates/layer_control_panel.html`):
   - Added `will-change: transform`, `backface-visibility: hidden`, `contain: layout style` for GPU compositing isolation
   - Added explicit `position: relative; z-index: 1` to panel content areas
   - **Result:** Panel shows white instead of basemap bleed-through, but core flickering persists

2. **forceLayerRedraw() with viewreset + SVG toggle + invalidateSize**:
   - Fire `viewreset` event, toggle SVG display property, call `invalidateSize()`
   - Called at 800ms and 1500ms after page load
   - **Result:** No effect

3. **Simulated User Zoom with Event Cascade**:
   - Fire `movestart` → micro zoom (0.001 level) → restore → fire `moveend`
   - Attempted to replicate the event sequence of manual zoom
   - **Result:** No effect

4. **Synthetic Window Resize Event**:
   - Dispatch `window.dispatchEvent(new Event('resize'))` + `invalidateSize()`
   - Same code path as manual window resize
   - **Result:** No effect

5. **Remove Clip Boundary Constraint from Bounds**:
   - Modified `calculate_optimal_bounds()` to always return full union bounds
   - Hypothesis: SVG renderer initialized with incorrect dimensions when bounds constrained
   - **Result:** No effect (issue persists even with full bounds)

6. **Disable Hover highlight_function**:
   - Commented out highlight_function entirely
   - **Result:** No effect (ruled out hover as cause)

#### Hypotheses and Future Fix Ideas

1. **Leaflet SVG Renderer Race Condition**:
   - SVG may not complete initial render before first paint
   - Manual zoom triggers internal redraw mechanisms
   - **To try:** Force SVG redraw via direct DOM manipulation after all layers loaded

2. **Folium Layer Wrapper Interference**:
   - Folium wraps layers in additional containers that may interfere with Leaflet's layer management
   - **To try:** Inspect generated HTML for wrapper layer differences between working/broken maps

3. **Canvas Renderer Instead of SVG**:
   - Leaflet supports Canvas renderer which may handle complex scenes better
   - **To try:** `L.map('map', { preferCanvas: true })`
   - **Caveat:** Requires Folium configuration changes, may affect layer styling

4. **Lazy Layer Loading**:
   - Add layers progressively after initial map render
   - **To try:** Delay adding complex polygon layers until after basemap tiles load

5. **Browser-Specific SVG Bugs**:
   - Issue reported on Chrome and Edge (both Chromium-based)
   - **To try:** Test on Firefox/Safari to narrow down if browser-specific

6. **Compare Working vs Broken Maps**:
   - Do detailed HTML diff between maps that work and maps that break
   - Look for differences in layer order, feature counts, CSS classes applied

7. **Leaflet GitHub Issues to Monitor**:
   - [#5960](https://github.com/Leaflet/Leaflet/issues/5960): SVG renderer loses width/height attributes
   - [#8361](https://github.com/Leaflet/Leaflet/issues/8361): Controls disappear on hover with many features
   - [#5207](https://github.com/Leaflet/Leaflet/issues/5207): Layers don't display until window resize

## Logging System

### Console Output (INFO Level)
Clean, user-friendly messages showing workflow progress:
```
================================================================================
PEIT MAP CREATOR - Environmental Layer Intersection Tool
================================================================================
Log file: logs/peit_20250108_143022.log

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
2025-01-08 14:30:22 - peit.core.input_reader - INFO - Reading input polygon from: ...
2025-01-08 14:30:22 - peit.core.input_reader - DEBUG - File format: GPKG
2025-01-08 14:30:23 - peit.core.arcgis_query - DEBUG - Querying: https://services3...
2025-01-08 14:30:25 - peit.core.arcgis_query - INFO - Found 152 intersecting features
...
```

### Log File Location
- Directory: `logs/`
- Filename format: `peit_YYYYMMDD_HHMMSS.log`
- Encoding: UTF-8
- Retention: Manual (old logs are not automatically deleted)

## Output Structure

Each run creates timestamped directory in `outputs/`:
```
outputs/peit_map_20250108_143022/
├── index.html                      # Self-contained interactive map (open in browser)
├── metadata.json                   # Query statistics, feature counts, timing
├── PEIT_Report_20250108_143022.pdf # Formatted PDF report
├── PEIT_Report_20250108_143022.xlsx # Excel spreadsheet with feature data
└── data/
    ├── input_polygon.geojson       # Buffered search polygon (or original if polygon input)
    ├── original_geometry.geojson   # Pre-buffer geometry (only for point/line/mixed inputs)
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

### Page Title and Favicon
- **Dynamic Title**: Browser tab shows "PEIT Map - {Project Name}" when project name is provided, otherwise "PEIT Map"
- **Favicon**: Embedded inline PNG favicons with light/dark mode support via media queries
  - Light mode: Black map layers icon (`icon-light-48x48.png`)
  - Dark mode: White map layers icon (`icon-dark-48x48.png`)
- **Self-contained**: Both title and favicon are embedded in the HTML, working with file://, blob URLs, and downloaded ZIPs

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
- **Dynamic height**: Legend section uses flexbox to automatically expand when About section is collapsed, eliminating dead white space

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
- **Search functionality**: Real-time filtering across layer name, description, group, and subcategory labels (for layers with unique value symbology)
- **State management**: Group checkboxes remember individual layer states when toggled
- **Auto-adjusts**: Right-side Leaflet controls shift 350px when panel is expanded

#### Mobile Responsiveness
- On screens ≤768px wide, both panels are collapsed by default to maximize map visibility
- Users can still expand panels by clicking the toggle buttons
- Desktop behavior unchanged (panels open by default)
- Leaflet controls adjust position based on panel state
- CSS media queries handle initial visual state; JavaScript syncs body classes and toggle icons

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
  - Layer name displayed in italics at top with hyperlinked resource area codes in parentheses
    - Example: `GSA Federal Real Property (1.7, 1.8)` where codes link to NTIA BMP PDFs
    - Resource areas derived from layer's `group` field using `get_category_resource_areas()` mapping
    - Links open in new tabs (`target="_blank"`)
  - Name field shown in bold below layer name (uses `area_name_field` from config, falls back to first field containing 'name')
  - URLs are automatically converted to clickable links
  - Long URLs are truncated for display
  - **Mobile sizing**: On screens ≤768px, popups constrained to 50vh height and 85vw width
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
- `feature_count`: Final count after client-side filtering and clipping
- `bbox_count`: Initial count from bounding box query
- `filtered_count`: Number of features removed by client-side filtering
- `clipping`: Clipping statistics (if clipping was applied to lines/polygons)
- `query_time`: Total query time in seconds
- `warning`: Server limit warnings (e.g., "exceededTransferLimit")
- `error`: Error messages if query fails

### File Naming
- Output directories: `peit_map_YYYYMMDD_HHMMSS`
- GeoJSON files: Layer names sanitized (spaces→underscores, lowercase, special chars removed)
- Example: "RCRA Sites" → `rcra_sites.geojson`
- Log files: `peit_YYYYMMDD_HHMMSS.log`

### Coordinate System Handling
All data is standardized to EPSG:4326 (WGS84):
- Input polygons auto-reprojected if needed
- Query parameters use `'inSR': '4326', 'outSR': '4326'`
- Web map uses standard Leaflet coordinate system ([lat, lon])

### Import Dependencies
Modules follow strict layering to avoid circular dependencies:
```
config/ → utils/ → core/ → peit_map_creator.py
```

- Config modules can't import from utils or core
- Utils can't import from core
- Core modules can import from utils and config
- Main file imports from all packages

## Known Limitations

1. **Server Feature Limits**: Most FeatureServers return max 1000-2000 features per request. **Pagination is supported** to automatically fetch all features, but some older FeatureServers (backed by FileGDB/shapefiles) don't support pagination. Incomplete results are marked with "(INCOMPLETE)" suffix.
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

## Commit Message and PR Format

- Do NOT include "Generated with Claude Code" attribution in commits or PRs
- Do NOT include "Co-Authored-By: Claude" lines
- Do NOT include emoji robot icons (🤖) with Claude attribution
- Keep commit messages and PR descriptions clean and professional
- Use clear, descriptive messages that explain what changed and why

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
**Purpose**: Query ArcGIS FeatureServers with pagination support

**Functions**:
- `fetch_layer_metadata(layer_url, layer_id, timeout)`: Fetch layer metadata to check pagination support and find ObjectID field
- `paginated_query(query_url, base_params, oid_field, max_record_count, layer_name, max_iterations, total_timeout, request_timeout)`: Execute paginated query to fetch all features beyond server limit
- `query_arcgis_layer(layer_url, layer_id, polygon_geom, layer_name, clip_boundary, geometry_type, use_polygon_query, esri_polygon_json, polygon_query_metadata, pagination_enabled, pagination_max_iterations, pagination_total_timeout)`: Query single layer with optional clipping and pagination

### core.layer_processor
**Purpose**: Batch process multiple layers

**Functions**:
- `process_all_layers(polygon_gdf, config)`: Query all configured layers, returns (results, metadata, clip_summary)

### geometry_input.clipping
**Purpose**: Clip query result geometries to buffer boundary

**Functions**:
- `create_clip_boundary(input_geom, buffer_miles, original_crs)`: Create buffered clip boundary
- `clip_geodataframe(gdf, clip_boundary, layer_name, geometry_type)`: Clip geometries in GeoDataFrame
- `aggregate_clip_metadata(layer_metadata_list)`: Aggregate clipping statistics across layers
- `count_vertices(geometry)`: Count vertices in any geometry type
- `extract_geometry_type(geometry, target_type)`: Extract specific geometry types from GeometryCollection

### core.map_builder
**Purpose**: Generate interactive Leaflet maps

**Functions**:
- `generate_popup_resource_links(group, category_resource_areas, resource_area_urls)`: Generate HTML hyperlinks for resource area codes based on layer group for popup display
- `calculate_optimal_bounds(polygon_gdf, layer_results, clip_boundary)`: Calculate optimal viewport bounds encompassing all visible features
- `create_web_map(polygon_gdf, layer_results, metadata, config, input_filename, project_name, xlsx_relative_path, pdf_relative_path, clip_boundary)`: Build complete map with dynamic title and embedded favicon

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
**Purpose**: ESRI JSON to GeoJSON conversion and geometry utilities

**Functions**:
- `convert_esri_point(geom, props)`: Convert point geometry
- `convert_esri_linestring(geom, props)`: Convert line geometry
- `convert_esri_polygon(geom, props)`: Convert polygon geometry
- `convert_esri_to_geojson(esri_feature)`: Main converter dispatcher
- `shapely_to_esri_polygon(geom)`: Convert Shapely Polygon/MultiPolygon to ESRI JSON format for server queries
- `count_geometry_vertices(geom)`: Count total vertices in Polygon or MultiPolygon
- `simplify_for_query(geom, max_vertices, tolerance, max_tolerance)`: Progressively simplify geometry for server queries

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
- About section with project information and hyperlinks to PEIT Map Creator and APPEIT
- Dynamic creation date (US Central timezone, MM/DD/YYYY format without leading zeros)
- Buy Me a Coffee button linking to https://buymeacoffee.com/kucimaps
- PDF and XLSX report download links
- Dynamic legend with icons/colors
- Synchronizes with layer visibility from right panel
- Shows only visible layers
- Feature counts for each layer

**Creation Date Implementation**:
The creation date is rendered at map generation time using US Central timezone (UTC-6) to ensure consistent dates across local Windows development and Modal Linux containers. The date is embedded as static text in the HTML, so it shows when the map was created, not when it's viewed.

```python
# In core/map_builder.py
us_central = timezone(timedelta(hours=-6))
now_central = datetime.now(us_central)
creation_date = f"{now_central.month}/{now_central.day}/{now_central.year}"  # e.g., "12/6/2025"
```

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

---

## Web Frontend (peit-app-homepage)

The web frontend is a Next.js 16 application providing a user-friendly interface for uploading geospatial files and processing them via the Modal backend.

### Tech Stack
- **Framework**: Next.js 16 with App Router
- **Styling**: Tailwind CSS + shadcn/ui components
- **Deployment**: Vercel
- **API Client**: Custom TypeScript client with SSE support

### Key Components

**`components/upload-card.tsx`**
- Drag-and-drop file upload zone
- File validation (type, size)
- Visual feedback for upload states
- "Draw Your Own!" button to launch interactive map drawing
- **Geometry preview**: When file is selected, shows SVG geometry preview as subtle background watermark
- **Edit Drawing button**: For drawn geometries, displays "Edit Drawing" button to return to map drawer with existing geometry loaded
- **Green globe icon**: File selected state shows green globe with checkmark badge

**`components/geometry-preview.tsx`**
- SVG-based geometry preview component (no basemap, abstract representation)
- Renders GeoJSON features as SVG paths (polygons, lines, points)
- Theme-aware styling (works in light/dark mode)
- Uses `lib/geometry-svg.ts` for coordinate projection

**`lib/geometry-svg.ts`**
- Utilities for converting GeoJSON to SVG paths
- `calculateBBox()`: Calculate bounding box from GeoJSON
- `projectToSVG()`: Project geographic coordinates to SVG space (flips Y-axis)
- `featureToSVGElements()`: Convert GeoJSON features to SVG path data

**`components/map-drawer.tsx`**
- Interactive map for drawing custom geometries
- Full-screen overlay below header
- Leaflet-Geoman integration for drawing tools (polygon, polyline, rectangle, marker)
- Address/coordinate search using Nominatim geocoder
- Base map selector (Street, Light, Dark, Satellite)
- Converts drawn geometries to GeoJSON file for processing pipeline
- **Initial geometry loading**: Accepts `initialGeometry` prop to pre-populate feature group for editing existing drawings
- **Mobile CSS customizations**: On mobile (≤768px), drawing action buttons (Finish, Remove Last Vertex, Cancel) stack vertically below the tool icon instead of horizontally. Defined in `app/globals.css`.

**`components/map-drawer-dynamic.tsx`**
- Dynamic import wrapper with `ssr: false` for Leaflet compatibility
- Loading state with centered spinner

**`components/config-panel.tsx`**
- Project name and ID inputs with tooltips explaining their purpose
- Buffer distance configuration (hidden for polygon inputs since polygons don't get buffered)
  - Minimum: 1ft (prevents empty geometries from 0ft buffer on points/lines)
  - Maximum: 5,280ft (1 mile)
  - Default: 500ft
  - Slider step: 100ft increments (slider label shows 1ft minimum)
  - Clickable value: Click the ft value to manually enter exact buffer distance
  - Auto-correction: If buffer is 0 for non-polygon geometry (e.g., restored from previous polygon session), auto-corrects to 500ft
- Clip buffer distance slider with tooltip
  - Minimum: 0.1 mi (cannot be 0)
  - Maximum: 0.5 mi
  - Default: 0.2 mi
  - Clickable value: Click the mi value to manually enter exact clip distance
- Real-time area estimation based on geometry and buffer settings
- Area validation against 500 sq mi limit with warning at 250 sq mi
- Uses `LabelWithTooltip` helper component for consistent tooltip UI

**`components/processing-status.tsx`**
- Real-time progress display via SSE
- Layer-by-layer processing status
- "View Live Map" button - opens shareable map URL in new tab
- "Download ZIP" button - downloads full results package
- "Copy" button - copies shareable URL to clipboard
- Direct PDF/XLSX report links
- Expiration notice (7 days)

**`components/dashboard/job-history-list.tsx`**
- Renders job cards in Map History dashboard
- Search bar filters by run ID, project name, project ID, or filename
- Displays: project name, project ID, filename, status, timestamps, feature/layer counts, input area
- Input area displayed for completed jobs as "Area: X sq mi" (1 decimal place precision, shown under Features/Layers)
- Only shown for completed jobs with non-null area values
- Run ID (16-char job ID) shown in monospace font with copy-to-clipboard button and auto-dismissing toast (3s)
- Action buttons: View Map, Download ZIP, PDF, Excel (for completed jobs)
- Delete button with confirmation dialog
- Expiration countdown

**`components/header.tsx`**
- Site navigation and branding
- GitHub and Donations links
- Responsive mobile layout
- Shows Sign In/Sign Up buttons or UserMenu based on auth state

**`components/footer.tsx`**
- Minimal footer with Terms of Service and Privacy Policy links
- Copyright notice with dynamic year
- Centered layout, muted text styling
- Responsive (stacks vertically on mobile)

### Authentication (Supabase)

User authentication via Supabase with OAuth and email/password options.

**Auth Components:**
- `components/auth/auth-modal.tsx`: Sign in/sign up dialog with Google, GitHub OAuth and email/password. **Terms acceptance required**: On sign-up tab, users must accept Terms of Service and Privacy Policy checkbox before signing up (applies to both OAuth and email sign-up).
- `components/auth/user-menu.tsx`: Avatar dropdown with Map History, Account Settings, Sign Out. Uses OAuth provider avatar and display name from `user.user_metadata`. Uses Tooltip + DropdownMenu composition with `<span>` wrapper to avoid nested button hydration errors.

**Account Components:**
- `components/account/delete-account.tsx`: Account deletion with email confirmation

**Theme Components:**
- `components/theme-provider.tsx`: Wraps next-themes ThemeProvider for dark mode support
- `components/theme-toggle.tsx`: Theme toggle button (dropdown) and ThemeSelector (button group for Account Settings)

**Routes:**
- `app/auth/callback/route.ts`: OAuth callback handler
- `app/dashboard/page.tsx`: Map History page (authenticated users only)
- `app/account/page.tsx`: Account settings page (profile info, theme settings, account deletion)
- `app/terms/page.tsx`: Terms of Service page (static, public)
- `app/privacy/page.tsx`: Privacy Policy page (static, public)

**Supabase Client Files (`lib/supabase/`):**
- `client.ts`: Browser client for client components
- `server.ts`: Server client for server components
- `middleware.ts`: Middleware client for session refresh

**Proxy (`proxy.ts`):**
- Next.js 16 renamed `middleware.ts` → `proxy.ts` convention
- Refreshes Supabase auth sessions on each request
- Runs on all routes except static assets

**Database Tables:**

**`jobs` table** - Stores job processing records with RLS policies filtering by `user_id`.

| Column | Type | Description |
|--------|------|-------------|
| `input_area_sq_miles` | REAL | Square mileage of input geometry (after buffering) |
| `execution_time_seconds` | REAL (generated) | Auto-computed from `completed_at - created_at` |

**`user_stats` table** - Aggregated map creation statistics per user, auto-updated via triggers.

| Column | Type | Description |
|--------|------|-------------|
| `user_id` | UUID (PK) | References auth.users(id), cascades on delete |
| `maps_created` | INTEGER | Total maps started by user |
| `maps_completed` | INTEGER | Maps that finished successfully |
| `maps_failed` | INTEGER | Maps that failed during processing |
| `total_features_processed` | BIGINT | Sum of features across completed maps |
| `first_map_at` | TIMESTAMPTZ | User's first map creation timestamp |
| `last_map_at` | TIMESTAMPTZ | User's most recent map creation timestamp |
| `updated_at` | TIMESTAMPTZ | Last stats update timestamp |

- Trigger `trigger_update_user_stats` fires on INSERT/UPDATE/DELETE of `jobs` table
- Stats updated when: job created, job claimed, job completed, job failed, job deleted
- RLS policy ensures users can only view their own stats

**Profile Display:**
Avatar and display name come directly from OAuth provider (`user.user_metadata`). No custom profile editing - users see their Google/GitHub profile automatically.

**Supabase URL Configuration:**
The following redirect URLs are configured in Supabase Dashboard → Authentication → URL Configuration:
- `https://peit-map-creator.com/**` (production)
- `https://www.peit-map-creator.com/**` (www subdomain)
- `http://localhost:3000/**` (local development)

All URLs use wildcard patterns to allow OAuth callbacks to work correctly in each environment.

Avatar URL lookup order (different providers use different field names):
- `user.user_metadata.avatar_url` (GitHub)
- `user.user_metadata.picture` (Google)

Display name lookup order:
- `user.user_metadata.full_name`
- `user.user_metadata.name`
- Email prefix as fallback

**Mobile Authentication:**
Sign in/sign up buttons are hidden on mobile to save space. A User icon button (`sm:hidden`) opens the auth modal, matching the icon-only pattern used by GitHub and Donations buttons on mobile.

**Anonymous Job Claiming:**
Anonymous users can process files and later claim jobs by signing up:
- Jobs created without auth have `user_id=NULL`
- On completion, job ID stored in localStorage (`lib/pending-jobs.ts`)
- Complete screen state preserved in sessionStorage (survives OAuth redirect)
- `ClaimJobPrompt` dialog appears on mouse move/touch after job completion
- On sign-in, `POST /api/claim-jobs` associates pending jobs with user
- Toast confirms "Map saved to your history!"

**Navigation State Management:**
SessionStorage preserves the "Processing Complete" screen across OAuth redirects, but must be cleared on intentional navigation to prevent stale state:
- Header logo click (`components/header.tsx`): Navigates to `/?reset=1` which triggers state reset in `app/page.tsx`. The `?reset=1` query parameter signals the HomePage to clear sessionStorage and reset all React state to 'upload'. URL is then cleaned up via `router.replace('/')`.
- Dashboard "+ New Map" button (`app/dashboard/page.tsx`): Uses `href="/?reset=1"` to ensure fresh upload state
- Account "Back to Home" button (`app/account/page.tsx`): Uses `href="/?reset=1"` to ensure fresh upload state
- Sign out (`components/auth/user-menu.tsx`): Calls `clearCompleteState()` before signing out and redirecting to home
- Sign out event (`app/page.tsx`): `onAuthStateChange` listens for `SIGNED_OUT` event and resets `appState` to 'upload'
- "Process Another" button (`app/page.tsx`): Calls `clearCompleteState()` when starting a new run

**IMPORTANT:** All navigation links that should return users to a fresh upload state MUST use `/?reset=1` instead of just `/`. This includes any "+ New Map", "Back to Home", or similar navigation elements.

**Why `?reset=1` for header logo:**
Client-side navigation via Next.js Link doesn't remount the HomePage component - it only re-renders with existing state. The `?reset=1` query parameter provides a reliable signal that triggers a useEffect to clear storage and reset state, ensuring the logo click always works regardless of the current page state.

**Error State Preservation:**
When processing fails (rate limit, network error, etc.), file and configuration are preserved for retry:

- **"Try Again" button** (`handleTryAgain` in `app/page.tsx`): Returns to configure step with file and config preserved (does NOT reset to upload)
- **"Start Fresh" link**: Calls `handleProcessAnother` to reset completely for users who want a different file
- **Auth redirect from error state**: Error state saved to sessionStorage; on sign-in, restored to configure step
  - For drawn geometries: Fully restored (File regenerated from saved GeoJSON)
  - For uploaded files: Fully restored (File contents stored as base64, then decoded back to File)
  - Fallback: If base64 storage fails (quota exceeded), config restored, user prompted to re-select file

Storage functions in `lib/pending-jobs.ts`:
- `saveErrorState()`: Async function that saves filename, config, GeoJSON (for drawn), geometrySource, locationData, and file contents as base64 (for uploaded files)
- `getErrorState()`: Retrieves error state (expires after 1 hour)
- `clearErrorState()`: Clears stored error state
- `base64ToFile()`: Converts base64 string back to File object

Key files:
- `lib/pending-jobs.ts`: localStorage/sessionStorage utilities
- `components/claim-job-prompt.tsx`: Sign-up prompt dialog
- `modal_app.py`: `/api/claim-jobs` endpoint

**Dependencies:**
- `@supabase/supabase-js` - Supabase client
- `@supabase/ssr` - Server-side rendering support

### Welcome Email

New users receive a branded welcome email when they sign up (via any method: OAuth or email/password).

**Implementation:**
- **Supabase Edge Function**: `supabase/functions/send-welcome-email/index.ts`
- **Database Trigger**: `on_auth_user_created_welcome_email` on `auth.users` table
- **Email Service**: Resend API (free tier: 100 emails/day)
- **Sender**: `noreply@peit-map-creator.com`

**How it works:**
1. User signs up (OAuth or email/password)
2. Supabase inserts row into `auth.users` table
3. PostgreSQL trigger `on_auth_user_created_welcome_email` fires
4. Trigger calls Edge Function via `pg_net` HTTP POST
5. Edge Function sends branded HTML email via Resend API

**Email Content:**
- Logo linked to app homepage
- Personalized greeting (uses `full_name` from OAuth metadata if available)
- Feature highlights (maps, history, reports)
- "Start Creating" CTA button
- Clean, modern styling with system fonts

**Configuration:**
- Resend API key stored as Supabase secret: `RESEND_API_KEY`
- Domain `peit-map-creator.com` verified in Resend dashboard
- Edge Function deployed with `--no-verify-jwt` flag (called by database trigger, not authenticated users)

**Maintenance:**
- To update email template: Edit `supabase/functions/send-welcome-email/index.ts` and redeploy:
  ```bash
  cd peit-app-homepage
  npx supabase functions deploy send-welcome-email --no-verify-jwt
  ```
- To disable welcome emails: Drop the trigger in Supabase SQL Editor:
  ```sql
  DROP TRIGGER IF EXISTS on_auth_user_created_welcome_email ON auth.users;
  ```

### Dark Mode

The app supports light, dark, and system themes using `next-themes`.

**How it works:**
- Theme preference stored in `localStorage` (persists across sessions, even when logged out)
- First visit: Uses system/OS preference
- After explicit selection: User's choice overrides system preference
- Different device: Falls back to system preference (localStorage is per-browser)

**Components:**
- `ThemeProvider` in `app/layout.tsx`: Wraps app with next-themes provider
- `ThemeSelector` in Account Settings: Button group to choose System/Light/Dark
- `ThemeToggle`: Dropdown button component (available for use elsewhere if needed)

**Configuration:**
```typescript
// app/layout.tsx
<ThemeProvider
  attribute="class"
  defaultTheme="system"
  enableSystem
  disableTransitionOnChange
>
```

**CSS Variables:**
Theme colors defined in `app/globals.css`:
- `:root` - Light mode colors (oklch format)
- `.dark` - Dark mode colors (oklch format)

**Map Drawer Integration:**
- Map controls (search input, basemap selector) use fixed light styling (`bg-white text-gray-900`) to ensure readability on map tiles
- Default basemap automatically switches to "Dark Theme" when app is in dark mode
- User can still manually change basemap; theme-based default only applies on initial load

**Dependencies:**
- `next-themes@0.4.6` - Theme management with SSR support

### Draw Your Own Feature

Users can draw custom geometries on an interactive map instead of uploading a file:

**Frontend Flow:**
1. User clicks "Draw Your Own!" button on upload card
2. Full-screen map appears with Leaflet-Geoman drawing tools
3. User draws polygons, lines, and/or points
4. Clicking "Use This Geometry" converts drawings to GeoJSON file
5. File is passed to config panel like any uploaded file

**Geometry Processing:**
- Polygons: Used as-is (no buffering)
- Lines: Buffered by configured distance (default 500 ft)
- Points: Buffered by configured distance (default 500 ft)
- Mixed types (FeatureCollection): Separated, buffered individually, merged into unified polygon

**Dependencies:**
- `leaflet` - Map rendering
- `react-leaflet` - React bindings for Leaflet
- `@geoman-io/leaflet-geoman-free` - Drawing tools

**Utility Functions (`lib/geojson-utils.ts`):**
- `layersToGeoJSON()`: Convert Leaflet layers to GeoJSON FeatureCollection
- `geojsonToFile()`: Convert GeoJSON to File object
- `validateDrawnGeometry()`: Ensure geometry is valid and non-empty
- `getGeometrySummary()`: Generate human-readable geometry summary
- `detectGeometryType()`: Detect primary geometry type (polygon/line/point/mixed)
- `calculatePolygonAreaSqMiles()`: Calculate area of polygon features using Turf.js
- `estimateBufferedAreaSqMiles()`: Estimate area after applying buffer to all geometry types
- `validateGeometryArea()`: Validate area against limits (5,000 sq mi max, 2,500 sq mi warning)
- `reverseGeocodePoint()`: Geocode a single lat/lon coordinate via backend proxy (avoids CORS)
- `reverseGeocodeGeometry()`: Geocode a GeoJSON FeatureCollection's centroid via backend proxy

**Area Validation Constants:**
- `MAX_AREA_SQ_MILES`: 5,000 sq mi - Maximum allowed area
- `WARN_AREA_SQ_MILES`: 2,500 sq mi - Warning threshold for large areas

**Background Geocoding:**
To eliminate perceived delay when clicking "Use This Geometry", geocoding runs in the background:
- **First vertex**: When user places first point of a polygon/line, geocoding starts immediately
- **Marker creation**: When user places a standalone point marker, geocoding starts on creation
- **Edit mode**: When editing existing geometry, geocoding runs on initial load using the centroid
- **Caching**: Results are cached in a ref (not state) to avoid stale closure issues; "Use This Geometry" uses cached result instantly
- **Fallback**: If geocoding hasn't completed, waits briefly (max 3s) or geocodes synchronously
- **Clear All**: Resets geocoding state so next drawing session triggers fresh geocode

**Leaflet-Geoman Event Handling:**
- `pm:vertexadded` fires on the **workingLayer** (the layer being drawn), NOT on the map
- Must attach listener inside `pm:drawstart` handler via `e.workingLayer.on('pm:vertexadded', ...)`
- Markers don't fire `pm:vertexadded`; use `pm:create` with `instanceof L.Marker` check instead
- Refs (not state) used for caching to avoid React closure stale-value issues in callbacks

### Map Viewer Routes

**`app/maps/[jobId]/route.ts`**
- Server-side route that fetches and serves map HTML from Vercel Blob
- Validates job ID format (16 hex chars)
- Uses `@vercel/blob` `list()` to find blob by prefix
- Returns HTML with `Cache-Control: private, no-store` to ensure deletions take effect immediately
- Redirects to `/maps/expired` if blob not found

**`app/maps/expired/page.tsx`**
- Static page displayed when map link has expired or is invalid
- Shows "Map Expired" message with Clock icon
- Links back to homepage to create new map

**URL Format:** `https://peit-map-creator.com/maps/{jobId}`

### API Client (`lib/api.ts`)
TypeScript client for the Modal backend:
- `checkHealth()`: Verify backend availability
- `getRateLimitStatus()`: Check daily run limits
- `processFile()`: Upload and process file with SSE progress streaming
- `claimJobs()`: Claim unclaimed jobs for authenticated user
- `deleteJob()`: Delete a job and all associated storage (requires ownership)
- `reverseGeocode()`: Proxy reverse geocoding to Nominatim via backend (avoids CORS)

### File Validation (`lib/validation.ts`)
- **Allowed Extensions**: `.geojson`, `.json`, `.gpkg`, `.kml`, `.kmz`, `.zip`
- **Max File Size**: 5MB
- Provides user-friendly error messages

### Client-Side File Parsing (`lib/file-parsers.ts`)
Parses geospatial files in the browser for area estimation and geometry type detection before upload.

**Supported Formats:**
| Format | Library | Notes |
|--------|---------|-------|
| GeoJSON (.geojson, .json) | Native JSON.parse | Handles FeatureCollection, Feature, and raw Geometry |
| Shapefile (.shp, .zip) | `shpjs` | Merges multi-layer ZIPs into single FeatureCollection |
| KML (.kml) | `@tmcw/togeojson` | XML parsing via DOMParser |
| KMZ (.kmz) | `@tmcw/togeojson` + `jszip` | Extracts KML from ZIP archive |
| GeoPackage (.gpkg) | `@ngageoint/geopackage` | WASM-based SQLite, lazy-loaded from unpkg CDN |

**GeoPackage Implementation Details:**
The GeoPackage parser uses `@ngageoint/geopackage` which bundles sql.js (SQLite compiled to WebAssembly). Key implementation notes:

1. **WASM Loading**: Configured via `setSqljsWasmLocateFile()` to load from unpkg CDN
2. **Browser Compatibility**: Requires Turbopack/webpack aliases for Node.js modules (`fs`, `path`, `crypto`) that sql.js tries to import
3. **Raw SQL Queries**: Uses `geoPackage.connection.all()` for reliable data access (DAO methods have API inconsistencies)
4. **Geometry Parsing**: Uses `GeometryData.fromData()` to parse GeoPackage geometry blobs (GP header + WKB)
5. **WKB Fallback**: If WKB parsing fails (unsupported encoding), falls back to envelope bounding box for area estimation
6. **Envelope Extraction**: GeoPackage stores bounding box in geometry header, parsed separately from WKB body

**Next.js Configuration** (`next.config.mjs`):
```javascript
// Required for sql.js browser compatibility
turbopack: {
  resolveAlias: {
    fs: { browser: './lib/empty-module.js' },
    path: { browser: './lib/empty-module.js' },
    crypto: { browser: './lib/empty-module.js' },
  },
},
webpack: (config, { isServer }) => {
  if (!isServer) {
    config.resolve.fallback = { fs: false, path: false, crypto: false }
  }
  return config
},
```

**Usage:**
```typescript
import { parseGeospatialFile } from '@/lib/file-parsers'

const geojson = await parseGeospatialFile(file)
// Returns FeatureCollection or null if parsing fails
```

### Environment Variables
```
NEXT_PUBLIC_MODAL_API_URL=https://lukaskucinski--peit-processor-fastapi-app.modal.run
```

### Deployment URLs
- **Production**: https://peit-map-creator.com
- **GitHub**: https://github.com/lukaskucinski/peit_map_creator

### SEO Configuration
- `public/robots.txt`: Allows all crawlers, references sitemap
- `public/sitemap.xml`: Lists main pages for search engine indexing
- `app/layout.tsx`: Contains `metadataBase` URL for OpenGraph/Twitter cards
- `public/google*.html`: Google Search Console verification file
- Favicons: 48x48 PNG icons with tight cropping for browser tabs (generated via `scripts/generate-icons.mjs`)

---

## Modal Backend (modal_app.py)

Serverless backend running on Modal.com for cloud-based geospatial processing.

### Architecture
- **Runtime**: Modal.com serverless functions
- **Framework**: FastAPI with SSE support
- **Container**: Micromamba with GDAL/GeoPandas stack

### API Endpoints

**`POST /api/process`**
- Accepts multipart form data with geospatial file
- Streams progress updates via Server-Sent Events (SSE)
- Returns job ID for result download

**`GET /api/download/{job_id}`**
- Downloads ZIP file containing:
  - `index.html` (interactive map)
  - `PEIT_Report_*.pdf`
  - `PEIT_Report_*.xlsx`
  - `data/*.geojson` (individual layer files)

**`GET /api/health`**
- Health check endpoint

**`GET /api/reverse-geocode`**
- Proxies reverse geocoding requests to Nominatim (avoids browser CORS issues)
- Query params: `lat` (float), `lon` (float)
- Returns Nominatim JSON response with address details
- Uses httpx async client with proper User-Agent header

**`GET /api/rate-limit`**
- Returns remaining runs for current IP

**`POST /api/claim-jobs`**
- Claims unclaimed jobs for a newly authenticated user
- Body: `{ user_id: string, job_ids: string[] }`
- Updates jobs where `user_id IS NULL` to associate with the new user
- Returns: `{ success: true, claimed_count: int }`
- Used by frontend after anonymous user signs up to save their maps to history

**`DELETE /api/jobs/{job_id}`**
- Deletes a job and all associated storage (Supabase record, Modal Volume files, Vercel Blob files)
- Body: `{ user_id: string }`
- Requires job to belong to the requesting user (ownership verified before deletion)
- Returns: `{ success: true, deleted: { database: bool, volume: bool, blobs: [...] } }`
- Error codes: 400 (invalid format), 403 (not authorized), 404 (not found), 500 (server error)

### Anonymous Job Claiming

When anonymous users create maps, the jobs are stored with `user_id = NULL`. If they later sign up or log in, they can claim these jobs.

**Frontend Flow:**
1. Anonymous user processes file → job created with `user_id = NULL`
2. Job ID stored in localStorage (`peit_pending_jobs`)
3. Complete state shows "Save to History" prompt with Sign Up/Sign In buttons
4. User authenticates → `onAuthStateChange` detects sign-in
5. Frontend calls `POST /api/claim-jobs` with user ID and pending job IDs
6. Backend updates job records to set `user_id`
7. Jobs now appear in user's Map History dashboard

**Key Files:**
- `lib/pending-jobs.ts`: localStorage management for pending job IDs
- `components/claim-job-prompt.tsx`: Sign up CTA shown after job completion
- `components/processing-status.tsx`: Displays the claim prompt for anonymous users
- `app/page.tsx`: Orchestrates auth state changes and job claiming

### Security & Rate Limiting

**Protection Layers:**

| Protection | Implementation |
|------------|----------------|
| Daily rate limit (authenticated) | 20 runs per day per user_id |
| Daily rate limit (anonymous) | 4 runs per day per IP address |
| Daily rate limit (global) | 50 runs per day across all users |
| Concurrent limit | 3 simultaneous jobs per IP |
| Input geometry area limit | 500 sq miles maximum |
| File size | 5MB (validated after upload) |
| Request size | 6MB (early rejection via middleware) |
| File types | Whitelist of geo extensions |
| CORS | Restricted to Vercel domains only |
| Job IDs | 16-char UUIDs (prevents URL enumeration) |
| Data retention | 7-day auto-cleanup |

**Tiered Rate Limiting:**
- **Authenticated Users**: 20 runs/day tracked by `user_id` (Modal Dict `peit-user-rate-limits`)
- **Anonymous Users**: 4 runs/day tracked by IP address (Modal Dict `peit-rate-limits`)
- **Per-User Storage**: Key format `{user_id}:{date}`
- **Per-IP Storage**: Key format `{ip}:{date}`
- **Global Storage**: Modal Dict (`peit-global-rate-limit`) with key format `global:{date}`
- **Concurrent Jobs**: Modal Dict (`peit-active-jobs`) with key format `active:{ip}`
- **Reset**: Daily limits reset at midnight UTC; concurrent slots reset when jobs complete
- **Order of Checks**: Global limit → User/IP limit (based on auth) → File validation → Concurrent limit
- **Logging**: Slot acquire/release events logged with `[RATE LIMIT]` prefix for debugging

**Global Rate Limit:**
- Prevents service abuse regardless of IP address rotation
- Checked BEFORE user/IP limit to fail fast
- Returns 429 with `limit_type: "global"` when exceeded
- Configurable via `MAX_GLOBAL_RUNS_PER_DAY` constant (default: 50)

**Input Geometry Area Limit:**
- Maximum input area: 500 sq miles (configurable in `geometry_settings.max_input_area_sq_miles`)
- Warning threshold: 250 sq miles (displays yellow warning suggesting map performance may degrade)
- Validated on backend after geometry processing (includes buffer)
- Frontend displays estimated area for GeoJSON files and drawn geometries
- Uses turf.js for client-side area estimation
- Non-GeoJSON formats (GPKG, SHP) show "not available" message; limit still enforced on backend
- Auto-detects geometry type and sets buffer to 0ft for polygon-only inputs
- Recommended: Urban areas should not exceed 100 sq mi for optimal results
- Prevents state-scale runs that would overwhelm the system

**Request Size Middleware:**
- Uses `LimitUploadSizeMiddleware` (Starlette middleware)
- Rejects requests >6MB before reading body (returns 413)
- Provides early rejection to prevent resource exhaustion

**Concurrent Job Limiting:**
- Tracks active jobs per IP using Modal Dict
- `check_concurrent_limit()` blocks new jobs if IP has ≥3 active
- `release_job_slot()` frees slot on job completion, error, or client disconnection
- **Slot Leak Prevention**: Concurrent check runs AFTER file validation to prevent slots being consumed when validation fails
- **Client Disconnection Handling**: `asyncio.CancelledError` is caught to release slots when users close browser tabs during processing
- **Debugging**: To clear stuck slots manually: `modal dict clear peit-active-jobs`

**CORS Restrictions:**
```python
allow_origins=[
    "https://peit-map-creator.vercel.app",
    "https://peit-map-creator-*.vercel.app",  # Preview deployments
    "http://localhost:3000",  # Local development
]
```

### Live Map URLs (Vercel Blob)

Generated maps are automatically uploaded to Vercel Blob storage, providing shareable live URLs.

**Features:**
- **Live URLs**: Maps accessible at `https://peit-map-creator.com/maps/{job_id}`
- **Direct report links**: PDF and XLSX reports have direct download URLs embedded in map HTML
- **7-day retention**: Matches ZIP download retention policy
- **Zero additional cost**: Within Vercel Blob free tier (1GB storage, 10GB transfer/month)

**Files Uploaded to Blob:**
- `maps/{job_id}/index.html` - Interactive map (~4-5MB)
- `maps/{job_id}/PEIT_Report_*.pdf` - PDF report
- `maps/{job_id}/PEIT_Report_*.xlsx` - Excel report

**NOT Uploaded (ZIP only):**
- `data/*.geojson` files - Not needed since map has embedded GeoJSON

**Upload Order (Important):**
Reports (PDF/XLSX) are uploaded to blob storage **before** the map HTML is generated. This allows the absolute blob URLs to be embedded in the map's About section, ensuring the download links work correctly when the map is accessed via the live URL.

**SSE Completion Event:**
```python
{
    'stage': 'complete',
    'job_id': job_id,
    'download_url': '/api/download/{job_id}',
    'map_url': 'https://peit-map-creator.com/maps/{job_id}',
    'pdf_url': '<blob_url>',
    'xlsx_url': '<blob_url>',
}
```

**Environment Setup:**
1. Create Vercel Blob store in Vercel dashboard
2. Add Modal secret: `modal secret create vercel-blob BLOB_READ_WRITE_TOKEN=xxx`

### Timeout Handling

Modal cancels long-running jobs after ~10 minutes. The backend detects this via `FunctionTimeoutError`:

**Behavior:**
- `FunctionTimeoutError` caught in SSE polling loop (`modal_app.py` lines 829-850)
- Database updated to `status='failed'` with descriptive error message
- SSE error event emitted to frontend
- Concurrent job slot released
- User sees actionable error message in UI

**Error Message:** "Processing exceeded the 10-minute time limit. This usually happens with very large or complex areas. Try a smaller area, simpler geometry, or contact support."

**Implementation Details:**
- Exception handler added BEFORE `TimeoutError` handler (order matters - `FunctionTimeoutError` inherits from `TimeoutError`)
- Supabase client initialized in `event_generator()` for database updates
- Database update wrapped in try/except to ensure SSE event is always sent even if DB update fails
- Logs timeout events with `[TIMEOUT]` prefix for debugging

**Status Values:**
- `processing` - Job in progress
- `complete` - Success
- `failed` - Error or timeout

### Scheduled Cleanup

**Cron Job:** `cleanup_old_results()` runs daily at 3 AM UTC
- Deletes Modal Volume job folders older than 7 days
- Deletes Vercel Blob files older than 7 days
- Uses file modification time (`st_mtime`) for volume, `uploadedAt` for blobs

```python
@app.function(
    image=peit_image,
    volumes={"/results": results_volume},
    secrets=[vercel_blob_secret],
    schedule=modal.Cron("0 3 * * *"),  # 3 AM UTC daily
)
def cleanup_old_results():
    # Deletes volume folders and blobs older than 7 days
```

**Future Enhancement (auth):** When authentication is added:
- Free users: 7-day retention
- Paid users: Indefinite storage (until unsubscribe)

### Configuration
```python
MAX_RUNS_PER_DAY_AUTHENTICATED = 20  # Authenticated users (user_id-based)
MAX_RUNS_PER_DAY_ANONYMOUS = 4       # Anonymous users (IP-based)
MAX_CONCURRENT_JOBS_PER_IP = 3
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_REQUEST_SIZE = 6 * 1024 * 1024  # 6MB (with overhead)
```

### Container Image
Uses Micromamba for geospatial dependencies:
- GDAL >= 3.8
- GeoPandas >= 0.14
- Shapely >= 2.0
- Fiona >= 1.9
- PyProj >= 3.6

**Python Dependencies:**
- `vercel>=0.3.5` - Official Vercel Python SDK for Blob storage operations
  - Uses `BlobClient` for put, list_objects, and delete operations
  - Properly supports `prefix` parameter for filtering blob listings
  - **API Note:** `put()` uses positional args, not options dict: `client.put(pathname, content, access="public", content_type="...")`

### Deployment
```bash
# Development (hot reload)
modal serve modal_app.py

# Production
modal deploy modal_app.py
```

### Volume Storage
- **peit-results**: Temporary storage for generated ZIP files
- **peit-rate-limits**: Daily rate limit counters per IP (anonymous users)
- **peit-user-rate-limits**: Daily rate limit counters per user_id (authenticated users)
- **peit-active-jobs**: Active job counters per IP
- Results auto-cleanup after 7 days via scheduled cron job
