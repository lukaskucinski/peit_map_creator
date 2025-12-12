"use client"

import { useState, useCallback, useEffect } from "react"
import type { FeatureCollection } from "geojson"
import { Header } from "@/components/header"
import { UploadCard } from "@/components/upload-card"
import { HowItWorks } from "@/components/how-it-works"
import { ConfigPanel, type ProcessingConfig } from "@/components/config-panel"
import { ProcessingStatus, type ProgressUpdate } from "@/components/processing-status"
import { MapDrawer } from "@/components/map-drawer-dynamic"
import { runMockProcessing } from "@/lib/mock-processing"
import { processFile, downloadResults, isUsingMockMode } from "@/lib/api"
import { parseGeospatialFile } from "@/lib/file-parsers"
import { createClient } from "@/lib/supabase/client"
import type { User } from "@supabase/supabase-js"

// Application state types
type AppState =
  | { step: 'upload' }
  | { step: 'draw' }
  | { step: 'configure'; file: File; geojsonData?: FeatureCollection | null }
  | { step: 'processing'; file: File; config: ProcessingConfig }
  | { step: 'complete'; file: File; config: ProcessingConfig; downloadUrl?: string; mapUrl?: string; pdfUrl?: string; xlsxUrl?: string }
  | { step: 'error'; file: File; config: ProcessingConfig; message: string }

export default function HomePage() {
  const [appState, setAppState] = useState<AppState>({ step: 'upload' })
  const [progressUpdates, setProgressUpdates] = useState<ProgressUpdate[]>([])
  const [geojsonData, setGeojsonData] = useState<FeatureCollection | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const supabase = createClient()

  // Track authentication state for job history
  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null)
    })

    // Listen for auth changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null)
    })

    return () => subscription.unsubscribe()
  }, [supabase])

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
        setAppState({
          step: 'complete',
          file,
          config,
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
            onDownload={handleDownload}
            onProcessAnother={handleProcessAnother}
          />
        )}

        {/* How It Works section - hidden during processing/complete */}
        {showHowItWorks && <HowItWorks />}
      </main>
    </div>
  )
}
