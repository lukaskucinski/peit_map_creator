import { createClient } from "./client"

export interface Profile {
  id: string
  custom_avatar_url: string | null
  created_at: string
  updated_at: string
}

/**
 * Get the user's profile from the profiles table
 */
export async function getProfile(userId: string): Promise<Profile | null> {
  const supabase = createClient()

  const { data, error } = await supabase
    .from("profiles")
    .select("*")
    .eq("id", userId)
    .single()

  if (error) {
    // Profile might not exist yet for older users
    if (error.code === "PGRST116") {
      return null
    }
    console.error("Error fetching profile:", error)
    return null
  }

  return data
}

/**
 * Update the user's custom avatar URL in the profiles table
 */
export async function updateCustomAvatar(
  userId: string,
  avatarUrl: string | null
): Promise<{ success: boolean; error?: string }> {
  const supabase = createClient()

  // First try to update existing profile
  const { error: updateError } = await supabase
    .from("profiles")
    .update({ custom_avatar_url: avatarUrl })
    .eq("id", userId)

  if (updateError) {
    // If profile doesn't exist, create it (for users created before this migration)
    if (updateError.code === "PGRST116") {
      const { error: insertError } = await supabase
        .from("profiles")
        .insert({ id: userId, custom_avatar_url: avatarUrl })

      if (insertError) {
        console.error("Error creating profile:", insertError)
        return { success: false, error: insertError.message }
      }
      return { success: true }
    }

    console.error("Error updating custom avatar:", updateError)
    return { success: false, error: updateError.message }
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
