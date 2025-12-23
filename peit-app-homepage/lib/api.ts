/**
 * PEIT Modal API Client
 *
 * Handles communication with the Modal.com serverless backend for geospatial processing.
 * Uses Server-Sent Events (SSE) for real-time progress streaming.
 */

import type { ProcessingConfig } from "@/components/config-panel"
import type { ProgressUpdate } from "@/components/processing-status"

// API URL from environment variable (set in .env.local)
const API_URL = process.env.NEXT_PUBLIC_MODAL_API_URL || ""

/**
 * Check if we're using mock mode (no API URL configured)
 */
export function isUsingMockMode(): boolean {
  return !API_URL
}

/**
 * Rate limit information from the API
 */
export interface RateLimitInfo {
  remaining_runs: number
  max_runs_per_day: number
  global_remaining_runs: number
  max_global_runs_per_day: number
  resets_at: string
}

/**
 * Result of file processing
 */
export interface ProcessingResult {
  success: boolean
  jobId?: string
  downloadUrl?: string
  mapUrl?: string
  mapBlobUrl?: string
  pdfUrl?: string
  xlsxUrl?: string
  error?: string
}

/**
 * Result of claiming jobs
 */
export interface ClaimJobsResult {
  success: boolean
  claimedCount?: number
  error?: string
}

/**
 * Result of deleting a job
 */
export interface DeleteJobResult {
  success: boolean
  error?: string
}

/**
 * Check API health status
 */
export async function checkHealth(): Promise<boolean> {
  if (!API_URL) return false

  try {
    const response = await fetch(`${API_URL}/api/health`, {
      method: "GET",
    })
    const data = await response.json()
    return data.status === "healthy"
  } catch {
    return false
  }
}

/**
 * Get rate limit status for the current user
 */
export async function getRateLimitStatus(): Promise<RateLimitInfo | null> {
  if (!API_URL) return null

  try {
    const response = await fetch(`${API_URL}/api/rate-limit`, {
      method: "GET",
    })
    if (!response.ok) return null
    return await response.json()
  } catch {
    return null
  }
}

/**
 * Parse SSE event data
 */
function parseSSEEvent(data: string): ProgressUpdate | null {
  try {
    // SSE format: "data: {...}\n\n"
    const lines = data.split("\n")
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const jsonStr = line.slice(6) // Remove "data: " prefix
        return JSON.parse(jsonStr)
      }
    }
    return null
  } catch {
    return null
  }
}

/**
 * Process a geospatial file with progress streaming
 *
 * @param file - The file to process
 * @param config - Processing configuration options
 * @param userId - Optional user ID for authenticated users (associates job with user)
 * @param onProgress - Callback for progress updates
 * @returns Processing result with download URL on success
 */
export async function processFile(
  file: File,
  config: ProcessingConfig,
  userId: string | null,
  onProgress: (update: ProgressUpdate) => void
): Promise<ProcessingResult> {
  if (!API_URL) {
    return {
      success: false,
      error: "API URL not configured. Using mock mode.",
    }
  }

  // Build form data
  const formData = new FormData()
  formData.append("file", file)
  formData.append("project_name", config.projectName)
  formData.append("project_id", config.projectId)
  formData.append("buffer_distance_feet", config.bufferDistanceFeet.toString())
  formData.append("clip_buffer_miles", config.clipBufferMiles.toString())

  // Include user_id if authenticated (for job history tracking)
  if (userId) {
    formData.append("user_id", userId)
  }

  try {
    const response = await fetch(`${API_URL}/api/process`, {
      method: "POST",
      body: formData,
    })

    // Check for rate limit error
    if (response.status === 429) {
      const errorData = await response.json()
      return {
        success: false,
        error: errorData.message || "Rate limit exceeded. Please try again tomorrow.",
      }
    }

    // Check for other errors
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      return {
        success: false,
        error: errorData.detail || `Server error: ${response.status}`,
      }
    }

    // Read SSE stream
    const reader = response.body?.getReader()
    if (!reader) {
      return {
        success: false,
        error: "Failed to read response stream",
      }
    }

    const decoder = new TextDecoder()
    let buffer = ""
    let lastUpdate: ProgressUpdate | null = null

    while (true) {
      const { done, value } = await reader.read()

      if (done) break

      // Decode chunk and add to buffer
      buffer += decoder.decode(value, { stream: true })

      // Process complete events (separated by double newline)
      const events = buffer.split("\n\n")
      buffer = events.pop() || "" // Keep incomplete event in buffer

      for (const eventData of events) {
        if (!eventData.trim()) continue

        const update = parseSSEEvent(eventData)
        if (update) {
          lastUpdate = update
          onProgress(update)

          // Check for error
          if (update.stage === "error") {
            return {
              success: false,
              error: update.error || update.message,
            }
          }

          // Check for completion
          if (update.stage === "complete") {
            // Extract URLs from the update
            const extendedUpdate = update as ProgressUpdate & {
              download_url?: string
              job_id?: string
              map_url?: string
              map_blob_url?: string
              pdf_url?: string
              xlsx_url?: string
            }

            return {
              success: true,
              jobId: extendedUpdate.job_id,
              downloadUrl: extendedUpdate.download_url ? `${API_URL}${extendedUpdate.download_url}` : undefined,
              mapUrl: extendedUpdate.map_url,
              mapBlobUrl: extendedUpdate.map_blob_url,
              pdfUrl: extendedUpdate.pdf_url,
              xlsxUrl: extendedUpdate.xlsx_url,
            }
          }
        }
      }
    }

    // If we got here without a complete event, check last update
    if (lastUpdate?.stage === "complete") {
      const extendedUpdate = lastUpdate as ProgressUpdate & {
        download_url?: string
        job_id?: string
        map_url?: string
        map_blob_url?: string
        pdf_url?: string
        xlsx_url?: string
      }

      return {
        success: true,
        jobId: extendedUpdate.job_id,
        downloadUrl: extendedUpdate.download_url ? `${API_URL}${extendedUpdate.download_url}` : undefined,
        mapUrl: extendedUpdate.map_url,
        mapBlobUrl: extendedUpdate.map_blob_url,
        pdfUrl: extendedUpdate.pdf_url,
        xlsxUrl: extendedUpdate.xlsx_url,
      }
    }

    return {
      success: false,
      error: "Processing ended without completion status",
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error occurred"
    return {
      success: false,
      error: `Network error: ${message}`,
    }
  }
}

/**
 * Download results for a completed job
 *
 * @param downloadUrl - Full URL to the download endpoint
 */
export async function downloadResults(downloadUrl: string): Promise<void> {
  try {
    const response = await fetch(downloadUrl)

    if (!response.ok) {
      throw new Error(`Download failed: ${response.status}`)
    }

    // Get filename from Content-Disposition header or URL
    const contentDisposition = response.headers.get("Content-Disposition")
    let filename = "peit_results.zip"

    if (contentDisposition) {
      const match = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
      if (match) {
        filename = match[1].replace(/['"]/g, "")
      }
    }

    // Create blob and trigger download
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    console.error("Download error:", error)
    throw error
  }
}

/**
 * Claim unclaimed jobs for a newly authenticated user
 *
 * @param userId - The authenticated user's ID
 * @param jobIds - Array of job IDs to claim
 * @returns Result with number of jobs claimed
 */
export async function claimJobs(
  userId: string,
  jobIds: string[]
): Promise<ClaimJobsResult> {
  if (!API_URL) {
    return {
      success: false,
      error: "API URL not configured",
    }
  }

  if (!jobIds || jobIds.length === 0) {
    return {
      success: true,
      claimedCount: 0,
    }
  }

  try {
    const response = await fetch(`${API_URL}/api/claim-jobs`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        user_id: userId,
        job_ids: jobIds,
      }),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      return {
        success: false,
        error: errorData.detail || `Server error: ${response.status}`,
      }
    }

    const data = await response.json()
    return {
      success: true,
      claimedCount: data.claimed_count || 0,
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error occurred"
    return {
      success: false,
      error: `Network error: ${message}`,
    }
  }
}

/**
 * Nominatim response structure for reverse geocoding
 */
export interface NominatimResponse {
  lat: string
  lon: string
  display_name: string
  address?: {
    city?: string
    town?: string
    village?: string
    municipality?: string
    county?: string
    state?: string
    country?: string
    country_code?: string
  }
  error?: string
}

/**
 * Reverse geocode coordinates via backend proxy
 *
 * This proxies requests through our Modal backend to avoid CORS issues
 * with Nominatim's public API (which doesn't include CORS headers).
 *
 * @param lat - Latitude coordinate
 * @param lon - Longitude coordinate
 * @returns Nominatim response or null on error
 */
export async function reverseGeocode(
  lat: number,
  lon: number
): Promise<NominatimResponse | null> {
  if (!API_URL) return null

  try {
    const response = await fetch(
      `${API_URL}/api/reverse-geocode?lat=${lat}&lon=${lon}`
    )
    if (!response.ok) return null

    const data = await response.json()
    if (data.error) {
      console.warn("Geocoding error:", data.error)
      return null
    }
    return data
  } catch (error) {
    console.warn("Reverse geocode failed:", error)
    return null
  }
}

/**
 * Delete a job and all associated data (map, reports, storage)
 *
 * @param jobId - The job ID to delete
 * @param userId - The authenticated user's ID (must own the job)
 * @returns Result with success status
 */
export async function deleteJob(
  jobId: string,
  userId: string
): Promise<DeleteJobResult> {
  if (!API_URL) {
    return {
      success: false,
      error: "API URL not configured",
    }
  }

  try {
    const response = await fetch(`${API_URL}/api/jobs/${jobId}`, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ user_id: userId }),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      return {
        success: false,
        error: errorData.detail || `Error: ${response.status}`,
      }
    }

    return { success: true }
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error occurred"
    return {
      success: false,
      error: `Network error: ${message}`,
    }
  }
}
