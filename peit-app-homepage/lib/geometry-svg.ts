import type { FeatureCollection, Feature, Geometry, Position } from "geojson"
import * as turf from "@turf/turf"

/**
 * Bounding box type: [minX, minY, maxX, maxY] (lng, lat, lng, lat)
 */
type BBox = [number, number, number, number]

/**
 * SVG dimensions and padding configuration
 */
interface SVGConfig {
  width: number
  height: number
  padding: number
}

/**
 * Calculate bounding box from GeoJSON with optional padding
 */
export function calculateBBox(geojson: FeatureCollection): BBox | null {
  if (!geojson.features || geojson.features.length === 0) {
    return null
  }

  try {
    const bbox = turf.bbox(geojson)
    return bbox as BBox
  } catch {
    return null
  }
}

/**
 * Project a geographic coordinate to SVG space
 * Geographic: (lng, lat) where lat increases northward
 * SVG: (x, y) where y increases downward
 */
export function projectToSVG(
  coord: Position,
  bbox: BBox,
  config: SVGConfig
): [number, number] {
  const [minX, minY, maxX, maxY] = bbox
  const { width, height, padding } = config

  // Calculate available drawing area
  const drawWidth = width - 2 * padding
  const drawHeight = height - 2 * padding

  // Calculate scale to fit while maintaining aspect ratio
  const bboxWidth = maxX - minX
  const bboxHeight = maxY - minY

  // Handle edge cases (single point or very small bbox)
  if (bboxWidth === 0 && bboxHeight === 0) {
    return [width / 2, height / 2]
  }

  const scaleX = bboxWidth > 0 ? drawWidth / bboxWidth : 1
  const scaleY = bboxHeight > 0 ? drawHeight / bboxHeight : 1
  const scale = Math.min(scaleX, scaleY)

  // Center the geometry within the SVG
  const scaledWidth = bboxWidth * scale
  const scaledHeight = bboxHeight * scale
  const offsetX = padding + (drawWidth - scaledWidth) / 2
  const offsetY = padding + (drawHeight - scaledHeight) / 2

  // Project coordinate (flip Y axis for SVG)
  const x = offsetX + (coord[0] - minX) * scale
  const y = offsetY + (maxY - coord[1]) * scale // Flip Y

  return [x, y]
}

/**
 * Convert a ring (array of coordinates) to SVG path data
 */
function ringToPathData(ring: Position[], bbox: BBox, config: SVGConfig): string {
  if (ring.length === 0) return ""

  const points = ring.map((coord) => projectToSVG(coord, bbox, config))
  const [first, ...rest] = points

  let path = `M ${first[0]} ${first[1]}`
  for (const point of rest) {
    path += ` L ${point[0]} ${point[1]}`
  }

  return path
}

/**
 * Convert a GeoJSON feature to SVG path data
 */
export function featureToSVGElements(
  feature: Feature,
  bbox: BBox,
  config: SVGConfig
): SVGPathData[] {
  const geometry = feature.geometry
  if (!geometry) return []

  const elements: SVGPathData[] = []

  switch (geometry.type) {
    case "Point": {
      const [x, y] = projectToSVG(geometry.coordinates, bbox, config)
      elements.push({
        type: "circle",
        cx: x,
        cy: y,
        r: 4,
      })
      break
    }

    case "MultiPoint": {
      for (const coord of geometry.coordinates) {
        const [x, y] = projectToSVG(coord, bbox, config)
        elements.push({
          type: "circle",
          cx: x,
          cy: y,
          r: 4,
        })
      }
      break
    }

    case "LineString": {
      const pathData = ringToPathData(geometry.coordinates, bbox, config)
      if (pathData) {
        elements.push({
          type: "path",
          d: pathData,
          fill: "none",
        })
      }
      break
    }

    case "MultiLineString": {
      for (const line of geometry.coordinates) {
        const pathData = ringToPathData(line, bbox, config)
        if (pathData) {
          elements.push({
            type: "path",
            d: pathData,
            fill: "none",
          })
        }
      }
      break
    }

    case "Polygon": {
      // Outer ring + holes
      let pathData = ""
      for (const ring of geometry.coordinates) {
        pathData += ringToPathData(ring, bbox, config) + " Z "
      }
      if (pathData.trim()) {
        elements.push({
          type: "path",
          d: pathData.trim(),
          fillRule: "evenodd",
        })
      }
      break
    }

    case "MultiPolygon": {
      let pathData = ""
      for (const polygon of geometry.coordinates) {
        for (const ring of polygon) {
          pathData += ringToPathData(ring, bbox, config) + " Z "
        }
      }
      if (pathData.trim()) {
        elements.push({
          type: "path",
          d: pathData.trim(),
          fillRule: "evenodd",
        })
      }
      break
    }

    case "GeometryCollection": {
      for (const geom of geometry.geometries) {
        const subFeature: Feature = { type: "Feature", properties: {}, geometry: geom }
        elements.push(...featureToSVGElements(subFeature, bbox, config))
      }
      break
    }
  }

  return elements
}

/**
 * SVG element data types
 */
export type SVGPathData =
  | { type: "path"; d: string; fill?: string; fillRule?: "evenodd" | "nonzero" }
  | { type: "circle"; cx: number; cy: number; r: number }

/**
 * Convert entire GeoJSON FeatureCollection to SVG elements
 */
export function geojsonToSVGElements(
  geojson: FeatureCollection,
  config: SVGConfig
): { elements: SVGPathData[]; viewBox: string } | null {
  const bbox = calculateBBox(geojson)
  if (!bbox) return null

  const elements: SVGPathData[] = []

  for (const feature of geojson.features) {
    elements.push(...featureToSVGElements(feature, bbox, config))
  }

  return {
    elements,
    viewBox: `0 0 ${config.width} ${config.height}`,
  }
}
