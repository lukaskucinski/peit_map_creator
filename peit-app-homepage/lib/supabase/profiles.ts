import { createClient } from "./client"

export interface Profile {
  id: string
  custom_avatar_url: string | null
  created_at: string
  updated_at: string
}

/**
 * Get the user's profile from the profiles table
 * Uses maybeSingle() to handle case where profile doesn't exist (returns null, no error)
 */
export async function getProfile(userId: string): Promise<Profile | null> {
  const supabase = createClient()

  const { data, error } = await supabase
    .from("profiles")
    .select("*")
    .eq("id", userId)
    .maybeSingle()

  if (error) {
    console.error("Error fetching profile:", error)
    return null
  }

  return data
}

/**
 * Update the user's custom avatar URL in the profiles table
 * Uses upsert to handle both existing and new profiles
 *
 * Avatar values:
 * - string URL: Custom avatar uploaded by user
 * - "" (empty string): User explicitly removed their avatar (don't fallback to OAuth)
 * - null: Never set a custom avatar (fallback to OAuth avatar allowed)
 */
export async function updateCustomAvatar(
  userId: string,
  avatarUrl: string | null
): Promise<{ success: boolean; error?: string }> {
  const supabase = createClient()

  // Use upsert to create profile if it doesn't exist, or update if it does
  const { error } = await supabase
    .from("profiles")
    .upsert(
      { id: userId, custom_avatar_url: avatarUrl },
      { onConflict: "id" }
    )

  if (error) {
    console.error("Error updating custom avatar:", error)
    return { success: false, error: error.message }
  }

  return { success: true }
}

/**
 * Ensure a profile exists for the user (upsert)
 * Call this after OAuth login to ensure profile row exists
 */
export async function ensureProfile(userId: string): Promise<void> {
  const supabase = createClient()

  const { error } = await supabase
    .from("profiles")
    .upsert({ id: userId }, { onConflict: "id", ignoreDuplicates: true })

  if (error) {
    console.error("Error ensuring profile exists:", error)
  }
}
