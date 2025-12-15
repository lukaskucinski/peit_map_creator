"use client"

import type React from "react"
import { useState, useCallback } from "react"
import { Upload, FileCheck, X, AlertCircle, Pencil } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { validateFile, formatFileSize, getAllowedTypesDescription } from "@/lib/validation"

interface UploadCardProps {
  onFileSelected?: (file: File) => void
  onFileCleared?: () => void
  onDrawClick?: () => void
  selectedFile?: File | null
  disabled?: boolean
}

export function UploadCard({
  onFileSelected,
  onFileCleared,
  onDrawClick,
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
            <LandcoverIcon className="h-9 w-9 text-primary" />
          </div>

          <h1 className="mb-2 text-2xl font-semibold text-foreground md:text-3xl text-balance">
            Geospatial File Processor
          </h1>

          <p className="mb-6 max-w-md text-muted-foreground text-pretty">
            Upload a geospatial file to create an environmental map in seconds.
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

          <p className="mb-4 text-sm text-muted-foreground">or drag and drop your file here</p>

          <div className="flex flex-wrap items-center justify-center gap-2 mb-6 text-xs text-muted-foreground">
            <span className="rounded-full bg-secondary px-3 py-1.5 font-medium">GeoJSON</span>
            <span className="rounded-full bg-secondary px-3 py-1.5 font-medium">Shapefile</span>
            <span className="rounded-full bg-secondary px-3 py-1.5 font-medium">GPKG</span>
            <span className="rounded-full bg-secondary px-3 py-1.5 font-medium">KML</span>
          </div>

          {/* Divider */}
          <div className="flex items-center gap-3 mb-6 w-full max-w-md">
            <div className="flex-1 h-px bg-border" />
            <span className="text-xs text-muted-foreground">or</span>
            <div className="flex-1 h-px bg-border" />
          </div>

          {/* Draw Your Own Button */}
          <Button
            size="lg"
            variant="outline"
            onClick={onDrawClick}
            disabled={disabled || !onDrawClick}
            className="group h-14 w-full max-w-md gap-3 rounded-xl text-base font-medium transition-all hover:bg-accent hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
          >
            <Pencil className="h-5 w-5 transition-transform group-hover:rotate-[-15deg]" />
            Draw Your Own!
          </Button>
        </div>
      </div>
    </div>
  )
}

function LandcoverIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 100 100"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M49.932 22.56a4.725 2.593 0 0 0-3.274.76L1.383 48.166a4.725 2.593 0 0 0 0 3.668L46.658 76.68a4.725 2.593 0 0 0 6.684 0l45.275-24.846a4.725 2.593 0 0 0 0-3.668L53.342 23.32a4.725 2.593 0 0 0-3.41-.76zM50 28.82l8.713 4.782a25.922 25.922 0 0 0-3.606 1.705c-2.827 1.61-5.458 3.774-6.994 6.636c-6.097-.96-12.326-1.538-18.468-1.953L50 28.82zm15.297 8.395L88.596 50l-7.639 4.191c-7.813-5.86-17.33-9.24-27.441-11.29c1.018-1.175 2.451-2.33 4.064-3.249c2.43-1.383 5.237-2.227 6.963-2.304a2.5 2.5 0 0 0 .754-.133zm-43.793 7.244a2.5 2.5 0 0 0 .506.078c19.426 1.07 40.051 2.978 54.074 12.328l-3.334 1.83c-7.592-4.899-16.302-8.454-27.129-7.892c-6.456.335-13.67 2.145-21.84 5.988L11.406 50l10.098-5.541zm27.258 11.08c7.27.138 13.278 2.534 18.96 5.916L50 71.18L29.277 59.807c7.526-3.144 13.88-4.374 19.485-4.268z" />
    </svg>
  )
}
