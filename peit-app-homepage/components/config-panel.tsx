"use client"

import { useState, useCallback, useEffect } from "react"
import { Play, Settings, AlertTriangle, AlertCircle, MapPin } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"
import type { FeatureCollection } from "geojson"
import {
  validateGeometryArea,
  detectGeometryType,
  type AreaValidation,
  type DetectedGeometryType,
  MAX_AREA_SQ_MILES,
} from "@/lib/geojson-utils"

export interface ProcessingConfig {
  projectName: string
  projectId: string
  bufferDistanceFeet: number
  clipBufferMiles: number
}

interface ConfigPanelProps {
  filename: string
  onRun: (config: ProcessingConfig) => void
  disabled?: boolean
  geojsonData?: FeatureCollection | null
}

// Constants
const DEFAULT_BUFFER_FEET = 500
const MIN_BUFFER_FEET = 0
const MAX_BUFFER_FEET = 26400 // 5 miles in feet

const DEFAULT_CLIP_MILES = 1.0
const MIN_CLIP_MILES = 0.1
const MAX_CLIP_MILES = 5.0

export function ConfigPanel({ filename, onRun, disabled = false, geojsonData }: ConfigPanelProps) {
  const [projectName, setProjectName] = useState("")
  const [projectId, setProjectId] = useState("")
  const [bufferDistanceFeet, setBufferDistanceFeet] = useState(DEFAULT_BUFFER_FEET)
  const [clipBufferMiles, setClipBufferMiles] = useState(DEFAULT_CLIP_MILES)
  const [areaValidation, setAreaValidation] = useState<AreaValidation | null>(null)
  const [detectedGeomType, setDetectedGeomType] = useState<DetectedGeometryType | null>(null)
  const [hasAutoSetBuffer, setHasAutoSetBuffer] = useState(false)

  // Get filename without extension for default project name
  const defaultProjectName = filename.replace(/\.[^/.]+$/, "")

  // Detect geometry type and auto-set buffer when geojsonData changes
  useEffect(() => {
    if (geojsonData) {
      const geomType = detectGeometryType(geojsonData)
      setDetectedGeomType(geomType)

      // Auto-set buffer to 0 for polygon-only inputs (only on first detection)
      if (!hasAutoSetBuffer) {
        if (geomType === 'polygon') {
          setBufferDistanceFeet(0)
        } else {
          setBufferDistanceFeet(DEFAULT_BUFFER_FEET)
        }
        setHasAutoSetBuffer(true)
      }
    } else {
      setDetectedGeomType(null)
      setHasAutoSetBuffer(false)
    }
  }, [geojsonData, hasAutoSetBuffer])

  // Calculate area validation when geojsonData or bufferDistanceFeet changes
  useEffect(() => {
    if (geojsonData) {
      const validation = validateGeometryArea(geojsonData, bufferDistanceFeet, MAX_AREA_SQ_MILES)
      setAreaValidation(validation)
    } else {
      setAreaValidation(null)
    }
  }, [geojsonData, bufferDistanceFeet])

  // Determine if run should be disabled due to area validation
  const isAreaInvalid = areaValidation ? !areaValidation.valid : false

  // Check if the file format can be parsed client-side for area estimation
  // Supported: GeoJSON, Shapefile, KML, KMZ, GeoPackage (lazy-loaded WASM)
  const lowerFilename = filename.toLowerCase()
  const isGeoPackage = lowerFilename.endsWith('.gpkg')
  const isClientParseable = (
    lowerFilename.endsWith('.geojson') ||
    lowerFilename.endsWith('.json') ||
    lowerFilename.endsWith('.shp') ||
    lowerFilename.endsWith('.zip') ||
    lowerFilename.endsWith('.kml') ||
    lowerFilename.endsWith('.kmz') ||
    isGeoPackage
  )
  // GeoPackage files may fail to parse client-side due to WKB encoding variants
  const isGeoPackageParseFailure = isGeoPackage && !geojsonData && isClientParseable

  const handleRun = useCallback(() => {
    onRun({
      projectName: projectName.trim() || defaultProjectName,
      projectId: projectId.trim() || generateProjectId(),
      bufferDistanceFeet,
      clipBufferMiles,
    })
  }, [projectName, projectId, bufferDistanceFeet, clipBufferMiles, defaultProjectName, onRun])

  // Format buffer distance for display
  const formatBufferFeet = (feet: number): string => {
    if (feet >= 5280) {
      const miles = feet / 5280
      return `${feet.toLocaleString()} ft (${miles.toFixed(2)} mi)`
    }
    return `${feet.toLocaleString()} ft`
  }

  return (
    <Card className="mx-auto max-w-2xl mt-6">
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Settings className="h-5 w-5" />
          Configuration Options
          <span className="text-sm font-normal text-muted-foreground">(Optional)</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Project Name */}
        <div className="space-y-2">
          <Label htmlFor="projectName">Project Name</Label>
          <Input
            id="projectName"
            placeholder={defaultProjectName}
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            disabled={disabled}
            maxLength={100}
          />
          <p className="text-xs text-muted-foreground">
            Leave blank to use filename
          </p>
        </div>

        {/* Project ID */}
        <div className="space-y-2">
          <Label htmlFor="projectId">Project ID</Label>
          <Input
            id="projectId"
            placeholder="Auto-generated"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
            disabled={disabled}
            maxLength={50}
          />
          <p className="text-xs text-muted-foreground">
            Leave blank to auto-generate
          </p>
        </div>

        {/* Input Buffer Distance */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label>Input Buffer Distance</Label>
            <span className="text-sm font-medium text-foreground">
              {formatBufferFeet(bufferDistanceFeet)}
            </span>
          </div>
          <Slider
            value={[bufferDistanceFeet]}
            onValueChange={(value) => setBufferDistanceFeet(value[0])}
            min={MIN_BUFFER_FEET}
            max={MAX_BUFFER_FEET}
            step={100}
            disabled={disabled}
            className="w-full"
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>0 ft</span>
            <span>26,400 ft (5 mi)</span>
          </div>
          {detectedGeomType && (
            <p className="text-xs text-muted-foreground">
              {detectedGeomType === 'polygon' && "Polygon detected - buffer set to 0 ft (no buffer needed)"}
              {detectedGeomType === 'line' && "Line detected - buffer applied on both sides"}
              {detectedGeomType === 'point' && "Point detected - buffer creates circular search area"}
              {detectedGeomType === 'mixed' && "Mixed geometry - buffer applied to points/lines only"}
            </p>
          )}
        </div>

        {/* Clip Buffer Distance */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Label>Clip Buffer Distance</Label>
            <span className="text-sm font-medium text-foreground">
              {clipBufferMiles.toFixed(1)} mi
            </span>
          </div>
          <Slider
            value={[clipBufferMiles]}
            onValueChange={(value) => setClipBufferMiles(value[0])}
            min={MIN_CLIP_MILES}
            max={MAX_CLIP_MILES}
            step={0.1}
            disabled={disabled}
            className="w-full"
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>0.1 mi</span>
            <span>5.0 mi</span>
          </div>
        </div>

        {/* Area Estimate Display */}
        {areaValidation ? (
          <div
            className={`rounded-lg px-4 py-3 text-sm ${
              areaValidation.error
                ? "bg-destructive/10 border border-destructive/20"
                : areaValidation.warning
                  ? "bg-yellow-50 border border-yellow-200 dark:bg-yellow-950/20 dark:border-yellow-900/30"
                  : "bg-muted border border-muted-foreground/10"
            }`}
          >
            <div className="flex items-center gap-2">
              {areaValidation.error ? (
                <AlertCircle className="h-4 w-4 text-destructive flex-shrink-0" />
              ) : areaValidation.warning ? (
                <AlertTriangle className="h-4 w-4 text-yellow-600 dark:text-yellow-500 flex-shrink-0" />
              ) : (
                <MapPin className="h-4 w-4 text-muted-foreground flex-shrink-0" />
              )}
              <div>
                <span className="font-medium">Estimated Area: </span>
                <span className={areaValidation.error ? "text-destructive" : ""}>
                  {areaValidation.areaSqMiles.toFixed(1)} sq mi
                </span>
                {areaValidation.areaSqMiles > 0 && !areaValidation.error && !areaValidation.warning && (
                  <span className="text-muted-foreground"> (limit: {MAX_AREA_SQ_MILES.toLocaleString()} sq mi)</span>
                )}
              </div>
            </div>
            {areaValidation.warning && (
              <p className="mt-1 text-yellow-700 dark:text-yellow-400 ml-6">{areaValidation.warning}</p>
            )}
            {areaValidation.error && (
              <p className="mt-1 text-destructive ml-6">{areaValidation.error}</p>
            )}
            <p className="mt-2 text-xs text-muted-foreground ml-6">
              Tip: For urban areas, we recommend keeping input geometry under 100 sq mi for optimal results.
            </p>
          </div>
        ) : isGeoPackageParseFailure ? (
          <div className="rounded-lg px-4 py-3 text-sm bg-yellow-50 border border-yellow-200 dark:bg-yellow-950/20 dark:border-yellow-900/30">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-yellow-600 dark:text-yellow-500 flex-shrink-0" />
              <div>
                <span className="font-medium">Area Estimate: </span>
                <span className="text-yellow-700 dark:text-yellow-400">
                  Could not parse GeoPackage client-side
                </span>
              </div>
            </div>
            <p className="mt-2 text-xs text-yellow-700 dark:text-yellow-400 ml-6">
              This GeoPackage uses a geometry encoding that cannot be parsed in the browser.
              The {MAX_AREA_SQ_MILES.toLocaleString()} sq mi limit will be enforced during server-side processing.
            </p>
            <p className="mt-1 text-xs text-muted-foreground ml-6">
              Tip: For urban areas, we recommend keeping input geometry under 100 sq mi for optimal results.
            </p>
          </div>
        ) : !areaValidation && !isClientParseable && (
          <div className="rounded-lg px-4 py-3 text-sm bg-muted border border-muted-foreground/10">
            <div className="flex items-center gap-2">
              <MapPin className="h-4 w-4 text-muted-foreground flex-shrink-0" />
              <div>
                <span className="font-medium">Area Estimate: </span>
                <span className="text-muted-foreground">
                  Not available for this file format
                </span>
              </div>
            </div>
            <p className="mt-2 text-xs text-muted-foreground ml-6">
              Area estimation is not available for this format. The {MAX_AREA_SQ_MILES.toLocaleString()} sq mi limit will be enforced during processing.
            </p>
            <p className="mt-1 text-xs text-muted-foreground ml-6">
              Tip: For urban areas, we recommend keeping input geometry under 100 sq mi for optimal results.
            </p>
          </div>
        )}

        {/* Run Button */}
        <Button
          size="lg"
          onClick={handleRun}
          disabled={disabled || isAreaInvalid}
          className="w-full h-12 gap-2 text-base font-medium"
        >
          <Play className="h-5 w-5" />
          Run Processing
        </Button>
      </CardContent>
    </Card>
  )
}

/**
 * Generate a simple project ID
 */
function generateProjectId(): string {
  const timestamp = Date.now().toString(36)
  const random = Math.random().toString(36).substring(2, 6)
  return `PEIT-${timestamp}-${random}`.toUpperCase()
}
