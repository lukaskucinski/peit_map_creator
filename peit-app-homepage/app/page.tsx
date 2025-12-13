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
import { addPendingJob, getPendingJobs, clearPendingJobs } from "@/lib/pending-jobs"
import { useToast } from "@/hooks/use-toast"
import type { User } from "@supabase/supabase-js"

// Application state types
type AppState =
  | { step: 'upload' }
  | { step: 'draw' }
  | { step: 'configure'; file: File; geojsonData?: FeatureCollection | null }
  | { step: 'processing'; file: File; config: ProcessingConfig }
  | { step: 'complete'; file: File; config: ProcessingConfig; jobId?: string; downloadUrl?: string; mapUrl?: string; pdfUrl?: string; xlsxUrl?: string }
  | { step: 'error'; file: File; config: ProcessingConfig; message: string }

export default function HomePage() {
  const [appState, setAppState] = useState<AppState>({ step: 'upload' })
  const [progressUpdates, setProgressUpdates] = useState<ProgressUpdate[]>([])
  const [geojsonData, setGeojsonData] = useState<FeatureCollection | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [authModalOpen, setAuthModalOpen] = useState(false)
  const [authModalTab, setAuthModalTab] = useState<"signin" | "signup">("signin")
  const supabase = createClient()
  const { toast } = useToast()

  // Track the previous user state for detecting sign-in events
  const prevUserRef = useRef<User | null>(null)

  // Claim pending jobs for a newly authenticated user
  const claimPendingJobs = useCallback(async (userId: string) => {
    // Get current job ID from app state (if in complete state)
    const currentJobId = appState.step === 'complete' ? appState.jobId : undefined

    // Get stored pending jobs from localStorage
    const storedJobs = getPendingJobs()

    // Combine current job with stored jobs (deduplicate)
    const jobsTolaim = [...new Set([currentJobId, ...storedJobs].filter(Boolean))] as string[]

    if (jobsTolaim.length === 0) {
      return
    }

    const result = await claimJobs(userId, jobsTolaim)

    if (result.success && result.claimedCount && result.claimedCount > 0) {
      // Clear localStorage after successful claim
      clearPendingJobs()

      // Show success toast
      toast({
        title: result.claimedCount === 1
          ? "Map saved to your history!"
          : `${result.claimedCount} maps saved to your history!`,
        description: "View your maps anytime from the dashboard.",
      })
    }
  }, [appState, toast])

  // Track authentication state for job history
  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null)
      prevUserRef.current = session?.user ?? null
    })

    // Listen for auth changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (_event, session) => {
      const newUser = session?.user ?? null
      const prevUser = prevUserRef.current

      setUser(newUser)

      // Detect sign-in event (was not logged in, now logged in)
      if (!prevUser && newUser) {
        // Close auth modal if open
        setAuthModalOpen(false)

        // Claim any pending jobs
        await claimPendingJobs(newUser.id)
      }

      // Update ref for next comparison
      prevUserRef.current = newUser
    })

    return () => subscription.unsubscribe()
  }, [supabase, claimPendingJobs])

  // Handle file selection
  const handleFileSelected = useCallback((file: File) => {
    setAppState({ step: 'configure', file })
    setProgressUpdates([])

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
  }, [])

  // Handle draw mode
  const handleDrawClick = useCallback(() => {
    setAppState({ step: 'draw' })
    setProgressUpdates([])
  }, [])

  // Handle draw complete (geometry drawn and confirmed)
  const handleDrawComplete = useCallback((file: File) => {
    setAppState({ step: 'configure', file })
    setProgressUpdates([])

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
        }

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
    setAppState({ step: 'upload' })
    setProgressUpdates([])
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
            selectedFile={appState.step === 'configure' ? appState.file : null}
            disabled={false}
          />
        )}

        {/* Map Drawer - for drawing geometry */}
        {showMapDrawer && (
          <MapDrawer
            onComplete={handleDrawComplete}
            onCancel={handleDrawCancel}
          />
        )}

        {/* Config Panel - appears below upload card when file is selected */}
        {showConfigPanel && (
          <ConfigPanel
            filename={appState.file.name}
            onRun={handleRun}
            disabled={false}
            geojsonData={geojsonData}
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
            jobId={appState.step === 'complete' ? appState.jobId : undefined}
            isAuthenticated={!!user}
            onDownload={handleDownload}
            onProcessAnother={handleProcessAnother}
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

      {/* Auth Modal - for sign up/sign in from ProcessingStatus */}
      <AuthModal
        open={authModalOpen}
        onOpenChange={setAuthModalOpen}
        defaultTab={authModalTab}
      />
    </div>
  )
}
