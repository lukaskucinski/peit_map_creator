-- Add custom_display_name column to profiles table
-- This stores the user's preferred display name that persists across OAuth re-logins
-- Values:
--   - text string: Custom name set by user
--   - '' (empty string): User explicitly cleared their name (show email fallback)
--   - NULL: Never set, fallback to OAuth provider name

ALTER TABLE public.profiles
ADD COLUMN IF NOT EXISTS custom_display_name text;

-- Update the updated_at trigger to include new column changes
-- (The existing trigger should already handle this if you have one)
