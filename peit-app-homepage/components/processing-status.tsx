"use client"

import { useEffect, useState, useRef } from "react"
import { Loader2, CheckCircle, Download, RotateCcw, XCircle, ExternalLink, Copy, Check, FileText, FileSpreadsheet } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Button } from "@/components/ui/button"

// Fun messages for layer querying stage (defined outside component to prevent re-creation)
const FUN_MESSAGES = [
  "Querying environmental databases...",
  "Consulting the map spirits...",
  "Asking nicely for data...",
  "Downloading the internet...",
  "Herding digital sheep...",
  "Spinning up the hamster wheel...",
  "Bribing the servers with cookies...",
  "Teaching pixels to dance...",
  "Untangling spaghetti code...",
  "Warming up the flux capacitor...",
  "Calibrating the coffee machine...",
  "Negotiating with the cloud...",
  "Summoning the data wizards...",
  "Polishing the algorithms...",
  "Feeding the binary hamsters...",
  "Optimizing the chaos engine...",
  "Convincing electrons to cooperate...",
  "Translating cartographer hieroglyphics...",
  "Befriending the database gremlins...",
  "Coaxing features out of hiding...",
  "Performing digital archaeology...",
  "Asking satellites very politely...",
  "Decoding the ancient GIS scrolls...",
  "Persuading polygons to behave...",
  "Wrangling wayward waypoints...",
  "Charming the coordinate systems...",
  "Taming wild geometries...",
  "Negotiating with stubborn servers...",
  "Consulting the oracle of spatial data...",
  "Tickling the database until it laughs...",
  "Singing lullabies to angry APIs...",
  "Playing hide and seek with features...",
  "Teaching old maps new tricks...",
  "Convincing layers to share secrets...",
  "Bribing the GIS gods with RAM...",
  "Whispering sweet nothings to shapefiles...",
  "Juggling spatial references...",
  "Performing arcane GIS rituals...",
  "Translating server grumbles...",
  "Deciphering environmental enigmas...",
  "Channeling the spirit of Mercator...",
  "Appeasing the projection demons...",
  "Convincing bytes to play nice...",
  "Herding cats with GPS collars...",
  "Teaching vectors to vector...",
  "Explaining maps to computers...",
  "Negotiating feature treaties...",
  "Persuading servers it's not a DDoS...",
  "Asking databases to share toys...",
  "Convincing layers to line up...",
  "Playing matchmaker for coordinates...",
  "Teaching features to take turns...",
  "Bribing the network with packets...",
  "Convincing servers we're friends...",
  "Explaining urgency to lazy APIs...",
  "Teaching patience to impatient queries...",
]

export interface ProgressUpdate {
  stage: 'upload' | 'geometry_input' | 'layer_querying' | 'layer_query' | 'map_generation' | 'report_generation' | 'blob_upload' | 'complete' | 'error'
  message: string
  progress: number
  layer_name?: string              // Name of current layer being queried
  currentLayer?: number            // Layers completed (1-indexed)
  totalLayers?: number             // Total layers to process
  features_found?: number          // Features found in current layer
  estimated_completion_time?: number  // Predicted total job time (seconds)
  input_area_sq_miles?: number     // Input area size for end-stage weighting
  bellwether_feature_counts?: {    // Feature counts from bellwether layers
    rcra: number
    npdes: number
    wetlands: number
  }
  error?: string
}

interface ProcessingStatusProps {
  filename: string
  progressUpdates: ProgressUpdate[]
  isComplete: boolean
  isError: boolean
  errorMessage?: string
  downloadUrl?: string
  mapUrl?: string
  pdfUrl?: string
  xlsxUrl?: string
  showCompletionTime?: boolean
  onDownload?: () => void
  onProcessAnother?: () => void
  // Try again callback for error state (preserves file/config)
  onTryAgain?: () => void
  // Auth callbacks for rate limit errors (anonymous users)
  isAuthenticated?: boolean
  onSignUp?: () => void
  onSignIn?: () => void
}

export function ProcessingStatus({
  filename,
  progressUpdates,
  isComplete,
  isError,
  errorMessage,
  downloadUrl,
  mapUrl,
  pdfUrl,
  xlsxUrl,
  showCompletionTime = true,
  onDownload,
  onProcessAnother,
  onTryAgain,
  isAuthenticated = false,
  onSignUp,
  onSignIn,
}: ProcessingStatusProps) {
  const [elapsedTime, setElapsedTime] = useState(0)
  const [startTime] = useState(Date.now())
  const [isDownloading, setIsDownloading] = useState(false)
  const [copied, setCopied] = useState(false)

  // Time-based predictive progress display (PURE time-based, never jumps)
  const [displayProgress, setDisplayProgress] = useState(0)
  const [estimatedTotalTime, setEstimatedTotalTime] = useState(45) // Initial default (seconds)
  const [inputAreaSize, setInputAreaSize] = useState<number | null>(null) // For end-stage weighting

  // Track layers we've already logged to prevent duplicates (use ref to avoid re-renders)
  const loggedLayersRef = useRef(new Set<string>())
  const runningFeatureTotalRef = useRef(0)

  // Client-side fun message rotation (changes every 3 seconds consistently)
  const [funMessage, setFunMessage] = useState('')
  const funMessageInitialized = useRef(false)
  const remainingMessages = useRef<string[]>([])  // Pool of unshown messages

  // Copy map URL to clipboard
  const copyMapUrl = async () => {
    if (mapUrl) {
      try {
        await navigator.clipboard.writeText(mapUrl)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      } catch (err) {
        console.error("Failed to copy:", err)
      }
    }
  }

  // Handle download with loading state
  const handleDownloadClick = async () => {
    if (!onDownload) return
    setIsDownloading(true)
    try {
      await onDownload()
    } finally {
      setIsDownloading(false)
    }
  }

  // Get the latest progress update
  const latestUpdate = progressUpdates[progressUpdates.length - 1]

  // Track elapsed time
  useEffect(() => {
    if (isComplete || isError) return

    const interval = setInterval(() => {
      setElapsedTime(Math.floor((Date.now() - startTime) / 1000))
    }, 1000)

    return () => clearInterval(interval)
  }, [startTime, isComplete, isError])

  // Helper function to get next random message without repeating until all shown
  const getNextFunMessage = () => {
    // If pool is empty, refill with all messages
    if (remainingMessages.current.length === 0) {
      remainingMessages.current = [...FUN_MESSAGES]
    }

    // Pick random message from remaining pool
    const randomIndex = Math.floor(Math.random() * remainingMessages.current.length)
    const message = remainingMessages.current[randomIndex]

    // Remove selected message from pool
    remainingMessages.current.splice(randomIndex, 1)

    return message
  }

  // Client-side fun message rotation (every 3 seconds during layer querying)
  useEffect(() => {
    if (isComplete || isError) {
      funMessageInitialized.current = false
      remainingMessages.current = []  // Reset pool
      return
    }

    if (latestUpdate?.stage !== 'layer_query' && latestUpdate?.stage !== 'layer_querying') {
      funMessageInitialized.current = false
      remainingMessages.current = []  // Reset pool
      return
    }

    // Pick initial random message only once when entering layer querying stage
    if (!funMessageInitialized.current) {
      setFunMessage(getNextFunMessage())
      funMessageInitialized.current = true
    }

    // Set up interval to rotate messages every 3 seconds
    const interval = setInterval(() => {
      setFunMessage(getNextFunMessage())
    }, 3000) // Change every 3 seconds

    return () => clearInterval(interval)
  }, [latestUpdate?.stage, isComplete, isError])

  // Track running feature total (no logging - for internal tracking only)
  useEffect(() => {
    if (latestUpdate?.stage === 'layer_query' && latestUpdate.features_found !== undefined) {
      // Create unique key for this layer completion event
      const layerKey = `${latestUpdate.currentLayer}-${latestUpdate.layer_name}`

      // Only count if we haven't seen this layer completion yet
      if (latestUpdate.layer_name && !loggedLayersRef.current.has(layerKey)) {
        loggedLayersRef.current.add(layerKey)
        runningFeatureTotalRef.current += latestUpdate.features_found
      }
    }

    // Reset tracking when starting new job
    if (latestUpdate?.stage === 'upload') {
      loggedLayersRef.current.clear()
      runningFeatureTotalRef.current = 0
    }
  }, [latestUpdate])

  // Update estimated time from SSE (IGNORE backend progress percentages)
  useEffect(() => {
    // Capture input area size for end-stage time weighting
    if (latestUpdate?.input_area_sq_miles != null) {
      setInputAreaSize(latestUpdate.input_area_sq_miles)
    }

    // Update estimated total time when backend provides prediction
    if (latestUpdate?.estimated_completion_time != null) {
      let newEstimate = latestUpdate.estimated_completion_time

      // Sophisticated end-stage time calculation based on area AND feature density
      if (inputAreaSize !== null && latestUpdate?.bellwether_feature_counts) {
        const { rcra, npdes, wetlands } = latestUpdate.bellwether_feature_counts
        const maxFeatures = Math.max(rcra, npdes, wetlands)

        let endStageTime = 5 // Base time

        // Area-based multiplier
        if (inputAreaSize > 300) {
          // Extra large areas
          endStageTime += 90
        } else if (inputAreaSize > 200) {
          // Large areas
          endStageTime += 40
        } else if (inputAreaSize > 50) {
          // Medium areas
          endStageTime += 10
        }

        // Feature density multiplier (high feature count = more time for map rendering)
        if (maxFeatures > 5000) {
          endStageTime += 30 // Very high density
        } else if (maxFeatures > 1000) {
          endStageTime += 15 // High density
        } else if (maxFeatures > 500) {
          endStageTime += 5 // Medium density
        }

        newEstimate += endStageTime
      } else if (inputAreaSize !== null) {
        // Fallback to area-only estimation if bellwether counts unavailable
        let endStageTime = 5
        if (inputAreaSize > 300) {
          endStageTime = 95
        } else if (inputAreaSize > 200) {
          endStageTime = 45
        } else if (inputAreaSize > 50) {
          endStageTime = 15
        }
        newEstimate += endStageTime
      }

      setEstimatedTotalTime(newEstimate)
    }

    // When complete, push to 100%
    if (isComplete) {
      setDisplayProgress(100)
    }
  }, [latestUpdate, isComplete, inputAreaSize])

  // PURE time-based smooth progress (NEVER jumps, NEVER goes backwards)
  useEffect(() => {
    if (isComplete || isError) return

    const interval = setInterval(() => {
      const elapsed = (Date.now() - startTime) / 1000

      // Calculate time-based progress percentage
      // Dynamic cap based on current stage to show end-stage progress
      let maxProgress = 99
      if (latestUpdate?.stage === 'map_generation') {
        maxProgress = 94 // Show movement through map generation (92% + 2%)
      } else if (latestUpdate?.stage === 'report_generation') {
        maxProgress = 96 // Show movement through report generation (94% + 2%)
      } else if (latestUpdate?.stage === 'blob_upload') {
        maxProgress = 98 // Show movement through blob upload (96% + 1%)
      }

      let timeProgress = Math.min(maxProgress, (elapsed / estimatedTotalTime) * 100)

      // CRITICAL: Only INCREMENT progress, never decrement
      setDisplayProgress(prev => {
        const newProgress = Math.floor(timeProgress)
        // Only update if new progress is HIGHER than current
        return newProgress > prev ? newProgress : prev
      })
    }, 100) // Update every 100ms = 10 updates/second = smooth 1% increments

    return () => clearInterval(interval)
  }, [estimatedTotalTime, startTime, isComplete, isError, latestUpdate?.stage])

  // Format elapsed time
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  // Check if this is a rate limit error for anonymous users
  const isAnonymousRateLimitError = isError &&
    !isAuthenticated &&
    errorMessage?.toLowerCase().includes('anonymous') &&
    errorMessage?.toLowerCase().includes('sign up')

  // Error state
  if (isError) {
    return (
      <div className="mx-auto max-w-2xl">
        <Card className="border-destructive/50 bg-destructive/5">
          <CardContent className="pt-6">
            <div className="flex flex-col items-center text-center">
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-destructive/20">
                <XCircle className="h-7 w-7 text-destructive" />
              </div>

              <h2 className="mb-2 text-xl font-semibold text-foreground">
                {isAnonymousRateLimitError ? "Daily Limit Reached" : "Processing Failed"}
              </h2>

              <p className="mb-4 text-sm text-muted-foreground max-w-md">
                {errorMessage || "An unexpected error occurred while processing your file."}
              </p>

              <p className="mb-6 text-xs text-muted-foreground">
                Elapsed: {formatTime(elapsedTime)}
              </p>

              {/* Show sign up/sign in buttons for anonymous rate limit errors */}
              {isAnonymousRateLimitError && onSignUp && onSignIn ? (
                <div className="flex flex-col gap-4">
                  <div className="flex gap-3 justify-center">
                    <Button onClick={onSignUp}>
                      Sign Up
                    </Button>
                    <Button
                      variant="outline"
                      onClick={onSignIn}
                      className="hover:bg-muted-foreground/10"
                    >
                      Sign In
                    </Button>
                  </div>
                  <Button
                    onClick={onTryAgain ?? onProcessAnother}
                    variant="ghost"
                    size="sm"
                    className="gap-2 hover:bg-muted-foreground/10"
                  >
                    <RotateCcw className="h-4 w-4" />
                    Try Again Tomorrow
                  </Button>
                </div>
              ) : (
                <div className="flex flex-col gap-3 items-center">
                  <Button
                    onClick={onTryAgain ?? onProcessAnother}
                    variant="outline"
                    className="gap-2"
                  >
                    <RotateCcw className="h-4 w-4" />
                    Try Again
                  </Button>
                  {onProcessAnother && onTryAgain && (
                    <button
                      onClick={onProcessAnother}
                      className="text-xs text-muted-foreground hover:text-foreground underline"
                    >
                      or start fresh with a different file
                    </button>
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Complete state
  if (isComplete) {
    return (
      <div className="mx-auto max-w-2xl">
        <Card className="border-primary/50 bg-primary/5">
          <CardContent className="pt-6">
            <div className="flex flex-col items-center text-center">
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-green-500/20">
                <CheckCircle className="h-7 w-7 text-green-600 dark:text-green-500" />
              </div>

              <h2 className="mb-2 text-xl font-semibold text-foreground">
                Processing Complete!
              </h2>

              <p className="mb-2 text-sm text-muted-foreground">
                Your geospatial data has been processed successfully.
              </p>

              {showCompletionTime && (
                <p className="mb-6 text-xs text-muted-foreground">
                  Completed in {formatTime(elapsedTime)}
                </p>
              )}
              {!showCompletionTime && <div className="mb-6" />}

              <div className="flex flex-col gap-4 w-full max-w-md">
                {/* Primary actions */}
                <div className="flex gap-3 justify-center">
                  {mapUrl && (
                    <Button
                      onClick={() => window.open(mapUrl, '_blank')}
                      className="gap-2"
                      size="lg"
                    >
                      <ExternalLink className="h-5 w-5" />
                      View Live Map
                    </Button>
                  )}
                  <Button
                    onClick={handleDownloadClick}
                    variant={mapUrl ? "outline" : "default"}
                    size="lg"
                    className="gap-2"
                    disabled={isDownloading}
                  >
                    {isDownloading ? (
                      <>
                        <Loader2 className="h-5 w-5 animate-spin" />
                        Downloading...
                      </>
                    ) : (
                      <>
                        <Download className="h-5 w-5" />
                        Download ZIP
                      </>
                    )}
                  </Button>
                </div>

                {/* Share section */}
                {mapUrl && (
                  <div className="flex items-center justify-center gap-2 text-sm">
                    <span className="text-muted-foreground">Share:</span>
                    <code className="bg-muted px-2 py-1 rounded text-xs max-w-[200px] truncate">
                      {mapUrl}
                    </code>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={copyMapUrl}
                      className="gap-1 h-8 hover:bg-muted-foreground/10 active:bg-muted-foreground/20 transition-colors duration-200"
                    >
                      {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                      {copied ? 'Copied!' : 'Copy'}
                    </Button>
                  </div>
                )}

                {/* Direct report links */}
                {(pdfUrl || xlsxUrl) && (
                  <div className="flex gap-4 justify-center text-sm">
                    {pdfUrl && (
                      <a
                        href={pdfUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline flex items-center gap-1"
                      >
                        <FileText className="h-4 w-4" />
                        PDF Report
                      </a>
                    )}
                    {xlsxUrl && (
                      <a
                        href={xlsxUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline flex items-center gap-1"
                      >
                        <FileSpreadsheet className="h-4 w-4" />
                        Excel Report
                      </a>
                    )}
                  </div>
                )}

                {/* Expiration notice */}
                {mapUrl && (
                  <p className="text-xs text-muted-foreground text-center">
                    Live links expire in 7 days
                  </p>
                )}


                {/* Process another */}
                <Button
                  onClick={onProcessAnother}
                  variant="ghost"
                  size="sm"
                  className="gap-2 mx-auto hover:bg-muted-foreground/10 active:bg-muted-foreground/20 transition-colors duration-200"
                  disabled={isDownloading}
                >
                  <RotateCcw className="h-4 w-4" />
                  Process Another File
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Processing state
  return (
    <div className="mx-auto max-w-2xl">
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col items-center text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-primary/10">
              <Loader2 className="h-7 w-7 text-primary animate-spin" />
            </div>

            <h2 className="mb-2 text-xl font-semibold text-foreground">
              Processing: {filename}
            </h2>

            {/* Progress bar */}
            <div className="w-full max-w-md mb-4">
              <Progress value={displayProgress} className="h-3" />
            </div>

            {/* Progress percentage and current task */}
            <div className="mb-2 text-2xl font-bold text-primary">
              {displayProgress}%
            </div>

            {/* Current task message */}
            <p className="mb-4 text-sm text-muted-foreground min-h-[20px]">
              {(latestUpdate?.stage === 'layer_query' || latestUpdate?.stage === 'layer_querying') && funMessage
                ? funMessage
                : latestUpdate?.message || "Initializing..."}
            </p>

            {/* Elapsed time */}
            <p className="text-xs text-muted-foreground">
              Elapsed: {formatTime(elapsedTime)}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
