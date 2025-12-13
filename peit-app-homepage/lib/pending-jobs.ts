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
