"use client"

import { useState, useCallback } from "react"
import { Play, Settings } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"

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
}

// Constants
const DEFAULT_BUFFER_FEET = 500
const MIN_BUFFER_FEET = 0
const MAX_BUFFER_FEET = 26400 // 5 miles in feet

const DEFAULT_CLIP_MILES = 1.0
const MIN_CLIP_MILES = 0.1
const MAX_CLIP_MILES = 5.0

export function ConfigPanel({ filename, onRun, disabled = false }: ConfigPanelProps) {
  const [projectName, setProjectName] = useState("")
  const [projectId, setProjectId] = useState("")
  const [bufferDistanceFeet, setBufferDistanceFeet] = useState(DEFAULT_BUFFER_FEET)
  const [clipBufferMiles, setClipBufferMiles] = useState(DEFAULT_CLIP_MILES)

  // Get filename without extension for default project name
  const defaultProjectName = filename.replace(/\.[^/.]+$/, "")

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

        {/* Run Button */}
        <Button
          size="lg"
          onClick={handleRun}
          disabled={disabled}
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
