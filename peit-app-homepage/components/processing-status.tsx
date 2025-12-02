"use client"

import { useEffect, useState } from "react"
import { Loader2, CheckCircle, Download, RotateCcw, XCircle } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Button } from "@/components/ui/button"

export interface ProgressUpdate {
  stage: 'upload' | 'geometry' | 'query' | 'map' | 'report' | 'complete' | 'error'
  message: string
  progress: number
  currentLayer?: number
  totalLayers?: number
  error?: string
}

interface ProcessingStatusProps {
  filename: string
  progressUpdates: ProgressUpdate[]
  isComplete: boolean
  isError: boolean
  errorMessage?: string
  downloadUrl?: string
  onDownload?: () => void
  onProcessAnother?: () => void
}

export function ProcessingStatus({
  filename,
  progressUpdates,
  isComplete,
  isError,
  errorMessage,
  downloadUrl,
  onDownload,
  onProcessAnother,
}: ProcessingStatusProps) {
  const [elapsedTime, setElapsedTime] = useState(0)
  const [startTime] = useState(Date.now())
  const [isDownloading, setIsDownloading] = useState(false)

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

  // Track elapsed time
  useEffect(() => {
    if (isComplete || isError) return

    const interval = setInterval(() => {
      setElapsedTime(Math.floor((Date.now() - startTime) / 1000))
    }, 1000)

    return () => clearInterval(interval)
  }, [startTime, isComplete, isError])

  // Get the latest progress update
  const latestUpdate = progressUpdates[progressUpdates.length - 1]
  const progress = latestUpdate?.progress ?? 0

  // Format elapsed time
  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

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
                Processing Failed
              </h2>

              <p className="mb-4 text-sm text-muted-foreground max-w-md">
                {errorMessage || "An unexpected error occurred while processing your file."}
              </p>

              <p className="mb-6 text-xs text-muted-foreground">
                Elapsed: {formatTime(elapsedTime)}
              </p>

              <Button
                onClick={onProcessAnother}
                variant="outline"
                className="gap-2"
              >
                <RotateCcw className="h-4 w-4" />
                Try Again
              </Button>
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
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-primary/20">
                <CheckCircle className="h-7 w-7 text-primary" />
              </div>

              <h2 className="mb-2 text-xl font-semibold text-foreground">
                Processing Complete!
              </h2>

              <p className="mb-2 text-sm text-muted-foreground">
                Your geospatial data has been processed successfully.
              </p>

              <p className="mb-6 text-xs text-muted-foreground">
                Completed in {formatTime(elapsedTime)}
              </p>

              <div className="flex gap-3">
                <Button
                  onClick={handleDownloadClick}
                  className="gap-2"
                  size="lg"
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
                      Download Results
                    </>
                  )}
                </Button>
                <Button
                  onClick={onProcessAnother}
                  variant="outline"
                  size="lg"
                  className="gap-2"
                  disabled={isDownloading}
                >
                  <RotateCcw className="h-4 w-4" />
                  Process Another
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

            <p className="mb-4 text-sm text-muted-foreground min-h-[20px]">
              {latestUpdate?.message || "Initializing..."}
            </p>

            {/* Layer count if available */}
            {latestUpdate?.currentLayer && latestUpdate?.totalLayers && (
              <p className="mb-4 text-xs text-muted-foreground">
                Layer {latestUpdate.currentLayer} of {latestUpdate.totalLayers}
              </p>
            )}

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
