import type { FeatureCollection, Feature, Geometry } from 'geojson'
import type { Layer, FeatureGroup } from 'leaflet'
import * as turf from '@turf/turf'

// Area limit constants (in square miles)
export const MAX_AREA_SQ_MILES = 500
export const WARN_AREA_SQ_MILES = 250

// US state abbreviations for filename generation
const STATE_ABBREVIATIONS: Record<string, string> = {
  'Alabama': 'al', 'Alaska': 'ak', 'Arizona': 'az', 'Arkansas': 'ar', 'California': 'ca',
  'Colorado': 'co', 'Connecticut': 'ct', 'Delaware': 'de', 'Florida': 'fl', 'Georgia': 'ga',
  'Hawaii': 'hi', 'Idaho': 'id', 'Illinois': 'il', 'Indiana': 'in', 'Iowa': 'ia',
  'Kansas': 'ks', 'Kentucky': 'ky', 'Louisiana': 'la', 'Maine': 'me', 'Maryland': 'md',
  'Massachusetts': 'ma', 'Michigan': 'mi', 'Minnesota': 'mn', 'Mississippi': 'ms', 'Missouri': 'mo',
  'Montana': 'mt', 'Nebraska': 'ne', 'Nevada': 'nv', 'New Hampshire': 'nh', 'New Jersey': 'nj',
  'New Mexico': 'nm', 'New York': 'ny', 'North Carolina': 'nc', 'North Dakota': 'nd', 'Ohio': 'oh',
  'Oklahoma': 'ok', 'Oregon': 'or', 'Pennsylvania': 'pa', 'Rhode Island': 'ri', 'South Carolina': 'sc',
  'South Dakota': 'sd', 'Tennessee': 'tn', 'Texas': 'tx', 'Utah': 'ut', 'Vermont': 'vt',
  'Virginia': 'va', 'Washington': 'wa', 'West Virginia': 'wv', 'Wisconsin': 'wi', 'Wyoming': 'wy',
  'District of Columbia': 'dc', 'Puerto Rico': 'pr', 'Guam': 'gu', 'American Samoa': 'as',
  'U.S. Virgin Islands': 'vi', 'Northern Mariana Islands': 'mp'
}

// Conversion: 1 square mile = 2,589,988 square meters
const SQ_METERS_PER_SQ_MILE = 2589988

/**
 * Convert Leaflet layers from a FeatureGroup to a GeoJSON FeatureCollection
 */
export function layersToGeoJSON(featureGroup: FeatureGroup): FeatureCollection {
  const features: Feature[] = []

  featureGroup.eachLayer((layer: Layer) => {
    // Check if layer has toGeoJSON method (it should for drawn shapes)
    if ('toGeoJSON' in layer && typeof layer.toGeoJSON === 'function') {
      const geojson = layer.toGeoJSON() as Feature | FeatureCollection

      // Handle both single features and feature collections
      if (geojson.type === 'FeatureCollection') {
        features.push(...geojson.features)
      } else if (geojson.type === 'Feature') {
        features.push(geojson)
      }
    }
  })

  return {
    type: 'FeatureCollection',
    features
  }
}

/**
 * Convert a GeoJSON object to a File object that can be uploaded
 */
export function geojsonToFile(geojson: FeatureCollection, filename: string = 'drawn_geometry.geojson'): File {
  const jsonString = JSON.stringify(geojson, null, 2)
  const blob = new Blob([jsonString], { type: 'application/geo+json' })
  return new File([blob], filename, { type: 'application/geo+json' })
}

/**
 * Location data from reverse geocoding
 */
export interface LocationData {
  city: string      // City/town/village name
  county: string    // County name (without "County" suffix)
  state: string     // Full state name
  stateAbbr: string // Two-letter state abbreviation
}

/**
 * Reverse geocode a coordinate point to get location data.
 * Uses backend proxy to Nominatim API (avoids CORS issues).
 *
 * @param lat - Latitude
 * @param lon - Longitude
 * @returns Location data or null on failure
 */
export async function reverseGeocodePoint(lat: number, lon: number): Promise<LocationData | null> {
  try {
    // Import dynamically to avoid circular dependency
    const { reverseGeocode } = await import('@/lib/api')
    const data = await reverseGeocode(lat, lon)

    if (!data || !data.address) {
      return null
    }

    const city = data.address.city || data.address.town || data.address.village ||
                 data.address.municipality || ''
    const county = (data.address.county || '').replace(/\s+County$/i, '')
    const state = data.address.state || ''
    const stateAbbr = STATE_ABBREVIATIONS[state] || ''

    return { city, county, state, stateAbbr }
  } catch (error) {
    console.warn('Geocoding failed:', error)
    return null
  }
}

/**
 * Reverse geocode a GeoJSON FeatureCollection's centroid to get location data.
 * Uses backend proxy to Nominatim API (avoids CORS issues).
 *
 * @param geojson - The FeatureCollection to geocode
 * @returns Location data or null on failure
 */
export async function reverseGeocodeGeometry(geojson: FeatureCollection): Promise<LocationData | null> {
  try {
    const centroid = turf.centroid(geojson)
    const [lon, lat] = centroid.geometry.coordinates
    return reverseGeocodePoint(lat, lon)
  } catch (error) {
    console.warn('Geocoding failed:', error)
    return null
  }
}

/**
 * Reverse geocode a GeoJSON FeatureCollection's centroid to generate a location-based filename.
 * Uses backend proxy to Nominatim API (avoids CORS issues).
 *
 * @param geojson - The FeatureCollection to geocode
 * @returns A filename like "seattle_king_wa.geojson" or "drawn_geometry.geojson" on failure
 */
export async function generateLocationFilename(geojson: FeatureCollection): Promise<string> {
  const defaultFilename = 'drawn_geometry.geojson'

  const location = await reverseGeocodeGeometry(geojson)
  if (!location) return defaultFilename

  // Build filename parts (filter out empty strings)
  const parts = [location.city, location.county, location.stateAbbr]
    .filter(Boolean)
    .map(s => s.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, ''))
    .filter(s => s.length > 0)

  if (parts.length === 0) {
    return defaultFilename
  }

  return `${parts.join('_')}.geojson`
}

/**
 * Generate a location-based Project ID from geocoded location data.
 * Format: PEIT-CIT-COU-ST-DDMMYYYY (e.g., PEIT-SEA-KIN-WA-21122025)
 *
 * @param location - Location data from reverse geocoding
 * @returns Project ID string
 */
export function generateLocationProjectId(location: LocationData | null): string {
  const now = new Date()
  const day = now.getDate().toString().padStart(2, '0')
  const month = (now.getMonth() + 1).toString().padStart(2, '0')
  const year = now.getFullYear()
  const datePart = `${day}${month}${year}`

  if (!location) {
    // Fallback to random ID if no location
    const random = Math.random().toString(36).substring(2, 6).toUpperCase()
    return `PEIT-${random}-${datePart}`
  }

  // Create 3-letter codes from location parts
  const cityCode = location.city
    ? location.city.substring(0, 3).toUpperCase().replace(/[^A-Z]/g, '')
    : ''
  const countyCode = location.county
    ? location.county.substring(0, 3).toUpperCase().replace(/[^A-Z]/g, '')
    : ''
  const stateCode = location.stateAbbr.toUpperCase()

  // Build parts array (filter out empty strings)
  const parts = [cityCode, countyCode, stateCode].filter(s => s.length > 0)

  if (parts.length === 0) {
    // Fallback if all parts are empty
    const random = Math.random().toString(36).substring(2, 6).toUpperCase()
    return `PEIT-${random}-${datePart}`
  }

  return `PEIT-${parts.join('-')}-${datePart}`
}

/**
 * Validate that the drawn geometry is not empty and has valid features
 */
export function validateDrawnGeometry(geojson: FeatureCollection): { valid: boolean; error?: string } {
  if (!geojson || geojson.type !== 'FeatureCollection') {
    return { valid: false, error: 'Invalid GeoJSON format' }
  }

  if (!geojson.features || geojson.features.length === 0) {
    return { valid: false, error: 'Please draw at least one shape on the map' }
  }

  // Check that all features have valid geometry
  for (const feature of geojson.features) {
    if (!feature.geometry) {
      return { valid: false, error: 'One or more shapes have invalid geometry' }
    }

    const geomType = feature.geometry.type
    if (!['Point', 'LineString', 'Polygon', 'MultiPoint', 'MultiLineString', 'MultiPolygon'].includes(geomType)) {
      return { valid: false, error: `Unsupported geometry type: ${geomType}` }
    }

    // Check for empty coordinates
    const coords = (feature.geometry as Geometry & { coordinates: unknown }).coordinates
    if (!coords || (Array.isArray(coords) && coords.length === 0)) {
      return { valid: false, error: 'One or more shapes have empty coordinates' }
    }
  }

  return { valid: true }
}

/**
 * Get a summary of the drawn geometry for display
 */
export function getGeometrySummary(geojson: FeatureCollection): string {
  if (!geojson.features || geojson.features.length === 0) {
    return 'No shapes drawn'
  }

  const counts: Record<string, number> = {}

  for (const feature of geojson.features) {
    const type = feature.geometry?.type || 'Unknown'
    counts[type] = (counts[type] || 0) + 1
  }

  const parts: string[] = []

  if (counts['Polygon'] || counts['MultiPolygon']) {
    const total = (counts['Polygon'] || 0) + (counts['MultiPolygon'] || 0)
    parts.push(`${total} polygon${total > 1 ? 's' : ''}`)
  }

  if (counts['LineString'] || counts['MultiLineString']) {
    const total = (counts['LineString'] || 0) + (counts['MultiLineString'] || 0)
    parts.push(`${total} line${total > 1 ? 's' : ''}`)
  }

  if (counts['Point'] || counts['MultiPoint']) {
    const total = (counts['Point'] || 0) + (counts['MultiPoint'] || 0)
    parts.push(`${total} point${total > 1 ? 's' : ''}`)
  }

  return parts.join(', ') || `${geojson.features.length} shape(s)`
}

/**
 * Detected geometry type for a FeatureCollection
 */
export type DetectedGeometryType = 'polygon' | 'line' | 'point' | 'mixed' | 'unknown'

/**
 * Detect the primary geometry type in a FeatureCollection
 * Returns 'polygon', 'line', 'point', 'mixed', or 'unknown'
 */
export function detectGeometryType(geojson: FeatureCollection): DetectedGeometryType {
  if (!geojson.features || geojson.features.length === 0) {
    return 'unknown'
  }

  const types = new Set<string>()

  for (const feature of geojson.features) {
    if (!feature.geometry) continue

    const geomType = feature.geometry.type
    if (geomType === 'Polygon' || geomType === 'MultiPolygon') {
      types.add('polygon')
    } else if (geomType === 'LineString' || geomType === 'MultiLineString') {
      types.add('line')
    } else if (geomType === 'Point' || geomType === 'MultiPoint') {
      types.add('point')
    }
  }

  if (types.size === 0) return 'unknown'
  if (types.size > 1) return 'mixed'

  // Return the single type
  return types.values().next().value as DetectedGeometryType
}

/**
 * Calculate the area of polygon features in a GeoJSON FeatureCollection
 * Returns area in square miles
 */
export function calculatePolygonAreaSqMiles(geojson: FeatureCollection): number {
  if (!geojson.features || geojson.features.length === 0) {
    return 0
  }

  try {
    let totalAreaSqMeters = 0

    for (const feature of geojson.features) {
      if (feature.geometry?.type === 'Polygon' || feature.geometry?.type === 'MultiPolygon') {
        totalAreaSqMeters += turf.area(feature)
      }
    }

    return totalAreaSqMeters / SQ_METERS_PER_SQ_MILE
  } catch {
    return 0
  }
}

/**
 * Estimate the buffered area of a GeoJSON FeatureCollection
 * Applies buffer to all geometry types when buffer distance > 0
 *
 * @param geojson - The FeatureCollection to calculate area for
 * @param bufferDistanceFeet - Buffer distance in feet (applied to all geometry types)
 * @returns Estimated area in square miles
 */
export function estimateBufferedAreaSqMiles(
  geojson: FeatureCollection,
  bufferDistanceFeet: number
): number {
  if (!geojson.features || geojson.features.length === 0) {
    return 0
  }

  try {
    const bufferMiles = bufferDistanceFeet / 5280
    const bufferedFeatures: Feature[] = []

    for (const feature of geojson.features) {
      if (!feature.geometry) continue

      const geomType = feature.geometry.type

      if (geomType === 'Polygon' || geomType === 'MultiPolygon') {
        // Buffer polygons if buffer distance is specified, otherwise use as-is
        if (bufferMiles > 0) {
          const buffered = turf.buffer(feature, bufferMiles, { units: 'miles' })
          if (buffered) bufferedFeatures.push(buffered)
        } else {
          bufferedFeatures.push(feature)
        }
      } else if (geomType === 'Point' || geomType === 'MultiPoint') {
        // Buffer points
        const buffered = turf.buffer(feature, bufferMiles, { units: 'miles' })
        if (buffered) bufferedFeatures.push(buffered)
      } else if (geomType === 'LineString' || geomType === 'MultiLineString') {
        // Buffer lines
        const buffered = turf.buffer(feature, bufferMiles, { units: 'miles' })
        if (buffered) bufferedFeatures.push(buffered)
      }
    }

    if (bufferedFeatures.length === 0) return 0

    // Calculate total area of all buffered features
    // Note: This doesn't dissolve overlapping areas, so may overestimate
    // but is good enough for validation purposes
    let totalAreaSqMeters = 0
    for (const feature of bufferedFeatures) {
      totalAreaSqMeters += turf.area(feature)
    }

    return totalAreaSqMeters / SQ_METERS_PER_SQ_MILE
  } catch {
    return 0
  }
}

/**
 * Area validation result
 */
export interface AreaValidation {
  valid: boolean
  areaSqMiles: number
  warning?: string
  error?: string
}

/**
 * Validate geometry area against limits
 *
 * @param geojson - The FeatureCollection to validate
 * @param bufferDistanceFeet - Buffer distance in feet (for points/lines)
 * @param maxAreaSqMiles - Maximum allowed area (default: 5000)
 * @returns Validation result with area and any warnings/errors
 */
export function validateGeometryArea(
  geojson: FeatureCollection,
  bufferDistanceFeet: number,
  maxAreaSqMiles: number = MAX_AREA_SQ_MILES
): AreaValidation {
  const estimatedArea = estimateBufferedAreaSqMiles(geojson, bufferDistanceFeet)

  if (estimatedArea > maxAreaSqMiles) {
    return {
      valid: false,
      areaSqMiles: estimatedArea,
      error: `Estimated area (${estimatedArea.toFixed(1)} sq mi) exceeds limit (${maxAreaSqMiles} sq mi). Please reduce your geometry size or buffer distance.`
    }
  }

  if (estimatedArea > WARN_AREA_SQ_MILES) {
    return {
      valid: true,
      areaSqMiles: estimatedArea,
      warning: `Large area detected (${estimatedArea.toFixed(1)} sq mi). Processing may take longer.`
    }
  }

  return {
    valid: true,
    areaSqMiles: estimatedArea
  }
}
