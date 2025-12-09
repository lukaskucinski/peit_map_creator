/**
 * Client-side geospatial file parsers
 *
 * Provides unified parsing for various geospatial file formats:
 * - GeoJSON (.geojson, .json)
 * - Shapefile (.shp, .zip containing shapefile)
 * - KML (.kml)
 * - KMZ (.kmz)
 * - GeoPackage (.gpkg) - lazy-loaded WASM parser
 */

import shp from 'shpjs'
import { kml } from '@tmcw/togeojson'
import JSZip from 'jszip'
import type { FeatureCollection, Feature, Geometry } from 'geojson'

/**
 * Parse a Shapefile or ZIP containing shapefile components
 *
 * @param file - File object (.shp or .zip)
 * @returns FeatureCollection or null if parsing fails
 */
export async function parseShapefile(file: File): Promise<FeatureCollection | null> {
  try {
    const buffer = await file.arrayBuffer()
    const geojson = await shp(buffer)

    // shpjs returns FeatureCollection or array of FeatureCollections (for multi-layer zips)
    if (Array.isArray(geojson)) {
      // Merge all feature collections into one
      const allFeatures: Feature[] = []
      for (const fc of geojson) {
        if (fc && fc.features) {
          allFeatures.push(...fc.features)
        }
      }
      return {
        type: 'FeatureCollection',
        features: allFeatures
      }
    }

    return geojson as FeatureCollection
  } catch (error) {
    console.error('Error parsing Shapefile:', error)
    return null
  }
}

/**
 * Parse a KML file
 *
 * @param file - File object (.kml)
 * @returns FeatureCollection or null if parsing fails
 */
export async function parseKML(file: File): Promise<FeatureCollection | null> {
  try {
    const text = await file.text()
    const dom = new DOMParser().parseFromString(text, 'text/xml')

    // Check for parse errors
    const parseError = dom.querySelector('parsererror')
    if (parseError) {
      console.error('KML parse error:', parseError.textContent)
      return null
    }

    const geojson = kml(dom)
    return geojson as FeatureCollection
  } catch (error) {
    console.error('Error parsing KML:', error)
    return null
  }
}

/**
 * Parse a KMZ file (compressed KML)
 *
 * @param file - File object (.kmz)
 * @returns FeatureCollection or null if parsing fails
 */
export async function parseKMZ(file: File): Promise<FeatureCollection | null> {
  try {
    const buffer = await file.arrayBuffer()
    const zip = await JSZip.loadAsync(buffer)

    // Find the KML file inside the KMZ (typically doc.kml or root-level .kml)
    const kmlFilename = Object.keys(zip.files).find(
      (name) => name.toLowerCase().endsWith('.kml')
    )

    if (!kmlFilename) {
      console.error('No KML file found in KMZ archive')
      return null
    }

    const kmlText = await zip.files[kmlFilename].async('text')
    const dom = new DOMParser().parseFromString(kmlText, 'text/xml')

    // Check for parse errors
    const parseError = dom.querySelector('parsererror')
    if (parseError) {
      console.error('KML parse error in KMZ:', parseError.textContent)
      return null
    }

    const geojson = kml(dom)
    return geojson as FeatureCollection
  } catch (error) {
    console.error('Error parsing KMZ:', error)
    return null
  }
}

/**
 * Parse a GeoJSON file
 *
 * @param file - File object (.geojson or .json)
 * @returns FeatureCollection or null if parsing fails
 */
export async function parseGeoJSON(file: File): Promise<FeatureCollection | null> {
  try {
    const text = await file.text()
    const parsed = JSON.parse(text)

    // Handle FeatureCollection
    if (parsed.type === 'FeatureCollection' && Array.isArray(parsed.features)) {
      return parsed as FeatureCollection
    }

    // Handle single Feature - wrap in FeatureCollection
    if (parsed.type === 'Feature' && parsed.geometry) {
      return {
        type: 'FeatureCollection',
        features: [parsed as Feature]
      }
    }

    // Handle raw Geometry - wrap in Feature and FeatureCollection
    if (parsed.type && parsed.coordinates) {
      return {
        type: 'FeatureCollection',
        features: [{
          type: 'Feature',
          properties: {},
          geometry: parsed
        }]
      }
    }

    console.error('Unrecognized GeoJSON structure')
    return null
  } catch (error) {
    console.error('Error parsing GeoJSON:', error)
    return null
  }
}

/**
 * Parse a GeoPackage file using @ngageoint/geopackage
 * Uses lazy loading to avoid bundling WASM until needed
 *
 * @param file - File object (.gpkg)
 * @returns FeatureCollection or null if parsing fails
 */
export async function parseGeoPackage(file: File): Promise<FeatureCollection | null> {
  try {
    // Lazy load the geopackage library
    const { GeoPackageAPI, setSqljsWasmLocateFile } = await import('@ngageoint/geopackage')

    // Configure WASM file location - required for browser environments
    // sql.js needs to know where to fetch the WASM binary from
    setSqljsWasmLocateFile((file: string) => `https://unpkg.com/@ngageoint/geopackage@4.2.5/dist/${file}`)

    const buffer = await file.arrayBuffer()
    const uint8Array = new Uint8Array(buffer)

    // Open the GeoPackage from the buffer
    const geoPackage = await GeoPackageAPI.open(uint8Array)

    const allFeatures: Feature[] = []

    try {
      // Get all feature table names
      const featureTableNames = geoPackage.getFeatureTables()
      console.log('GeoPackage feature tables:', featureTableNames)

      for (const tableName of featureTableNames) {
        try {
          // Get geometry column name from gpkg_geometry_columns table
          let geomColumnName = 'geom'
          try {
            const geomColResult = geoPackage.connection.get(
              `SELECT column_name FROM gpkg_geometry_columns WHERE table_name = ?`,
              [tableName]
            )
            if (geomColResult?.column_name) {
              geomColumnName = geomColResult.column_name
            }
          } catch {
            // Use default 'geom' if metadata query fails
          }

          console.log(`Table "${tableName}": geometry column = "${geomColumnName}"`)

          // Use raw SQL to get features - this is more reliable than the DAO methods
          const rows = geoPackage.connection.all(
            `SELECT * FROM "${tableName}"`
          )

          console.log(`Table "${tableName}": got ${rows?.length || 0} rows from SQL`)

          if (!rows || rows.length === 0) continue

          // Log first row for debugging
          if (rows.length > 0) {
            console.log(`First row keys:`, Object.keys(rows[0]))
            console.log(`First row geom column type:`, typeof rows[0][geomColumnName])
            const geomValue = rows[0][geomColumnName]
            if (geomValue instanceof Uint8Array) {
              console.log(`First row geom: Uint8Array(${geomValue.length})`)
              // Log first 20 bytes as hex for debugging WKB header
              const hexBytes = Array.from(geomValue.slice(0, 20))
                .map(b => b.toString(16).padStart(2, '0'))
                .join(' ')
              console.log(`First 20 bytes (hex):`, hexBytes)
              // GeoPackage header: "GP" (0x47 0x50), version, flags, srsId (4 bytes)
              // Then optionally envelope, then WKB
              if (geomValue[0] === 0x47 && geomValue[1] === 0x50) {
                console.log(`GeoPackage geometry header detected (GP magic)`)
                const version = geomValue[2]
                const flags = geomValue[3]
                console.log(`  Version: ${version}, Flags: 0b${flags.toString(2).padStart(8, '0')}`)
              }
            } else {
              console.log(`First row geom value type:`, typeof geomValue)
            }
          }

          // Import geometry parser
          const gpkgModule = await import('@ngageoint/geopackage')

          let processedCount = 0
          for (const row of rows) {
            try {
              const geomBlob = row[geomColumnName]
              if (!geomBlob) {
                if (processedCount === 0) {
                  console.warn(`Row has no geometry in column "${geomColumnName}"`)
                }
                continue
              }

              // Parse the geometry blob using GeometryData
              let geojsonGeom: Geometry | null = null

              if (geomBlob instanceof Uint8Array || geomBlob instanceof ArrayBuffer) {
                try {
                  // Use the library's geometry parser
                  const uint8 = geomBlob instanceof Uint8Array ? geomBlob : new Uint8Array(geomBlob)
                  const geomData = new gpkgModule.GeometryData()
                  geomData.fromData(uint8)

                  // Check if geometry was successfully parsed
                  // GeometryData stores parse errors in geometryError property
                  const geomDataTyped = geomData as {
                    geometryError?: string
                    geometry?: { toGeoJSON: () => unknown }
                    envelope?: { minX: number; maxX: number; minY: number; maxY: number }
                  }

                  if (geomDataTyped.geometryError) {
                    if (processedCount === 0) {
                      console.warn(`WKB parse error:`, geomDataTyped.geometryError)
                    }
                    // Fallback: use envelope as bounding box polygon for area estimation
                    if (geomDataTyped.envelope) {
                      const env = geomDataTyped.envelope
                      if (processedCount === 0) {
                        console.log(`Using envelope as fallback:`, env)
                      }
                      // Create polygon from envelope bounds
                      geojsonGeom = {
                        type: 'Polygon',
                        coordinates: [[
                          [env.minX, env.minY],
                          [env.maxX, env.minY],
                          [env.maxX, env.maxY],
                          [env.minX, env.maxY],
                          [env.minX, env.minY]
                        ]]
                      }
                    }
                  } else if (geomDataTyped.geometry) {
                    // wkx's toGeoJSON returns geometry object directly
                    const result = geomDataTyped.geometry.toGeoJSON()
                    if (result && typeof result === 'object' && 'type' in result) {
                      geojsonGeom = result as unknown as Geometry
                    }
                  }
                } catch (parseError) {
                  if (processedCount === 0) {
                    console.warn(`Failed to parse geometry blob:`, parseError)
                  }
                }
              }

              if (!geojsonGeom) {
                if (processedCount === 0) {
                  console.warn(`Could not convert geometry to GeoJSON`)
                }
                continue
              }

              // Build properties from non-geometry columns
              const properties: Record<string, unknown> = {}
              for (const key of Object.keys(row)) {
                if (key !== geomColumnName && row[key] !== undefined && row[key] !== null) {
                  // Skip binary data in properties
                  if (!(row[key] instanceof Uint8Array) && !(row[key] instanceof ArrayBuffer)) {
                    properties[key] = row[key]
                  }
                }
              }

              allFeatures.push({
                type: 'Feature',
                properties,
                geometry: geojsonGeom
              })
              processedCount++
            } catch (rowError) {
              if (processedCount === 0) {
                console.warn(`Row processing error:`, rowError)
              }
            }
          }

          console.log(`Table "${tableName}": processed ${processedCount} features`)
        } catch (tableError) {
          console.warn(`Error processing table "${tableName}":`, tableError)
          // Continue with other tables
        }
      }
    } finally {
      // Always close the GeoPackage to free resources
      geoPackage.close()
    }

    if (allFeatures.length === 0) {
      console.error('No features found in GeoPackage - geometry encoding may be unsupported')
      return null
    }

    return {
      type: 'FeatureCollection',
      features: allFeatures
    }
  } catch (error) {
    console.error('Error parsing GeoPackage:', error)
    return null
  }
}

/**
 * Parse any supported geospatial file format
 *
 * Determines file type by extension and delegates to appropriate parser.
 *
 * Supported formats:
 * - .geojson, .json - GeoJSON
 * - .shp, .zip - Shapefile
 * - .kml - KML
 * - .kmz - KMZ (compressed KML)
 * - .gpkg - GeoPackage (lazy-loaded WASM)
 *
 * @param file - File object to parse
 * @returns FeatureCollection or null if format unsupported or parsing fails
 */
export async function parseGeospatialFile(file: File): Promise<FeatureCollection | null> {
  const name = file.name.toLowerCase()

  // GeoJSON
  if (name.endsWith('.geojson') || name.endsWith('.json')) {
    return parseGeoJSON(file)
  }

  // Shapefile (individual .shp or .zip archive)
  if (name.endsWith('.zip') || name.endsWith('.shp')) {
    return parseShapefile(file)
  }

  // KML
  if (name.endsWith('.kml')) {
    return parseKML(file)
  }

  // KMZ
  if (name.endsWith('.kmz')) {
    return parseKMZ(file)
  }

  // GeoPackage
  if (name.endsWith('.gpkg')) {
    return parseGeoPackage(file)
  }

  // Unsupported format
  // Return null - caller should show appropriate message
  return null
}

/**
 * Check if a file format is supported for client-side parsing
 *
 * @param filename - Name of the file to check
 * @returns true if format can be parsed client-side
 */
export function isClientParseable(filename: string): boolean {
  const name = filename.toLowerCase()
  return (
    name.endsWith('.geojson') ||
    name.endsWith('.json') ||
    name.endsWith('.zip') ||
    name.endsWith('.shp') ||
    name.endsWith('.kml') ||
    name.endsWith('.kmz') ||
    name.endsWith('.gpkg')
  )
}
