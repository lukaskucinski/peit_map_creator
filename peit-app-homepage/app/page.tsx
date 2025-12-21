"use client"

import { useState, useCallback, useEffect, useRef } from "react"
import type { FeatureCollection } from "geojson"
import { Header } from "@/components/header"
import { UploadCard } from "@/components/upload-card"
import { HowItWorks } from "@/components/how-it-works"
import { ConfigPanel, type ProcessingConfig } from "@/components/config-panel"
import { ProcessingStatus, type ProgressUpdate } from "@/components/processing-status"
import { MapDrawer } from "@/components/map-drawer-dynamic"
import { AuthModal } from "@/components/auth/auth-modal"
import { runMockProcessing } from "@/lib/mock-processing"
import { processFile, downloadResults, isUsingMockMode, claimJobs } from "@/lib/api"
import { parseGeospatialFile } from "@/lib/file-parsers"
import { createClient } from "@/lib/supabase/client"
import {
  addPendingJob,
  getPendingJobs,
  clearPendingJobs,
  saveCompleteState,
  getCompleteState,
  clearCompleteState,
  type StoredCompleteState,
} from "@/lib/pending-jobs"
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

export default function HomePage() {
  const [appState, setAppState] = useState<AppState>({ step: 'upload' })
  const [progressUpdates, setProgressUpdates] = useState<ProgressUpdate[]>([])
  const [geojsonData, setGeojsonData] = useState<FeatureCollection | null>(null)
  const [geometrySource, setGeometrySource] = useState<GeometrySource>('upload')
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

  // Track the previous user state for detecting sign-in events
  const prevUserRef = useRef<User | null>(null)

  // Restore complete state from sessionStorage on mount (survives OAuth redirect)
  useEffect(() => {
    const storedState = getCompleteState()
    if (storedState) {
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
  }, [])

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

      // If user is already logged in on page load AND we have pending jobs,
      // this might be returning from an OAuth redirect - claim the jobs
      if (currentUser && !isRestoringState) {
        const storedState = getCompleteState()
        const storedJobs = getPendingJobs()
        if (storedState?.jobId || storedJobs.length > 0) {
          await claimPendingJobs(currentUser.id)
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

        // Claim any pending jobs
        await claimPendingJobs(newUser.id)
      }

      // Detect sign-out event - reset to upload state
      if (event === 'SIGNED_OUT') {
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
  }, [supabase, claimPendingJobs, isRestoringState])

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

    // Parse file for area calculation and geometry type detection
    // Supports: GeoJSON, Shapefile, KML, KMZ, GeoPackage (lazy-loaded WASM)
    parseGeospatialFile(file)
      .then((parsed) => {
        setGeojsonData(parsed)
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
  }, [])

  // Handle draw mode (fresh draw, not edit)
  const handleDrawClick = useCallback(() => {
    setAppState({ step: 'draw' })
    setProgressUpdates([])
    setSavedConfig(null) // Clear saved config for new drawing
  }, [])

  // Handle edit geometry (return to draw mode with existing geometry)
  const handleEditGeometry = useCallback(() => {
    if (geojsonData) {
      setAppState({ step: 'draw', initialGeometry: geojsonData })
    }
  }, [geojsonData])

  // Handle draw complete (geometry drawn and confirmed)
  // Note: We preserve savedConfig here to retain user's configuration when editing
  const handleDrawComplete = useCallback((file: File) => {
    setAppState({ step: 'configure', file })
    setProgressUpdates([])
    setGeometrySource('draw')
    // savedConfig is preserved - don't clear it when returning from edit

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
    setAppState({ step: 'processing', file, config })
    setProgressUpdates([])

    // Use real API if configured, otherwise use mock processing
    if (isUsingMockMode()) {
      // Mock processing for development/demo
      const result = await runMockProcessing(file, config, (update) => {
        setProgressUpdates(prev => [...prev, update])
      })

      if (result.success) {
        setAppState({ step: 'complete', file, config })
      } else {
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
        setAppState({
          step: 'error',
          file,
          config,
          message: result.error || 'An unexpected error occurred',
        })
      }
    }
  }, [appState, user])

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

  // Handle process another
  const handleProcessAnother = useCallback(() => {
    // Clear the stored complete state
    clearCompleteState()
    setAppState({ step: 'upload' })
    setProgressUpdates([])
    setWasRestoredFromStorage(false)
    setClaimPromptReady(false)
    setClaimPromptOpen(false)
    setSavedConfig(null) // Clear saved config for new process
  }, [])

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
    <div className="min-h-screen bg-background">
      <Header />
      <main className="container mx-auto px-4 py-12 md:py-20">
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
          />
        )}

        {/* How It Works section - hidden during processing/complete */}
        {showHowItWorks && <HowItWorks />}
      </main>

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
