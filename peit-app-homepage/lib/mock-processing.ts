/**
 * Mock processing service for local testing
 * Simulates the backend processing workflow
 */

import type { ProcessingConfig } from "@/components/config-panel"
import type { ProgressUpdate } from "@/components/processing-status"

// Sample layer names from the actual PEIT configuration
const SAMPLE_LAYERS = [
  "NPS Land",
  "USBR Land",
  "USACE Lands for Permitting",
  "BIA AIAN National LAR",
  "BIA AIAN LAR Supplemental",
  "BIA TSA",
  "USFS Administrative Forest Boundaries",
  "BLM Administrative Unit Boundaries",
  "USFWS Interest Simplified",
  "USFWS Approved Acquisition Boundaries",
  "TVA Land",
  "DOE Land",
  "Military Installations",
  "NPDES Sites",
  "RCRA Sites",
  "Historic Places",
  "Navigable Waterways",
  "Critical Habitat",
  "Wetlands",
  "Floodplains",
]

/**
 * Sleep utility
 */
function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/**
 * Mock file processing that yields progress updates
 */
export async function* mockProcessFile(
  file: File,
  config: ProcessingConfig
): AsyncGenerator<ProgressUpdate> {
  // Stage 1: Upload (5%)
  yield {
    stage: 'upload',
    message: 'File received, preparing for processing...',
    progress: 5,
  }
  await sleep(500)

  // Stage 2: Geometry processing (10%)
  yield {
    stage: 'geometry',
    message: 'Processing input geometry...',
    progress: 10,
  }
  await sleep(800)

  // Stage 3: Query layers (10-90%)
  const totalLayers = SAMPLE_LAYERS.length
  const progressPerLayer = 80 / totalLayers // 80% of progress for layer queries

  for (let i = 0; i < totalLayers; i++) {
    const layerName = SAMPLE_LAYERS[i]
    const currentProgress = Math.round(10 + (i + 1) * progressPerLayer)

    yield {
      stage: 'query',
      message: `Querying: ${layerName}...`,
      progress: Math.min(currentProgress, 90),
      currentLayer: i + 1,
      totalLayers,
    }

    // Simulate variable query times (200-500ms per layer)
    await sleep(200 + Math.random() * 300)
  }

  // Stage 4: Generate map (92%)
  yield {
    stage: 'map',
    message: 'Generating interactive map...',
    progress: 92,
  }
  await sleep(1000)

  // Stage 5: Generate reports (96%)
  yield {
    stage: 'report',
    message: 'Generating PDF and XLSX reports...',
    progress: 96,
  }
  await sleep(800)

  // Stage 6: Complete (100%)
  yield {
    stage: 'complete',
    message: 'Processing complete!',
    progress: 100,
  }
}

/**
 * Run mock processing and collect all updates via callback
 */
export async function runMockProcessing(
  file: File,
  config: ProcessingConfig,
  onProgress: (update: ProgressUpdate) => void
): Promise<{ success: boolean; error?: string }> {
  try {
    for await (const update of mockProcessFile(file, config)) {
      onProgress(update)
    }
    return { success: true }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred'
    onProgress({
      stage: 'error',
      message: errorMessage,
      progress: 0,
      error: errorMessage,
    })
    return { success: false, error: errorMessage }
  }
}

/**
 * Simulate a failed processing (for testing error states)
 */
export async function* mockProcessFileWithError(
  file: File,
  config: ProcessingConfig
): AsyncGenerator<ProgressUpdate> {
  yield {
    stage: 'upload',
    message: 'File received, preparing for processing...',
    progress: 5,
  }
  await sleep(500)

  yield {
    stage: 'geometry',
    message: 'Processing input geometry...',
    progress: 10,
  }
  await sleep(800)

  // Simulate error at 35%
  yield {
    stage: 'query',
    message: 'Querying: NPDES Sites...',
    progress: 35,
    currentLayer: 5,
    totalLayers: 20,
  }
  await sleep(500)

  throw new Error('Connection timeout while querying NPDES Sites. Please try again.')
}
