/**
 * OAuth Callback Route
 *
 * Handles redirects from OAuth providers (Google, GitHub) and email confirmation links.
 * Exchanges the authorization code for a session and redirects to homepage.
 */

import { createClient } from "@/lib/supabase/server"
import { NextResponse } from "next/server"

export async function GET(request: Request) {
  const requestUrl = new URL(request.url)
  const code = requestUrl.searchParams.get("code")
  const origin = requestUrl.origin

  if (code) {
    const supabase = await createClient()
    await supabase.auth.exchangeCodeForSession(code)
  }

  // Redirect to home page after authentication
  return NextResponse.redirect(`${origin}/`)
}
