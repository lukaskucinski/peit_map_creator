"use client"

import { useMemo } from "react"
import type { FeatureCollection } from "geojson"
import { geojsonToSVGElements, type SVGPathData } from "@/lib/geometry-svg"
import { cn } from "@/lib/utils"

interface GeometryPreviewProps {
  geojson: FeatureCollection | null
  className?: string
}

const SVG_CONFIG = {
  width: 400,
  height: 300,
  padding: 20,
}

export function GeometryPreview({ geojson, className }: GeometryPreviewProps) {
  const svgData = useMemo(() => {
    if (!geojson || !geojson.features || geojson.features.length === 0) {
      return null
    }
    return geojsonToSVGElements(geojson, SVG_CONFIG)
  }, [geojson])

  if (!svgData) {
    return null
  }

  return (
    <svg
      viewBox={svgData.viewBox}
      className={cn("w-full h-full", className)}
      preserveAspectRatio="xMidYMid meet"
      aria-label="Geometry preview"
    >
      {svgData.elements.map((element, index) => (
        <SVGElement key={index} element={element} />
      ))}
    </svg>
  )
}

function SVGElement({ element }: { element: SVGPathData }) {
  if (element.type === "circle") {
    return (
      <circle
        cx={element.cx}
        cy={element.cy}
        r={element.r}
        className="fill-primary stroke-primary"
        strokeWidth={1.5}
      />
    )
  }

  if (element.type === "path") {
    const isLine = element.fill === "none"
    return (
      <path
        d={element.d}
        fillRule={element.fillRule}
        className={cn(
          "stroke-primary",
          isLine ? "fill-none" : "fill-primary/30"
        )}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    )
  }

  return null
}
