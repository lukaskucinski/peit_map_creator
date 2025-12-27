"use client"

import { useEffect, useState } from "react"
import { Loader2, CheckCircle, Download, RotateCcw, XCircle, ExternalLink, Copy, Check, FileText, FileSpreadsheet } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Button } from "@/components/ui/button"

export interface ProgressUpdate {
  stage: 'upload' | 'geometry_input' | 'layer_querying' | 'layer_query' | 'map_generation' | 'report_generation' | 'blob_upload' | 'complete' | 'error'
  message: string
  progress: number
  layer_name?: string         // Name of current layer being queried
  currentLayer?: number       // Layers completed (1-indexed)
  totalLayers?: number        // Total layers to process
  features_found?: number     // Features found in current layer
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
  const [runningFeatureTotal, setRunningFeatureTotal] = useState(0)

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
  const progress = latestUpdate?.progress ?? 0

  // Track elapsed time
  useEffect(() => {
    if (isComplete || isError) return

    const interval = setInterval(() => {
      setElapsedTime(Math.floor((Date.now() - startTime) / 1000))
    }, 1000)

    return () => clearInterval(interval)
  }, [startTime, isComplete, isError])

  // Track running feature total
  useEffect(() => {
    if (latestUpdate?.stage === 'layer_query' && latestUpdate.features_found !== undefined) {
      setRunningFeatureTotal(prev => prev + latestUpdate.features_found!)
    }
  }, [latestUpdate])

  // Reset feature total when starting new job
  useEffect(() => {
    if (latestUpdate?.stage === 'upload') {
      setRunningFeatureTotal(0)
    }
  }, [latestUpdate?.stage])

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
              <Progress value={progress} className="h-3" />
            </div>

            {/* Progress percentage and current task */}
            <div className="mb-2 text-2xl font-bold text-primary">
              {progress}%
            </div>

            {/* Current task message */}
            <p className="mb-2 text-sm text-muted-foreground min-h-[20px]">
              {latestUpdate?.message || "Initializing..."}
            </p>

            {/* Layer progress details (only show during layer querying) */}
            {latestUpdate?.stage === 'layer_querying' && latestUpdate?.totalLayers && (
              <div className="mb-4 w-full max-w-md">
                <div className="flex justify-between text-xs text-muted-foreground mb-1">
                  <span>
                    Layer {latestUpdate.currentLayer || 0} of {latestUpdate.totalLayers}
                  </span>
                  {latestUpdate.features_found !== undefined && (
                    <span className="text-primary font-medium">
                      {latestUpdate.features_found} {latestUpdate.features_found === 1 ? 'feature' : 'features'}
                    </span>
                  )}
                </div>

                {/* Current layer name (truncated if long) */}
                {latestUpdate.layer_name && (
                  <div className="text-xs text-muted-foreground/75 truncate text-left">
                    {latestUpdate.layer_name}
                  </div>
                )}
              </div>
            )}

            {/* Elapsed time */}
            <p className="text-xs text-muted-foreground">
              Elapsed: {formatTime(elapsedTime)}
            </p>

            {/* Running feature total */}
            {latestUpdate?.stage === 'layer_querying' && runningFeatureTotal > 0 && (
              <p className="text-xs text-primary font-medium mt-1">
                Total: {runningFeatureTotal.toLocaleString()} features found
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
