import { NextRequest, NextResponse } from 'next/server'
import { list } from '@vercel/blob'
import { createClient } from '@supabase/supabase-js'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ jobId: string }> }
) {
  const { jobId } = await params

  // Validate job ID format (16 hex chars)
  if (!/^[a-f0-9]{16}$/i.test(jobId)) {
    return NextResponse.redirect(new URL('/maps/expired', request.url))
  }

  let blobUrl: string | null = null

  // Try to get direct blob URL from database (fast path - no Advanced Operations)
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
  const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY

  if (supabaseUrl && supabaseKey) {
    try {
      const supabase = createClient(supabaseUrl, supabaseKey)
      const { data, error } = await supabase
        .from('jobs')
        .select('map_blob_url')
        .eq('id', jobId)
        .single()

      if (!error && data?.map_blob_url) {
        blobUrl = data.map_blob_url
        console.log(`Direct blob URL from database for ${jobId}`)
      }
    } catch (dbError) {
      console.warn('Database lookup failed, falling back to list():', dbError)
    }
  }

  // Fallback: Use list() for older jobs without map_blob_url
  if (!blobUrl) {
    const token = process.env.BLOB_READ_WRITE_TOKEN
    if (!token) {
      console.error('BLOB_READ_WRITE_TOKEN not configured')
      return NextResponse.redirect(new URL('/maps/expired', request.url))
    }

    try {
      const { blobs } = await list({
        prefix: `maps/${jobId}/index.html`,
        token
      })

      console.log(`Blob list() fallback for ${jobId}: found ${blobs.length} blobs`)

      if (blobs.length > 0 && blobs[0].url) {
        blobUrl = blobs[0].url
      }
    } catch (error) {
      console.error('Blob list() error:', error)
    }
  }

  // If no blob found via either method, redirect to expired page
  if (!blobUrl) {
    return NextResponse.redirect(new URL('/maps/expired', request.url))
  }

  // Fetch the HTML content from blob storage
  try {
    const response = await fetch(blobUrl)
    if (!response.ok) {
      return NextResponse.redirect(new URL('/maps/expired', request.url))
    }

    const html = await response.text()

    // Return the HTML with correct content-type (displays in browser, not downloads)
    // Use no-store to ensure deletion takes effect immediately
    // (Vercel Blob already handles caching at the storage layer)
    return new NextResponse(html, {
      status: 200,
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'private, no-store',
      },
    })
  } catch (error) {
    console.error('Error fetching map content:', error)
    return NextResponse.redirect(new URL('/maps/expired', request.url))
  }
}
