"use client"

import { useState, useCallback, useEffect, useRef } from "react"
import { Play, Settings, AlertTriangle, AlertCircle, MapPin, HelpCircle } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip"
import type { FeatureCollection } from "geojson"
import {
  validateGeometryArea,
  detectGeometryType,
  generateLocationProjectId,
  type AreaValidation,
  type DetectedGeometryType,
  type LocationData,
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
  /** Location data from reverse geocoding (for generating location-based project ID) */
  locationData?: LocationData | null
  /** Initial config values to restore (for edit mode) */
  initialConfig?: Partial<ProcessingConfig>
  /** Called when any config value changes */
  onConfigChange?: (config: Partial<ProcessingConfig>) => void
}

// Constants
const DEFAULT_BUFFER_FEET = 500
const MIN_BUFFER_FEET = 1
const SLIDER_MIN_BUFFER_FEET = 0 // Slider uses 0 for round increments, but value is clamped to MIN_BUFFER_FEET
const MAX_BUFFER_FEET = 26400 // 5 miles in feet

const DEFAULT_CLIP_MILES = 0.2
const MIN_CLIP_MILES = 0.1
const MAX_CLIP_MILES = 0.5

// Tooltip content for each configuration option
const TOOLTIPS = {
  projectName: "The display name for your project that appears in the generated map and reports. Defaults to the uploaded filename if left blank.",
  projectId: "A unique identifier for tracking and referencing this processing run. Appears in the PDF report and metadata files. Auto-generated if left blank.",
  inputBuffer: "The distance to expand around your input geometry to create the search area. Points become circular search areas; lines become corridor-style buffers. Larger buffers capture more environmental features but increase processing time.",
  clipBuffer: "Controls how far beyond your input geometry the results are clipped. Environmental features that extend beyond this distance are trimmed. Reduces output file size and focuses results on the area of interest.",
}

// Helper component for label with tooltip
// Uses a button wrapper so tooltips work on mobile (tap to focus) and desktop (hover)
function LabelWithTooltip({ label, tooltip, htmlFor }: { label: string; tooltip: string; htmlFor?: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className="inline-flex items-center justify-center rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1"
            aria-label={`More info about ${label}`}
          >
            <HelpCircle className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground transition-colors" />
          </button>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs">
          <p>{tooltip}</p>
        </TooltipContent>
      </Tooltip>
    </div>
  )
}

export function ConfigPanel({ filename, onRun, disabled = false, geojsonData, locationData, initialConfig, onConfigChange }: ConfigPanelProps) {
  const [projectName, setProjectName] = useState(initialConfig?.projectName ?? "")
  const [projectId, setProjectId] = useState(initialConfig?.projectId ?? "")
  const [bufferDistanceFeet, setBufferDistanceFeet] = useState(initialConfig?.bufferDistanceFeet ?? DEFAULT_BUFFER_FEET)
  const [clipBufferMiles, setClipBufferMiles] = useState(initialConfig?.clipBufferMiles ?? DEFAULT_CLIP_MILES)
  const [areaValidation, setAreaValidation] = useState<AreaValidation | null>(null)
  const [detectedGeomType, setDetectedGeomType] = useState<DetectedGeometryType | null>(null)
  const [hasAutoSetBuffer, setHasAutoSetBuffer] = useState(false)
  const [isEditingBuffer, setIsEditingBuffer] = useState(false)
  const [bufferInputValue, setBufferInputValue] = useState("")
  const bufferInputRef = useRef<HTMLInputElement>(null)
  const [isEditingClipBuffer, setIsEditingClipBuffer] = useState(false)
  const [clipBufferInputValue, setClipBufferInputValue] = useState("")
  const clipBufferInputRef = useRef<HTMLInputElement>(null)

  // Get filename without extension for default project name
  const defaultProjectName = filename.replace(/\.[^/.]+$/, "")

  // Detect geometry type and auto-set buffer when geojsonData changes
  useEffect(() => {
    if (geojsonData) {
      const geomType = detectGeometryType(geojsonData)
      setDetectedGeomType(geomType)

      // Auto-set buffer to 0 for polygon-only inputs (only on first detection)
      // Skip auto-set if we have initial config values (user already configured)
      if (!hasAutoSetBuffer && initialConfig?.bufferDistanceFeet === undefined) {
        if (geomType === 'polygon') {
          setBufferDistanceFeet(0)
        } else {
          setBufferDistanceFeet(DEFAULT_BUFFER_FEET)
        }
        setHasAutoSetBuffer(true)
      } else if (!hasAutoSetBuffer && initialConfig?.bufferDistanceFeet !== undefined) {
        // Mark as auto-set to prevent future auto-setting
        setHasAutoSetBuffer(true)
      }

      // Safeguard: if geometry is NOT polygon but buffer is 0, auto-correct to default
      // This handles edge case where restored config from polygon session is used with line/point file
      if (geomType !== 'polygon' && bufferDistanceFeet === 0) {
        setBufferDistanceFeet(DEFAULT_BUFFER_FEET)
      }
    } else {
      setDetectedGeomType(null)
      setHasAutoSetBuffer(false)
    }
  }, [geojsonData, hasAutoSetBuffer, initialConfig?.bufferDistanceFeet, bufferDistanceFeet])

  // Notify parent of config changes
  useEffect(() => {
    onConfigChange?.({
      projectName,
      projectId,
      bufferDistanceFeet,
      clipBufferMiles,
    })
  }, [projectName, projectId, bufferDistanceFeet, clipBufferMiles, onConfigChange])

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
      projectId: projectId.trim() || generateLocationProjectId(locationData),
      bufferDistanceFeet,
      clipBufferMiles,
    })
  }, [projectName, projectId, bufferDistanceFeet, clipBufferMiles, defaultProjectName, locationData, onRun])

  // Format buffer distance for display
  const formatBufferFeet = (feet: number): string => {
    if (feet >= 5280) {
      const miles = feet / 5280
      return `${feet.toLocaleString()} ft (${miles.toFixed(2)} mi)`
    }
    return `${feet.toLocaleString()} ft`
  }

  // Handle starting buffer edit mode
  const startBufferEdit = () => {
    if (disabled) return
    setBufferInputValue(bufferDistanceFeet.toString())
    setIsEditingBuffer(true)
    // Focus input after state update
    setTimeout(() => bufferInputRef.current?.select(), 0)
  }

  // Handle buffer input validation and save
  const saveBufferInput = () => {
    const parsed = parseInt(bufferInputValue, 10)
    if (!isNaN(parsed)) {
      // Clamp to valid range
      const clamped = Math.max(MIN_BUFFER_FEET, Math.min(MAX_BUFFER_FEET, parsed))
      setBufferDistanceFeet(clamped)
    }
    setIsEditingBuffer(false)
  }

  // Handle buffer input key events
  const handleBufferKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      saveBufferInput()
    } else if (e.key === 'Escape') {
      setIsEditingBuffer(false)
    }
  }

  // Handle starting clip buffer edit mode
  const startClipBufferEdit = () => {
    if (disabled) return
    setClipBufferInputValue(clipBufferMiles.toString())
    setIsEditingClipBuffer(true)
    setTimeout(() => clipBufferInputRef.current?.select(), 0)
  }

  // Handle clip buffer input validation and save
  const saveClipBufferInput = () => {
    const parsed = parseFloat(clipBufferInputValue)
    if (!isNaN(parsed)) {
      // Clamp to valid range (0.1-5.0, cannot be 0)
      const clamped = Math.max(MIN_CLIP_MILES, Math.min(MAX_CLIP_MILES, parsed))
      // Round to 1 decimal place
      setClipBufferMiles(Math.round(clamped * 10) / 10)
    }
    setIsEditingClipBuffer(false)
  }

  // Handle clip buffer input key events
  const handleClipBufferKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      saveClipBufferInput()
    } else if (e.key === 'Escape') {
      setIsEditingClipBuffer(false)
    }
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
          <LabelWithTooltip label="Project Name" tooltip={TOOLTIPS.projectName} htmlFor="projectName" />
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
          <LabelWithTooltip label="Project ID" tooltip={TOOLTIPS.projectId} htmlFor="projectId" />
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

        {/* Input Buffer Distance - only shown for non-polygon geometries */}
        {detectedGeomType !== 'polygon' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <LabelWithTooltip label="Input Buffer Distance" tooltip={TOOLTIPS.inputBuffer} />
              {isEditingBuffer ? (
                <input
                  ref={bufferInputRef}
                  type="number"
                  value={bufferInputValue}
                  onChange={(e) => setBufferInputValue(e.target.value)}
                  onBlur={saveBufferInput}
                  onKeyDown={handleBufferKeyDown}
                  min={MIN_BUFFER_FEET}
                  max={MAX_BUFFER_FEET}
                  className="w-24 h-7 px-2 text-sm font-medium text-right border rounded focus:outline-none focus:ring-2 focus:ring-ring"
                />
              ) : (
                <button
                  type="button"
                  onClick={startBufferEdit}
                  disabled={disabled}
                  className="text-sm font-medium text-foreground hover:text-primary hover:underline cursor-pointer disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
                  title="Click to edit"
                >
                  {formatBufferFeet(bufferDistanceFeet)}
                </button>
              )}
            </div>
            <Slider
              value={[bufferDistanceFeet]}
              onValueChange={(value) => setBufferDistanceFeet(Math.max(MIN_BUFFER_FEET, value[0]))}
              min={SLIDER_MIN_BUFFER_FEET}
              max={MAX_BUFFER_FEET}
              step={100}
              disabled={disabled}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>1 ft</span>
              <span>26,400 ft (5 mi)</span>
            </div>
            {detectedGeomType && (
              <p className="text-xs text-muted-foreground">
                {detectedGeomType === 'line' && "Line detected - buffer applied on both sides"}
                {detectedGeomType === 'point' && "Point detected - buffer creates circular search area"}
                {detectedGeomType === 'mixed' && "Mixed geometry - buffer applied to points/lines only"}
              </p>
            )}
          </div>
        )}

        {/* Clip Buffer Distance */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <LabelWithTooltip label="Clip Buffer Distance" tooltip={TOOLTIPS.clipBuffer} />
            {isEditingClipBuffer ? (
              <input
                ref={clipBufferInputRef}
                type="number"
                value={clipBufferInputValue}
                onChange={(e) => setClipBufferInputValue(e.target.value)}
                onBlur={saveClipBufferInput}
                onKeyDown={handleClipBufferKeyDown}
                min={MIN_CLIP_MILES}
                max={MAX_CLIP_MILES}
                step={0.1}
                className="w-20 h-7 px-2 text-sm font-medium text-right border rounded focus:outline-none focus:ring-2 focus:ring-ring"
              />
            ) : (
              <button
                type="button"
                onClick={startClipBufferEdit}
                disabled={disabled}
                className="text-sm font-medium text-foreground hover:text-primary hover:underline cursor-pointer disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
                title="Click to edit"
              >
                {clipBufferMiles.toFixed(1)} mi
              </button>
            )}
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
            <span>0.5 mi</span>
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
