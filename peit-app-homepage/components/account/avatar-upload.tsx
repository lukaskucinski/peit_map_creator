"use client"

import { useState, useRef } from "react"
import { createClient } from "@/lib/supabase/client"
import { useRouter } from "next/navigation"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Camera, Loader2, Trash2, Check } from "lucide-react"
import type { User } from "@supabase/supabase-js"

interface AvatarUploadProps {
  user: User
}

export function AvatarUpload({ user }: AvatarUploadProps) {
  const [uploading, setUploading] = useState(false)
  const [removing, setRemoving] = useState(false)
  const [savingName, setSavingName] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [displayName, setDisplayName] = useState(
    user.user_metadata?.full_name || user.user_metadata?.name || ""
  )
  const [avatarUrl, setAvatarUrl] = useState(
    user.user_metadata?.avatar_url || ""
  )
  const fileInputRef = useRef<HTMLInputElement>(null)
  const router = useRouter()
  const supabase = createClient()

  // Get user initials for avatar fallback
  const getInitials = () => {
    if (displayName) {
      return displayName
        .split(" ")
        .map((n: string) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    }
    return user.email?.slice(0, 2).toUpperCase() || "U"
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Validate file type
    if (!file.type.startsWith("image/")) {
      setError("Please select an image file")
      return
    }

    // Validate file size (max 1MB)
    if (file.size > 1024 * 1024) {
      setError("Image must be less than 1MB")
      return
    }

    setUploading(true)
    setError(null)
    setSuccess(null)

    try {
      // Create unique filename
      const fileExt = file.name.split(".").pop()
      const fileName = `${user.id}-${Date.now()}.${fileExt}`
      const filePath = `avatars/${fileName}`

      // Upload to Supabase Storage
      const { error: uploadError } = await supabase.storage
        .from("avatars")
        .upload(filePath, file, {
          cacheControl: "3600",
          upsert: false,
        })

      if (uploadError) {
        // Check if it's a bucket not found error
        if (uploadError.message.includes("not found")) {
          setError(
            "Avatar storage not configured. Please contact support."
          )
          return
        }
        throw uploadError
      }

      // Get public URL
      const {
        data: { publicUrl },
      } = supabase.storage.from("avatars").getPublicUrl(filePath)

      // Update user metadata
      const { error: updateError } = await supabase.auth.updateUser({
        data: { avatar_url: publicUrl },
      })

      if (updateError) throw updateError

      setAvatarUrl(publicUrl)
      setSuccess("Avatar updated successfully!")
      router.refresh()
    } catch (err) {
      console.error("Upload error:", err)
      setError(err instanceof Error ? err.message : "Failed to upload avatar")
    } finally {
      setUploading(false)
      // Clear file input
      if (fileInputRef.current) {
        fileInputRef.current.value = ""
      }
    }
  }

  const handleRemoveAvatar = async () => {
    setRemoving(true)
    setError(null)
    setSuccess(null)

    try {
      // Update user metadata to remove avatar
      const { error: updateError } = await supabase.auth.updateUser({
        data: { avatar_url: null },
      })

      if (updateError) throw updateError

      setAvatarUrl("")
      setSuccess("Avatar removed successfully!")
      router.refresh()
    } catch (err) {
      console.error("Remove error:", err)
      setError(err instanceof Error ? err.message : "Failed to remove avatar")
    } finally {
      setRemoving(false)
    }
  }

  const handleSaveDisplayName = async () => {
    setSavingName(true)
    setError(null)
    setSuccess(null)

    try {
      const { error: updateError } = await supabase.auth.updateUser({
        data: { full_name: displayName },
      })

      if (updateError) throw updateError

      setSuccess("Display name updated successfully!")
      router.refresh()
    } catch (err) {
      console.error("Update error:", err)
      setError(
        err instanceof Error ? err.message : "Failed to update display name"
      )
    } finally {
      setSavingName(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Avatar Section */}
      <div className="flex items-center gap-6">
        <div className="relative">
          <Avatar className="h-24 w-24">
            <AvatarImage src={avatarUrl} alt={displayName || "User avatar"} />
            <AvatarFallback className="text-2xl">{getInitials()}</AvatarFallback>
          </Avatar>
          <Button
            size="icon"
            variant="secondary"
            className="absolute -bottom-1 -right-1 h-8 w-8 rounded-full"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Camera className="h-4 w-4" />
            )}
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleFileSelect}
            disabled={uploading}
          />
        </div>

        <div className="flex-1 space-y-2">
          <p className="text-sm text-muted-foreground">
            Click the camera icon to upload a new avatar.
            <br />
            Max file size: 1MB. Supported: JPG, PNG, GIF, WebP.
          </p>
          {avatarUrl && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleRemoveAvatar}
              disabled={removing}
              className="gap-2"
            >
              {removing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
              Remove Avatar
            </Button>
          )}
        </div>
      </div>

      {/* Display Name Section */}
      <div className="space-y-2">
        <Label htmlFor="displayName">Display Name</Label>
        <div className="flex gap-2">
          <Input
            id="displayName"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Enter your display name"
            disabled={savingName}
          />
          <Button
            onClick={handleSaveDisplayName}
            disabled={savingName || !displayName.trim()}
            className="gap-2"
          >
            {savingName ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Check className="h-4 w-4" />
            )}
            Save
          </Button>
        </div>
      </div>

      {/* Status Messages */}
      {error && (
        <p className="text-sm text-destructive bg-destructive/10 p-2 rounded">
          {error}
        </p>
      )}
      {success && (
        <p className="text-sm text-green-600 bg-green-50 dark:bg-green-950 p-2 rounded">
          {success}
        </p>
      )}
    </div>
  )
}
