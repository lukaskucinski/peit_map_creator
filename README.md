# APPEIT Map Creator

A Python tool that replicates the NTIA's APPEIT (ArcGIS Pro Permitting and Environmental Information Tool) functionality by querying ArcGIS FeatureServers and generating interactive Leaflet web maps showing environmental layer intersections.

## Overview

This tool eliminates the need for an ArcGIS Pro license by directly querying ESRI-hosted FeatureServer REST APIs and creating dynamic, interactive web maps that display environmental features intersecting with a user-provided polygon.

### Key Features

- **No ArcGIS License Required**: Direct REST API queries to ESRI FeatureServers
- **Multiple Input Formats**: Supports SHP, KML, KMZ, GPKG, GeoJSON, and GDB files
- **Interactive Web Maps**: Generates Leaflet-based HTML maps with layer controls
- **Smart Rendering**: Only downloads and displays features that intersect the input polygon
- **Point Clustering**: Automatically clusters large numbers of point features for better performance
- **Multiple Base Maps**: Includes OpenStreetMap, CartoDB, and ESRI Satellite imagery
- **Separate Data Files**: Outputs clean GeoJSON files for each layer
- **Comprehensive Metadata**: Includes summary statistics and query information

## Installation

### Prerequisites

- **Python 3.8+** (tested with Python 3.12)
- **Anaconda** or **Miniconda** (recommended)

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/lukaskucinski/appeit_map_creator.git
   cd appeit_map_creator
   ```

2. **Create and activate conda environment** (if using Anaconda):
   ```bash
   conda create -n claude python=3.12
   conda activate claude
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Dependencies

The following Python packages will be installed:

- `geopandas>=0.14.0` - Geospatial data processing
- `folium>=0.15.0` - Interactive Leaflet map generation
- `requests>=2.31.0` - HTTP requests to ArcGIS REST APIs
- `shapely>=2.0.0` - Geometry operations
- `pyproj>=3.6.0` - Coordinate system transformations
- `fiona>=1.9.0` - File format support
- `matplotlib>=3.8.0` - Plotting support
- `branca>=0.7.0` - HTML/JavaScript templating

## Configuration

Environmental layers are defined in [config/layers_config.json](config/layers_config.json). The default configuration includes:

1. **RCRA Sites** - Resource Conservation and Recovery Act regulated facilities
2. **NPDES Sites** - National Pollutant Discharge Elimination System sites
3. **Navigable Waterways** - USACE Navigable Waterway Network
4. **Historic Places** - National Register of Historic Places (Points)

### Adding Additional Layers

Edit `config/layers_config.json` to add more FeatureServer layers:

```json
{
  "name": "Layer Name",
  "url": "https://services.arcgis.com/.../FeatureServer",
  "layer_id": 0,
  "color": "#HEX_COLOR",
  "icon": "font-awesome-icon-name",
  "icon_color": "red|blue|green|purple|orange|darkred|lightred|beige|darkblue|darkgreen|cadetblue|darkpurple|white|pink|lightblue|lightgreen|gray|black|lightgray",
  "description": "Layer description",
  "geometry_type": "point|line|polygon"
}
```

### Settings

Modify the `settings` section in `config/layers_config.json`:

- `max_features_per_layer`: Maximum features to request (default: 1000)
- `enable_clustering`: Enable marker clustering for point features (default: true)
- `cluster_threshold`: Minimum features before clustering activates (default: 50)
- `default_zoom`: Initial map zoom level (default: 10)
- `tile_layer`: Default base map (default: "OpenStreetMap")

## Usage

### Basic Usage

```python
python appeit_map_creator.py
```

By default, the script will process the file specified in the `__main__` section:

```python
if __name__ == "__main__":
    INPUT_FILE = r"C:\Users\lukas\Downloads\pa045_mpb.gpkg"
    output_dir = main(INPUT_FILE)
```

### Custom Usage

Modify the script or import the functions:

```python
from appeit_map_creator import main

# Process a custom input file
output_dir = main(
    input_file="path/to/your/polygon.shp",
    output_name="custom_output_name"  # Optional
)
```

### Jupyter-Style Cell Execution

The script is organized into 7 cells that can be run independently:

1. **Cell 1**: Imports and Configuration Setup
2. **Cell 2**: Input Polygon Reader Function
3. **Cell 3**: ArcGIS FeatureServer Query Function
4. **Cell 4**: Process All Layers Function
5. **Cell 5**: Create Leaflet Map with Folium
6. **Cell 6**: Generate Output Files and Structure
7. **Cell 7**: Main Execution Workflow

## Output Structure

Each run creates a timestamped directory in `outputs/`:

```
outputs/
└── appeit_map_20250106_143022/
    ├── index.html              # Interactive Leaflet map (open in browser)
    ├── metadata.json           # Summary statistics and query info
    └── data/
        ├── input_polygon.geojson
        ├── rcra_sites.geojson
        ├── npdes_sites.geojson
        ├── navigable_waterways.geojson
        └── historic_places.geojson
```

### Output Files

- **index.html**: Self-contained interactive map with layer controls, clustering, and popups
- **metadata.json**: Contains query statistics, feature counts, and processing times
- **data/*.geojson**: Individual GeoJSON files for each layer (only intersecting features)

## How It Works

### Workflow

1. **Read Input Polygon**
   - Supports multiple formats (SHP, KML, KMZ, GPKG, GeoJSON, GDB)
   - Auto-detects and reprojects to WGS84 (EPSG:4326)
   - Handles multi-feature files by creating union

2. **Query FeatureServers**
   - Sends spatial intersection queries to each configured FeatureServer
   - Uses ArcGIS REST API with parameters:
     - `geometry`: Input polygon as GeoJSON
     - `spatialRel`: esriSpatialRelIntersects
     - `outFields`: * (all attributes)
     - `f`: geojson (output format)
   - Only downloads features that intersect the input polygon

3. **Create Interactive Map**
   - Initializes Leaflet map centered on input polygon
   - Adds multiple base map options
   - Renders features with layer-specific styling:
     - **Points**: Custom markers with Font Awesome icons
     - **Lines**: Colored polylines with hover effects
     - **Polygons**: Filled areas with borders
   - Applies clustering for large point datasets
   - Creates popups with all feature attributes

4. **Generate Output**
   - Saves HTML map file
   - Exports separate GeoJSON files for each layer
   - Creates metadata JSON with statistics

### Handling Large Datasets

- **Server Limits**: Most ArcGIS FeatureServers limit results to 1000-2000 features
- **Warning System**: Displays warnings when server limits are exceeded
- **Clustering**: Automatically clusters point features when count exceeds threshold
- **Pagination**: Future enhancement to handle multi-page results

## Testing

### Test File

Use the included test file to verify functionality:

```
C:\Users\lukas\Downloads\pa045_mpb.gpkg
```

This Pennsylvania test polygon should intersect with multiple environmental layers.

### Expected Results

- **RCRA Sites**: Should find regulated facilities
- **NPDES Sites**: Should find discharge permit sites
- **Navigable Waterways**: May find waterways depending on location
- **Historic Places**: May find historic sites depending on location

## Troubleshooting

### Common Issues

**Issue**: `ModuleNotFoundError: No module named 'geopandas'`
- **Solution**: Run `pip install -r requirements.txt` in your conda environment

**Issue**: Empty map with no features
- **Solution**: Verify your input polygon is in a valid projection and covers an area with environmental features

**Issue**: "Request failed" errors
- **Solution**: Check internet connection and verify FeatureServer URLs are accessible

**Issue**: Clustering not working
- **Solution**: Verify `enable_clustering: true` in config and feature count exceeds `cluster_threshold`

### Debug Mode

Add print statements or use Python debugger to trace execution:

```python
import pdb; pdb.set_trace()
```

## Limitations

1. **Server Query Limits**: Most FeatureServers limit results to 1000-2000 features per query
2. **No Offline Mode**: Requires internet connection to query FeatureServers
3. **Single Polygon Input**: Currently processes one polygon at a time
4. **No Attribute Filtering**: Downloads all attributes (future enhancement planned)

## Future Enhancements

- [ ] Batch processing for multiple input polygons
- [ ] Pagination support for large datasets (>1000 features)
- [ ] Attribute filtering and selection
- [ ] Export to additional formats (KML, Shapefile, GeoPackage)
- [ ] Custom styling rules per layer
- [ ] Offline caching of FeatureServer queries
- [ ] Integration with additional data sources
- [ ] Command-line interface (CLI) with arguments
- [ ] Progress bars for long-running queries
- [ ] Retry logic with exponential backoff

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is open source and available under the MIT License.

## Acknowledgments

- **NTIA**: For the original APPEIT tool concept and layer definitions
- **ESRI**: For providing public FeatureServer REST APIs
- **Folium**: For excellent Python-to-Leaflet mapping capabilities
- **GeoPandas**: For powerful geospatial data processing

## Contact

For questions, issues, or suggestions:

- **GitHub**: https://github.com/lukaskucinski/appeit_map_creator
- **Issues**: https://github.com/lukaskucinski/appeit_map_creator/issues

## References

- [NTIA NBAM APPEIT](https://nbam.ntia.gov/content/37fa42c6313e4bdb9d8a9c05d2624891/about)
- [ArcGIS REST API Documentation](https://developers.arcgis.com/rest/)
- [Folium Documentation](https://python-visualization.github.io/folium/)
- [GeoPandas Documentation](https://geopandas.org/)
