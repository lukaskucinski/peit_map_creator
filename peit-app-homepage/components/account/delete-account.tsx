"use client"

import { useState } from "react"
import { createClient } from "@/lib/supabase/client"
import { useRouter } from "next/navigation"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Trash2, Loader2, AlertTriangle } from "lucide-react"

interface DeleteAccountProps {
  userEmail: string
  userId: string
}

export function DeleteAccount({ userEmail, userId }: DeleteAccountProps) {
  const [open, setOpen] = useState(false)
  const [confirmEmail, setConfirmEmail] = useState("")
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const router = useRouter()
  const supabase = createClient()

  const handleDelete = async () => {
    if (confirmEmail !== userEmail) {
      setError("Email doesn't match")
      return
    }

    setDeleting(true)
    setError(null)

    try {
      const apiUrl = process.env.NEXT_PUBLIC_MODAL_API_URL
      if (!apiUrl) {
        throw new Error("API not configured")
      }

      // Call backend to delete account
      const response = await fetch(`${apiUrl}/api/account`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ user_id: userId }),
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "Failed to delete account")
      }

      // Sign out locally - may fail with 403 since user is already deleted on server
      // That's OK, we just need to clear the local session
      try {
        await supabase.auth.signOut()
      } catch {
        // Ignore signOut errors - user is already deleted
      }

      // Redirect to home with success message
      router.push("/?deleted=true")
    } catch (err) {
      console.error("Delete error:", err)
      setError(err instanceof Error ? err.message : "Failed to delete account")
      setDeleting(false)
    }
  }

  const isEmailMatch = confirmEmail === userEmail

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3 p-3 rounded-lg bg-destructive/10 text-destructive">
        <AlertTriangle className="h-5 w-5 mt-0.5 flex-shrink-0" />
        <div className="text-sm">
          <p className="font-medium">Warning</p>
          <p>
            Deleting your account will permanently remove all your data,
            including your job history and saved maps. This action cannot be
            undone.
          </p>
        </div>
      </div>

      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogTrigger asChild>
          <Button variant="destructive" className="text-white">
            <Trash2 className="mr-2 h-4 w-4" />
            <span>Delete Account</span>
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
            <AlertDialogDescription className="space-y-3">
              <span className="block">
                This action cannot be undone. This will permanently delete your
                account and remove all associated data from our servers.
              </span>
              <span className="block font-medium text-foreground">
                To confirm, type your email address below:
              </span>
              <span className="block text-xs text-muted-foreground">
                {userEmail}
              </span>
            </AlertDialogDescription>
          </AlertDialogHeader>

          <div className="py-2">
            <Label htmlFor="confirm-email" className="sr-only">
              Confirm Email
            </Label>
            <Input
              id="confirm-email"
              type="email"
              placeholder="Type your email to confirm"
              value={confirmEmail}
              onChange={(e) => {
                setConfirmEmail(e.target.value)
                setError(null)
              }}
              disabled={deleting}
            />
            {error && (
              <p className="text-sm text-destructive mt-2">{error}</p>
            )}
          </div>

          <AlertDialogFooter>
            <AlertDialogCancel
              onClick={() => {
                setConfirmEmail("")
                setError(null)
              }}
              disabled={deleting}
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault()
                handleDelete()
              }}
              disabled={!isEmailMatch || deleting}
              className="bg-destructive text-white hover:bg-destructive/90"
            >
              {deleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                "Delete Account"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
