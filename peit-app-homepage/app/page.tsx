"use client"

import { useState, useCallback, useEffect, useRef, Suspense } from "react"
import { useSearchParams, useRouter } from "next/navigation"
import type { FeatureCollection } from "geojson"
import { Header } from "@/components/header"
import { Footer } from "@/components/footer"
import { UploadCard } from "@/components/upload-card"
import { HowItWorks } from "@/components/how-it-works"
import { ConfigPanel, type ProcessingConfig } from "@/components/config-panel"
import { ProcessingStatus, type ProgressUpdate } from "@/components/processing-status"
import { MapDrawer } from "@/components/map-drawer-dynamic"
import { AuthModal } from "@/components/auth/auth-modal"
import { runMockProcessing } from "@/lib/mock-processing"
import { processFile, downloadResults, isUsingMockMode, claimJobs } from "@/lib/api"
import { parseGeospatialFile } from "@/lib/file-parsers"
import { reverseGeocodeGeometry, type LocationData } from "@/lib/geojson-utils"
import { createClient } from "@/lib/supabase/client"
import {
  addPendingJob,
  getPendingJobs,
  clearPendingJobs,
  saveCompleteState,
  getCompleteState,
  clearCompleteState,
  saveErrorState,
  getErrorState,
  clearErrorState,
  base64ToFile,
  type StoredCompleteState,
} from "@/lib/pending-jobs"
import { geojsonToFile } from "@/lib/geojson-utils"
import { ClaimJobPrompt } from "@/components/claim-job-prompt"
import { useToast } from "@/hooks/use-toast"
import type { User } from "@supabase/supabase-js"

// Geometry source type - tracks whether geometry was uploaded or drawn
type GeometrySource = 'upload' | 'draw'

// Application state types
type AppState =
  | { step: 'upload' }
  | { step: 'draw'; initialGeometry?: FeatureCollection }
  | { step: 'configure'; file: File; geojsonData?: FeatureCollection | null }
  | { step: 'processing'; file: File; config: ProcessingConfig }
  | { step: 'complete'; file: File; config: ProcessingConfig; jobId?: string; downloadUrl?: string; mapUrl?: string; pdfUrl?: string; xlsxUrl?: string }
  | { step: 'error'; file: File; config: ProcessingConfig; message: string }

function HomePageContent() {
  const [appState, setAppState] = useState<AppState>({ step: 'upload' })
  const [progressUpdates, setProgressUpdates] = useState<ProgressUpdate[]>([])
  const [geojsonData, setGeojsonData] = useState<FeatureCollection | null>(null)
  const [geometrySource, setGeometrySource] = useState<GeometrySource>('upload')
  // Store location data from geocoding for project ID generation
  const [locationData, setLocationData] = useState<LocationData | null>(null)
  // Store config values to persist when editing geometry
  const [savedConfig, setSavedConfig] = useState<Partial<ProcessingConfig> | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [authModalOpen, setAuthModalOpen] = useState(false)
  const [authModalTab, setAuthModalTab] = useState<"signin" | "signup">("signin")
  const [isRestoringState, setIsRestoringState] = useState(true) // Track if we're restoring state
  const [wasRestoredFromStorage, setWasRestoredFromStorage] = useState(false) // Track if complete state was restored
  const [claimPromptOpen, setClaimPromptOpen] = useState(false) // Track claim prompt dialog visibility
  const [claimPromptReady, setClaimPromptReady] = useState(false) // Track if claim prompt is ready to show (waiting for trigger)
  const supabase = createClient()
  const { toast } = useToast()
  const searchParams = useSearchParams()
  const router = useRouter()

  // Track the previous user state for detecting sign-in events
  const prevUserRef = useRef<User | null>(null)

  // Track the active job ID to prevent abandoned jobs from interrupting new workflows
  // Uses ref to avoid React closure staleness issues
  const activeJobIdRef = useRef<string | null>(null)

  // Handle reset signal from header logo navigation (?reset=1)
  // This ensures clicking the logo always returns to a fresh upload state
  useEffect(() => {
    if (searchParams.get('reset') === '1') {
      // Clear sessionStorage states (same as handleProcessAnother)
      clearCompleteState()
      clearErrorState()
      // NOTE: Do NOT clear pending jobs (localStorage) - those persist for future sign-in

      // Clear active job tracking
      activeJobIdRef.current = null

      // Reset all React state
      setAppState({ step: 'upload' })
      setProgressUpdates([])
      setWasRestoredFromStorage(false)
      setClaimPromptReady(false)
      setClaimPromptOpen(false)
      setSavedConfig(null)
      setGeojsonData(null)
      setGeometrySource('upload')
      setLocationData(null)
      setIsRestoringState(false)

      // Clean up URL (remove query param) - prevents re-triggering on refresh
      router.replace('/', { scroll: false })
    }
  }, [searchParams, router])

  // Restore complete state from sessionStorage on mount (survives OAuth redirect)
  useEffect(() => {
    // Skip restoration if reset param is present (user clicked logo to go home)
    if (searchParams.get('reset') === '1') {
      return
    }

    const storedState = getCompleteState()
    if (storedState) {
      // Set active job to restored job ID so we recognize it as the current job
      activeJobIdRef.current = storedState.jobId ?? null

      // Create a dummy File object for display purposes
      // The actual file isn't needed since processing is complete
      const dummyFile = new File([], storedState.filename, { type: 'application/octet-stream' })

      setAppState({
        step: 'complete',
        file: dummyFile,
        config: { projectName: '', projectId: '', bufferDistanceFeet: 500, clipBufferMiles: 1 }, // Dummy config
        jobId: storedState.jobId,
        downloadUrl: storedState.downloadUrl,
        mapUrl: storedState.mapUrl,
        pdfUrl: storedState.pdfUrl,
        xlsxUrl: storedState.xlsxUrl,
      })
      setWasRestoredFromStorage(true)
    }
    setIsRestoringState(false)
  }, [searchParams])

  // Restore error state from sessionStorage (after OAuth redirect from error state)
  const restoreErrorState = useCallback(() => {
    const errorState = getErrorState()
    if (!errorState) return false

    // For drawn geometries, we can fully restore by regenerating the File
    if (errorState.geometrySource === 'draw' && errorState.geojsonData) {
      const geojson = errorState.geojsonData as FeatureCollection
      const file = geojsonToFile(geojson, errorState.filename || 'drawn_geometry.geojson')

      setAppState({ step: 'configure', file })
      setSavedConfig(errorState.config)
      setGeojsonData(geojson)
      setGeometrySource('draw')
      setLocationData(errorState.locationData ?? null)
      clearErrorState()
      return true
    }

    // For uploaded files, try to restore from stored base64 data
    if (errorState.geometrySource === 'upload') {
      let file: File
      let needsReselect = false

      // Try to restore full file from stored base64 data
      if (errorState.fileData?.base64) {
        file = base64ToFile(
          errorState.fileData.base64,
          errorState.filename,
          errorState.fileData.type,
          errorState.fileData.lastModified
        )
      } else {
        // Fallback: create placeholder file (user must re-select)
        file = new File([], errorState.filename, { type: 'application/octet-stream' })
        needsReselect = true
      }

      setAppState({ step: 'configure', file })
      setSavedConfig(errorState.config)
      setGeometrySource('upload')
      setLocationData(errorState.locationData ?? null)
      clearErrorState()

      if (needsReselect) {
        // Show a toast to inform user they need to re-select the file
        toast({
          title: "Please re-select your file",
          description: `Your settings have been restored. Re-select "${errorState.filename}" to continue.`,
        })
        setGeojsonData(null)
      } else {
        // Re-parse the restored file for area estimation
        parseGeospatialFile(file)
          .then((parsed) => {
            setGeojsonData(parsed)
          })
          .catch(() => {
            setGeojsonData(null)
          })
      }
      return true
    }

    return false
  }, [toast])

  // Claim pending jobs for a newly authenticated user
  // Note: This function doesn't depend on appState to avoid closure issues
  // It gets job IDs from localStorage and sessionStorage instead
  const claimPendingJobs = useCallback(async (userId: string) => {
    // Get job ID from sessionStorage (current complete state)
    const storedState = getCompleteState()
    const currentJobId = storedState?.jobId

    // Get stored pending jobs from localStorage
    const storedJobs = getPendingJobs()

    // Combine current job with stored jobs (deduplicate)
    const jobsToClaim = [...new Set([currentJobId, ...storedJobs].filter(Boolean))] as string[]

    if (jobsToClaim.length === 0) {
      return
    }

    const result = await claimJobs(userId, jobsToClaim)

    if (result.success && result.claimedCount && result.claimedCount > 0) {
      // Clear localStorage after successful claim (but NOT sessionStorage - keep the complete state visible)
      clearPendingJobs()

      // Show success toast
      toast({
        title: result.claimedCount === 1
          ? "Map saved to your history!"
          : `${result.claimedCount} maps saved to your history!`,
        description: "View your maps anytime from the dashboard.",
      })
    }
  }, [toast])

  // Track authentication state for job history
  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      const currentUser = session?.user ?? null
      setUser(currentUser)
      prevUserRef.current = currentUser

      // If user is already logged in on page load, this might be returning from an OAuth redirect
      if (currentUser && !isRestoringState) {
        // First check if we need to restore error state (user signed in from error screen)
        const restored = restoreErrorState()

        // If not restoring error state, check for pending jobs to claim
        if (!restored) {
          const storedState = getCompleteState()
          const storedJobs = getPendingJobs()
          if (storedState?.jobId || storedJobs.length > 0) {
            await claimPendingJobs(currentUser.id)
          }
        }
      }
    })

    // Listen for auth changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (event, session) => {
      const newUser = session?.user ?? null
      const prevUser = prevUserRef.current

      setUser(newUser)

      // Detect sign-in event (was not logged in, now logged in)
      if (!prevUser && newUser) {
        // Close auth modal and claim prompt if open
        setAuthModalOpen(false)
        setClaimPromptReady(false)
        setClaimPromptOpen(false)

        // Check if we need to restore error state (user signed in from error screen)
        const restored = restoreErrorState()

        // Claim any pending jobs (if not restoring error state)
        if (!restored) {
          await claimPendingJobs(newUser.id)
        }
      }

      // Detect sign-out event - reset to upload state
      if (event === 'SIGNED_OUT') {
        activeJobIdRef.current = null // Clear active job tracking
        setAppState({ step: 'upload' })
        setProgressUpdates([])
        setWasRestoredFromStorage(false)
        setClaimPromptReady(false)
        setClaimPromptOpen(false)
      }

      // Update ref for next comparison
      prevUserRef.current = newUser
    })

    return () => subscription.unsubscribe()
  }, [supabase, claimPendingJobs, restoreErrorState, isRestoringState])

  // Show claim prompt with delay - triggered by mouse movement (desktop) or timeout (mobile)
  useEffect(() => {
    if (!claimPromptReady || claimPromptOpen) return

    let timeoutId: NodeJS.Timeout | null = null
    let hasTriggered = false

    const showPrompt = () => {
      if (hasTriggered) return
      hasTriggered = true
      setClaimPromptOpen(true)
      setClaimPromptReady(false)
      // Clean up
      if (timeoutId) clearTimeout(timeoutId)
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('touchstart', handleTouch)
    }

    const handleMouseMove = () => {
      // Small delay after mouse move for smoother feel
      setTimeout(showPrompt, 200)
    }

    const handleTouch = () => {
      // For touch devices, show after a brief delay
      setTimeout(showPrompt, 500)
    }

    // Listen for mouse movement (desktop)
    window.addEventListener('mousemove', handleMouseMove, { once: true })
    // Listen for touch (mobile)
    window.addEventListener('touchstart', handleTouch, { once: true })

    // Fallback timeout for mobile devices that don't trigger events (3 seconds)
    timeoutId = setTimeout(showPrompt, 3000)

    return () => {
      if (timeoutId) clearTimeout(timeoutId)
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('touchstart', handleTouch)
    }
  }, [claimPromptReady, claimPromptOpen])

  // Handle file selection
  const handleFileSelected = useCallback((file: File) => {
    setAppState({ step: 'configure', file })
    setProgressUpdates([])
    setGeometrySource('upload')
    setSavedConfig(null) // Clear saved config for new file
    setLocationData(null) // Clear location data for new file

    // Parse file for area calculation and geometry type detection
    // Supports: GeoJSON, Shapefile, KML, KMZ, GeoPackage (lazy-loaded WASM)
    parseGeospatialFile(file)
      .then(async (parsed) => {
        setGeojsonData(parsed)
        // Also geocode for location-based project ID (non-blocking)
        if (parsed) {
          const location = await reverseGeocodeGeometry(parsed)
          setLocationData(location)
        }
      })
      .catch(() => {
        setGeojsonData(null)
      })
  }, [])

  // Handle file cleared
  const handleFileCleared = useCallback(() => {
    setAppState({ step: 'upload' })
    setProgressUpdates([])
    setGeojsonData(null)
    setGeometrySource('upload')
    setSavedConfig(null) // Clear saved config
    setLocationData(null) // Clear location data
  }, [])

  // Handle draw mode (fresh draw, not edit)
  const handleDrawClick = useCallback(() => {
    setAppState({ step: 'draw' })
    setProgressUpdates([])
    setSavedConfig(null) // Clear saved config for new drawing
    setLocationData(null) // Clear location data for new drawing
  }, [])

  // Handle edit geometry (return to draw mode with existing geometry)
  const handleEditGeometry = useCallback(() => {
    if (geojsonData) {
      setAppState({ step: 'draw', initialGeometry: geojsonData })
    }
  }, [geojsonData])

  // Handle draw complete (geometry drawn and confirmed)
  // Note: We preserve savedConfig here to retain user's configuration when editing
  const handleDrawComplete = useCallback((file: File, location?: LocationData | null) => {
    setAppState({ step: 'configure', file })
    setProgressUpdates([])
    setGeometrySource('draw')
    // savedConfig is preserved - don't clear it when returning from edit
    // Store location data from geocoding (already done in map drawer)
    setLocationData(location ?? null)

    // Parse the drawn geometry file for area calculation
    // Drawn geometry is always GeoJSON, but use unified parser for consistency
    parseGeospatialFile(file)
      .then((parsed) => {
        setGeojsonData(parsed)
      })
      .catch(() => {
        setGeojsonData(null)
      })
  }, [])

  // Handle draw cancel
  const handleDrawCancel = useCallback(() => {
    setAppState({ step: 'upload' })
    setProgressUpdates([])
  }, [])

  // Handle run processing
  const handleRun = useCallback(async (config: ProcessingConfig) => {
    if (appState.step !== 'configure') return

    const file = appState.file

    // Generate temporary job ID to track this specific run
    const tempJobId = crypto.randomUUID()
    activeJobIdRef.current = tempJobId
    console.log(`[JOB TRACKING] Starting new job: ${tempJobId}`)

    setAppState({ step: 'processing', file, config })
    setProgressUpdates([])

    // Use real API if configured, otherwise use mock processing
    if (isUsingMockMode()) {
      // Mock processing for development/demo
      const result = await runMockProcessing(file, config, (update) => {
        setProgressUpdates(prev => [...prev, update])
      })

      // Check if this job is still active before updating state
      console.log(`[JOB TRACKING] Job ${tempJobId} completed. Active job: ${activeJobIdRef.current}`)
      if (activeJobIdRef.current !== tempJobId) {
        console.log(`[JOB TRACKING] Ignoring completion for abandoned job: ${tempJobId}`)
        return
      }

      console.log(`[JOB TRACKING] Processing completion for active job: ${tempJobId}`)

      if (result.success) {
        setAppState({ step: 'complete', file, config })
      } else {
        // Save error state for mock mode too (consistent behavior)
        await saveErrorState({
          filename: file.name,
          config,
          geojsonData: geojsonData,
          geometrySource: geometrySource,
          locationData: locationData,
        }, file)

        setAppState({
          step: 'error',
          file,
          config,
          message: result.error || 'An unexpected error occurred',
        })
      }
    } else {
      // Real API processing - pass user ID for job history tracking
      const result = await processFile(file, config, user?.id ?? null, (update) => {
        setProgressUpdates(prev => [...prev, update])
      })

      // Check if this job is still active before updating state
      console.log(`[JOB TRACKING] Job ${tempJobId} completed. Active job: ${activeJobIdRef.current}`)
      if (activeJobIdRef.current !== tempJobId) {
        console.log(`[JOB TRACKING] Ignoring completion for abandoned job: ${tempJobId}`)
        return
      }

      console.log(`[JOB TRACKING] Processing completion for active job: ${tempJobId}`)

      if (result.success) {
        // Store job ID to localStorage if user is not authenticated
        // This allows claiming the job if they sign up later
        if (!user && result.jobId) {
          addPendingJob(result.jobId)
          // Queue claim prompt to show on next user interaction (mouse move or touch)
          setClaimPromptReady(true)
        }

        // Save complete state to sessionStorage (survives OAuth redirect)
        saveCompleteState({
          filename: file.name,
          jobId: result.jobId,
          downloadUrl: result.downloadUrl,
          mapUrl: result.mapUrl,
          pdfUrl: result.pdfUrl,
          xlsxUrl: result.xlsxUrl,
        })

        // Reset the restored flag since this is a fresh completion
        setWasRestoredFromStorage(false)

        setAppState({
          step: 'complete',
          file,
          config,
          jobId: result.jobId,
          downloadUrl: result.downloadUrl,
          mapUrl: result.mapUrl,
          pdfUrl: result.pdfUrl,
          xlsxUrl: result.xlsxUrl,
        })
      } else {
        // Save error state to sessionStorage for recovery after OAuth redirect
        await saveErrorState({
          filename: file.name,
          config,
          geojsonData: geojsonData,
          geometrySource: geometrySource,
          locationData: locationData,
        }, file)

        setAppState({
          step: 'error',
          file,
          config,
          message: result.error || 'An unexpected error occurred',
        })
      }
    }
  }, [appState, user, geojsonData, geometrySource, locationData])

  // Handle download
  const handleDownload = useCallback(async () => {
    if (appState.step === 'complete' && appState.downloadUrl) {
      try {
        await downloadResults(appState.downloadUrl)
      } catch (error) {
        console.error('Download failed:', error)
        alert('Download failed. Please try again.')
      }
    } else if (isUsingMockMode()) {
      // Mock mode - show message
      alert('Download functionality will be available when connected to the backend.\n\nTo enable real processing, set NEXT_PUBLIC_MODAL_API_URL in your .env.local file.')
    }
  }, [appState])

  // Handle process another (from complete state - starts fresh)
  const handleProcessAnother = useCallback(() => {
    // Clear active job tracking
    activeJobIdRef.current = null

    // Clear the stored complete state
    clearCompleteState()
    clearErrorState()
    setAppState({ step: 'upload' })
    setProgressUpdates([])
    setWasRestoredFromStorage(false)
    setClaimPromptReady(false)
    setClaimPromptOpen(false)
    setSavedConfig(null) // Clear saved config for new process
  }, [])

  // Handle try again (from error state - preserves file and config)
  const handleTryAgain = useCallback(() => {
    if (appState.step === 'error') {
      // Restore to configure with the preserved file and config
      setAppState({ step: 'configure', file: appState.file })
      setSavedConfig(appState.config)
      // geojsonData, geometrySource, locationData are already in state - don't clear them
    } else {
      // Fallback to fresh upload
      setAppState({ step: 'upload' })
      setSavedConfig(null)
    }
    clearErrorState()
    setProgressUpdates([])
    setWasRestoredFromStorage(false)
    setClaimPromptReady(false)
    setClaimPromptOpen(false)
  }, [appState])

  // Handle config changes from ConfigPanel
  const handleConfigChange = useCallback((config: Partial<ProcessingConfig>) => {
    setSavedConfig(config)
  }, [])

  // Determine what to show based on state
  const showHowItWorks = appState.step === 'upload' || appState.step === 'configure' || appState.step === 'error'
  const showUploadCard = appState.step === 'upload' || appState.step === 'configure'
  const showMapDrawer = appState.step === 'draw'
  const showConfigPanel = appState.step === 'configure'
  const showProcessingStatus = appState.step === 'processing' || appState.step === 'complete' || appState.step === 'error'

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Header />
      <main className="container mx-auto px-4 py-12 md:py-20 flex-1">
        {/* Upload Card */}
        {showUploadCard && (
          <UploadCard
            onFileSelected={handleFileSelected}
            onFileCleared={handleFileCleared}
            onDrawClick={handleDrawClick}
            onEditGeometry={geometrySource === 'draw' ? handleEditGeometry : undefined}
            selectedFile={appState.step === 'configure' ? appState.file : null}
            geojsonData={geojsonData}
            geometrySource={geometrySource}
            disabled={false}
          />
        )}

        {/* Map Drawer - for drawing geometry */}
        {showMapDrawer && (
          <MapDrawer
            onComplete={handleDrawComplete}
            onCancel={handleDrawCancel}
            initialGeometry={appState.step === 'draw' ? appState.initialGeometry : undefined}
          />
        )}

        {/* Config Panel - appears below upload card when file is selected */}
        {showConfigPanel && (
          <ConfigPanel
            filename={appState.file.name}
            onRun={handleRun}
            disabled={false}
            geojsonData={geojsonData}
            locationData={locationData}
            initialConfig={savedConfig ?? undefined}
            onConfigChange={handleConfigChange}
          />
        )}

        {/* Processing Status */}
        {showProcessingStatus && (
          <ProcessingStatus
            filename={
              appState.step === 'processing' || appState.step === 'complete' || appState.step === 'error'
                ? appState.file.name
                : ''
            }
            progressUpdates={progressUpdates}
            isComplete={appState.step === 'complete'}
            isError={appState.step === 'error'}
            errorMessage={appState.step === 'error' ? appState.message : undefined}
            downloadUrl={appState.step === 'complete' ? appState.downloadUrl : undefined}
            mapUrl={appState.step === 'complete' ? appState.mapUrl : undefined}
            pdfUrl={appState.step === 'complete' ? appState.pdfUrl : undefined}
            xlsxUrl={appState.step === 'complete' ? appState.xlsxUrl : undefined}
            showCompletionTime={!wasRestoredFromStorage}
            onDownload={handleDownload}
            onProcessAnother={handleProcessAnother}
            onTryAgain={handleTryAgain}
            isAuthenticated={!!user}
            onSignUp={() => {
              setAuthModalTab("signup")
              setAuthModalOpen(true)
            }}
            onSignIn={() => {
              setAuthModalTab("signin")
              setAuthModalOpen(true)
            }}
          />
        )}

        {/* How It Works section - hidden during processing/complete */}
        {showHowItWorks && <HowItWorks />}
      </main>

      <Footer />

      {/* Auth Modal - for sign up/sign in from ProcessingStatus */}
      <AuthModal
        open={authModalOpen}
        onOpenChange={setAuthModalOpen}
        defaultTab={authModalTab}
      />

      {/* Claim Job Prompt - for anonymous users after completing a job */}
      <ClaimJobPrompt
        open={claimPromptOpen}
        onOpenChange={setClaimPromptOpen}
        onSignUp={() => {
          setClaimPromptOpen(false)
          setAuthModalTab("signup")
          setAuthModalOpen(true)
        }}
        onSignIn={() => {
          setClaimPromptOpen(false)
          setAuthModalTab("signin")
          setAuthModalOpen(true)
        }}
      />
    </div>
  )
}

// Wrap in Suspense boundary for useSearchParams (required by Next.js 14+ for static generation)
export default function HomePage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-background flex flex-col">
        <Header />
        <main className="container mx-auto px-4 py-12 md:py-20 flex-1">
          <div className="flex items-center justify-center">
            <div className="animate-pulse text-muted-foreground">Loading...</div>
          </div>
        </main>
        <Footer />
      </div>
    }>
      <HomePageContent />
    </Suspense>
  )
}
