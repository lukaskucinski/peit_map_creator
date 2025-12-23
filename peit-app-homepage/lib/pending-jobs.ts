/**
 * Pending Jobs Storage
 *
 * Manages job IDs in localStorage for anonymous users who may sign up later.
 * This allows claiming jobs after authentication.
 */

const STORAGE_KEY = "peit_pending_jobs"
const MAX_JOBS = 10 // Prevent unbounded growth

interface PendingJob {
  jobId: string
  timestamp: number // Unix timestamp
}

/**
 * Check if localStorage is available
 */
function isStorageAvailable(): boolean {
  try {
    const testKey = "__storage_test__"
    window.localStorage.setItem(testKey, testKey)
    window.localStorage.removeItem(testKey)
    return true
  } catch {
    return false
  }
}

/**
 * Get all pending jobs from localStorage
 */
function getStoredJobs(): PendingJob[] {
  if (!isStorageAvailable()) {
    return []
  }

  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (!stored) {
      return []
    }
    const parsed = JSON.parse(stored)
    if (!Array.isArray(parsed)) {
      return []
    }
    return parsed.filter(
      (item): item is PendingJob =>
        typeof item === "object" &&
        typeof item.jobId === "string" &&
        typeof item.timestamp === "number"
    )
  } catch {
    return []
  }
}

/**
 * Save pending jobs to localStorage
 */
function saveStoredJobs(jobs: PendingJob[]): void {
  if (!isStorageAvailable()) {
    return
  }

  try {
    // Keep only the most recent MAX_JOBS
    const trimmed = jobs.slice(-MAX_JOBS)
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed))
  } catch {
    // Storage full or other error - silently fail
  }
}

/**
 * Add a job ID to the pending list
 *
 * @param jobId - The job ID to add
 */
export function addPendingJob(jobId: string): void {
  if (!jobId) return

  const jobs = getStoredJobs()

  // Check if job already exists
  if (jobs.some((job) => job.jobId === jobId)) {
    return
  }

  jobs.push({
    jobId,
    timestamp: Date.now(),
  })

  saveStoredJobs(jobs)
}

/**
 * Get all pending job IDs
 *
 * @returns Array of job IDs
 */
export function getPendingJobs(): string[] {
  return getStoredJobs().map((job) => job.jobId)
}

/**
 * Clear all pending jobs
 */
export function clearPendingJobs(): void {
  if (!isStorageAvailable()) {
    return
  }

  try {
    window.localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Silently fail
  }
}

/**
 * Remove a specific job from the pending list
 *
 * @param jobId - The job ID to remove
 */
export function removePendingJob(jobId: string): void {
  if (!jobId) return

  const jobs = getStoredJobs().filter((job) => job.jobId !== jobId)
  saveStoredJobs(jobs)
}

// ============================================================================
// Complete State Storage (sessionStorage)
// Used to preserve the "complete" screen across OAuth redirects
// ============================================================================

const COMPLETE_STATE_KEY = "peit_complete_state"

/**
 * Serializable complete state for storage
 */
export interface StoredCompleteState {
  filename: string
  jobId?: string
  downloadUrl?: string
  mapUrl?: string
  pdfUrl?: string
  xlsxUrl?: string
  timestamp: number
}

/**
 * Check if sessionStorage is available
 */
function isSessionStorageAvailable(): boolean {
  try {
    const testKey = "__session_test__"
    window.sessionStorage.setItem(testKey, testKey)
    window.sessionStorage.removeItem(testKey)
    return true
  } catch {
    return false
  }
}

/**
 * Save the complete state to sessionStorage
 * This preserves the completion screen across OAuth redirects
 */
export function saveCompleteState(state: Omit<StoredCompleteState, "timestamp">): void {
  if (!isSessionStorageAvailable()) return

  try {
    const stored: StoredCompleteState = {
      ...state,
      timestamp: Date.now(),
    }
    window.sessionStorage.setItem(COMPLETE_STATE_KEY, JSON.stringify(stored))
  } catch {
    // Silently fail
  }
}

/**
 * Get the stored complete state from sessionStorage
 * Returns null if not found or expired (older than 1 hour)
 */
export function getCompleteState(): StoredCompleteState | null {
  if (!isSessionStorageAvailable()) return null

  try {
    const stored = window.sessionStorage.getItem(COMPLETE_STATE_KEY)
    if (!stored) return null

    const parsed = JSON.parse(stored) as StoredCompleteState

    // Validate required fields
    if (!parsed.filename || typeof parsed.timestamp !== "number") {
      return null
    }

    // Expire after 1 hour (to prevent stale state)
    const oneHour = 60 * 60 * 1000
    if (Date.now() - parsed.timestamp > oneHour) {
      clearCompleteState()
      return null
    }

    return parsed
  } catch {
    return null
  }
}

/**
 * Clear the stored complete state
 */
export function clearCompleteState(): void {
  if (!isSessionStorageAvailable()) return

  try {
    window.sessionStorage.removeItem(COMPLETE_STATE_KEY)
  } catch {
    // Silently fail
  }
}

// ============================================================================
// Error State Storage (sessionStorage)
// Used to preserve file/config when auth redirects occur from error state
// ============================================================================

const ERROR_STATE_KEY = "peit_error_state"

/**
 * Serializable error state for storage
 * Note: File objects cannot be serialized directly, so we store:
 * - GeoJSON for drawn geometries (can regenerate File)
 * - Base64 file data for uploaded files (restores full file)
 */
export interface StoredErrorState {
  filename: string
  config: {
    projectName: string
    projectId: string
    bufferDistanceFeet: number
    clipBufferMiles: number
  }
  // For drawn geometries, we can regenerate the File from GeoJSON
  geojsonData?: object | null
  geometrySource: "upload" | "draw"
  // LocationData structure from geojson-utils.ts
  locationData?: {
    city: string
    county: string
    state: string
    stateAbbr: string
  } | null
  // For uploaded files, store the actual file contents as base64
  fileData?: {
    base64: string
    type: string
    lastModified: number
  } | null
  timestamp: number
}

/**
 * Convert a File to a base64 string
 */
async function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result as string
      // Remove data URL prefix (e.g., "data:application/octet-stream;base64,")
      const base64 = result.split(",")[1]
      resolve(base64)
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

/**
 * Convert a base64 string back to a File object
 */
export function base64ToFile(
  base64: string,
  filename: string,
  type: string,
  lastModified: number
): File {
  const binaryString = atob(base64)
  const bytes = new Uint8Array(binaryString.length)
  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i)
  }
  return new File([bytes], filename, { type, lastModified })
}

/**
 * Save the error state to sessionStorage
 * This preserves configuration across OAuth redirects from error state
 *
 * @param state - The error state to save (without timestamp and fileData)
 * @param file - Optional File object to store as base64 (for uploaded files)
 */
export async function saveErrorState(
  state: Omit<StoredErrorState, "timestamp" | "fileData">,
  file?: File
): Promise<void> {
  if (!isSessionStorageAvailable()) return

  let fileData: StoredErrorState["fileData"] = null

  // Only store file data for uploaded files (drawn geometries use geojsonData)
  if (file && state.geometrySource === "upload") {
    try {
      const base64 = await fileToBase64(file)
      fileData = {
        base64,
        type: file.type || "application/octet-stream",
        lastModified: file.lastModified,
      }
    } catch (e) {
      // If file conversion fails, continue without file data
      console.warn("Failed to convert file to base64:", e)
    }
  }

  const stored: StoredErrorState = {
    ...state,
    fileData,
    timestamp: Date.now(),
  }

  try {
    window.sessionStorage.setItem(ERROR_STATE_KEY, JSON.stringify(stored))
  } catch {
    // Quota exceeded - try without file data as fallback
    if (fileData) {
      console.warn("Storage quota exceeded, storing without file data")
      const withoutFile: StoredErrorState = { ...stored, fileData: null }
      try {
        window.sessionStorage.setItem(ERROR_STATE_KEY, JSON.stringify(withoutFile))
      } catch {
        // Silently fail if even without file data it doesn't fit
      }
    }
  }
}

/**
 * Get the stored error state from sessionStorage
 * Returns null if not found or expired (older than 1 hour)
 */
export function getErrorState(): StoredErrorState | null {
  if (!isSessionStorageAvailable()) return null

  try {
    const stored = window.sessionStorage.getItem(ERROR_STATE_KEY)
    if (!stored) return null

    const parsed = JSON.parse(stored) as StoredErrorState

    // Validate required fields
    if (
      !parsed.filename ||
      !parsed.config ||
      typeof parsed.timestamp !== "number"
    ) {
      return null
    }

    // Expire after 1 hour (to prevent stale state)
    const oneHour = 60 * 60 * 1000
    if (Date.now() - parsed.timestamp > oneHour) {
      clearErrorState()
      return null
    }

    return parsed
  } catch {
    return null
  }
}

/**
 * Clear the stored error state
 */
export function clearErrorState(): void {
  if (!isSessionStorageAvailable()) return

  try {
    window.sessionStorage.removeItem(ERROR_STATE_KEY)
  } catch {
    // Silently fail
  }
}
