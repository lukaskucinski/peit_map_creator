/**
 * File validation utilities for PEIT web upload
 */

// Allowed file extensions for geospatial files
export const ALLOWED_EXTENSIONS = [
  '.geojson',
  '.json',
  '.gpkg',
  '.kml',
  '.kmz',
  '.zip', // For shapefiles
] as const

// Maximum file size in bytes (5MB)
export const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
export const MAX_FILE_SIZE_MB = 5

export interface ValidationResult {
  valid: boolean
  error?: string
}

/**
 * Get the file extension from a filename (lowercase)
 */
export function getFileExtension(filename: string): string {
  const lastDot = filename.lastIndexOf('.')
  if (lastDot === -1) return ''
  return filename.slice(lastDot).toLowerCase()
}

/**
 * Check if a file extension is allowed
 */
export function isAllowedExtension(filename: string): boolean {
  const ext = getFileExtension(filename)
  return ALLOWED_EXTENSIONS.includes(ext as typeof ALLOWED_EXTENSIONS[number])
}

/**
 * Validate a file for upload
 * Returns { valid: true } if valid, or { valid: false, error: string } if invalid
 */
export function validateFile(file: File): ValidationResult {
  // Check file extension
  if (!isAllowedExtension(file.name)) {
    const ext = getFileExtension(file.name) || '(none)'
    return {
      valid: false,
      error: `Unsupported file type "${ext}". Please upload a GeoJSON, GeoPackage, KML, or Shapefile (ZIP).`,
    }
  }

  // Check file size
  if (file.size > MAX_FILE_SIZE_BYTES) {
    const sizeMB = (file.size / (1024 * 1024)).toFixed(1)
    return {
      valid: false,
      error: `File too large (${sizeMB}MB). Maximum size is ${MAX_FILE_SIZE_MB}MB.`,
    }
  }

  return { valid: true }
}

/**
 * Format file size for display
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`
  } else if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  } else {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }
}

/**
 * Get a human-readable description of allowed file types
 */
export function getAllowedTypesDescription(): string {
  return 'GeoJSON, GeoPackage (.gpkg), KML, KMZ, or Shapefile (.zip)'
}
