"use client"

import { useState, useCallback } from "react"
import { Header } from "@/components/header"
import { UploadCard } from "@/components/upload-card"
import { HowItWorks } from "@/components/how-it-works"
import { ConfigPanel, type ProcessingConfig } from "@/components/config-panel"
import { ProcessingStatus, type ProgressUpdate } from "@/components/processing-status"
import { runMockProcessing } from "@/lib/mock-processing"
import { processFile, downloadResults, isUsingMockMode } from "@/lib/api"

// Application state types
type AppState =
  | { step: 'upload' }
  | { step: 'configure'; file: File }
  | { step: 'processing'; file: File; config: ProcessingConfig }
  | { step: 'complete'; file: File; config: ProcessingConfig; downloadUrl?: string }
  | { step: 'error'; file: File; config: ProcessingConfig; message: string }

export default function HomePage() {
  const [appState, setAppState] = useState<AppState>({ step: 'upload' })
  const [progressUpdates, setProgressUpdates] = useState<ProgressUpdate[]>([])

  // Handle file selection
  const handleFileSelected = useCallback((file: File) => {
    setAppState({ step: 'configure', file })
    setProgressUpdates([])
  }, [])

  // Handle file cleared
  const handleFileCleared = useCallback(() => {
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
      // Real API processing
      const result = await processFile(file, config, (update) => {
        setProgressUpdates(prev => [...prev, update])
      })

      if (result.success) {
        setAppState({ step: 'complete', file, config, downloadUrl: result.downloadUrl })
      } else {
        setAppState({
          step: 'error',
          file,
          config,
          message: result.error || 'An unexpected error occurred',
        })
      }
    }
  }, [appState])

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
            selectedFile={appState.step === 'configure' ? appState.file : null}
            disabled={false}
          />
        )}

        {/* Config Panel - appears below upload card when file is selected */}
        {showConfigPanel && (
          <ConfigPanel
            filename={appState.file.name}
            onRun={handleRun}
            disabled={false}
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
