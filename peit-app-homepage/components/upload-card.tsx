"use client"

import type React from "react"
import { useState, useCallback } from "react"
import { Upload, FileCheck, X, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { validateFile, formatFileSize, getAllowedTypesDescription } from "@/lib/validation"

interface UploadCardProps {
  onFileSelected?: (file: File) => void
  onFileCleared?: () => void
  selectedFile?: File | null
  disabled?: boolean
}

export function UploadCard({
  onFileSelected,
  onFileCleared,
  selectedFile: externalSelectedFile,
  disabled = false
}: UploadCardProps) {
  const [isDragging, setIsDragging] = useState(false)
  const [internalSelectedFile, setInternalSelectedFile] = useState<File | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)

  // Use external state if provided, otherwise use internal state
  const selectedFile = externalSelectedFile !== undefined ? externalSelectedFile : internalSelectedFile

  const handleFile = useCallback((file: File) => {
    setValidationError(null)

    const result = validateFile(file)
    if (!result.valid) {
      setValidationError(result.error || "Invalid file")
      setInternalSelectedFile(null)
      return
    }

    setInternalSelectedFile(file)
    onFileSelected?.(file)
  }, [onFileSelected])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    if (!disabled) {
      setIsDragging(true)
    }
  }, [disabled])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    if (disabled) return

    const files = e.dataTransfer.files
    if (files.length > 0) {
      handleFile(files[0])
    }
  }, [disabled, handleFile])

  const handleFileSelect = useCallback(() => {
    if (disabled) return

    const input = document.createElement("input")
    input.type = "file"
    input.accept = ".geojson,.json,.gpkg,.kml,.kmz,.zip"
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0]
      if (file) {
        handleFile(file)
      }
    }
    input.click()
  }, [disabled, handleFile])

  const handleClearFile = useCallback(() => {
    setInternalSelectedFile(null)
    setValidationError(null)
    onFileCleared?.()
  }, [onFileCleared])

  // Render selected file state
  if (selectedFile) {
    return (
      <div className="mx-auto max-w-2xl">
        <div className="relative rounded-2xl border-2 border-primary bg-primary/5 p-8 md:p-12 transition-all duration-200 shadow-sm">
          <div className="flex flex-col items-center text-center">
            <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-primary/20">
              <FileCheck className="h-7 w-7 text-primary" />
            </div>

            <h2 className="mb-2 text-xl font-semibold text-foreground">
              File Selected
            </h2>

            <div className="mb-4 flex items-center gap-2 rounded-lg bg-card px-4 py-2 border border-border">
              <span className="text-sm font-medium text-foreground truncate max-w-[300px]">
                {selectedFile.name}
              </span>
              <span className="text-xs text-muted-foreground">
                ({formatFileSize(selectedFile.size)})
              </span>
              {!disabled && (
                <button
                  onClick={handleClearFile}
                  className="ml-2 p-1 rounded-full hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                  title="Remove file"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>

            <p className="text-sm text-muted-foreground">
              Configure options below, then click Run to process
            </p>
          </div>
        </div>
      </div>
    )
  }

  // Render upload state
  return (
    <div className="mx-auto max-w-2xl">
      <div
        className={cn(
          "relative rounded-2xl border-2 border-dashed bg-card p-8 md:p-12 transition-all duration-200 shadow-sm",
          disabled
            ? "opacity-50 cursor-not-allowed border-border"
            : isDragging
              ? "border-primary bg-accent/50 scale-[1.01]"
              : "border-border hover:border-primary/50",
        )}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="flex flex-col items-center text-center">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-primary/10">
            <MapPinIcon className="h-7 w-7 text-primary" />
          </div>

          <h1 className="mb-2 text-2xl font-semibold text-foreground md:text-3xl text-balance">
            Geospatial File Processor
          </h1>

          <p className="mb-6 max-w-md text-muted-foreground text-pretty">
            Upload a geospatial file to process and visualize your data in seconds.
          </p>

          {/* Validation Error */}
          {validationError && (
            <div className="mb-6 flex items-start gap-2 rounded-lg bg-destructive/10 border border-destructive/20 px-4 py-3 text-left max-w-md">
              <AlertCircle className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5" />
              <p className="text-sm text-destructive">{validationError}</p>
            </div>
          )}

          <Button
            size="lg"
            onClick={handleFileSelect}
            disabled={disabled}
            className="group mb-6 h-14 w-full max-w-md gap-3 rounded-xl bg-primary text-base font-medium text-primary-foreground shadow-lg shadow-primary/25 transition-all hover:bg-primary/90 hover:shadow-xl hover:shadow-primary/30 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
          >
            <Upload className="h-5 w-5 transition-transform group-hover:-translate-y-0.5" />
            Choose File
          </Button>

          <p className="mb-6 text-sm text-muted-foreground">or drag and drop your file here</p>

          <div className="flex flex-wrap items-center justify-center gap-2 text-xs text-muted-foreground">
            <span className="rounded-full bg-secondary px-3 py-1.5 font-medium">GeoJSON</span>
            <span className="rounded-full bg-secondary px-3 py-1.5 font-medium">Shapefile</span>
            <span className="rounded-full bg-secondary px-3 py-1.5 font-medium">GPKG</span>
            <span className="rounded-full bg-secondary px-3 py-1.5 font-medium">KML</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function MapPinIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  )
}
