"use client"

import { Bookmark } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

interface ClaimJobPromptProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSignUp: () => void
  onSignIn: () => void
}

export function ClaimJobPrompt({ open, onOpenChange, onSignUp, onSignIn }: ClaimJobPromptProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md animate-in fade-in-0 zoom-in-95 duration-300">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 justify-center">
            <Bookmark className="h-5 w-5 text-primary" />
            Save this map to your history
          </DialogTitle>
          <DialogDescription className="text-center">
            Sign up to access your maps from any device.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col items-center text-center gap-4 py-2">
          <div className="flex gap-3">
            <Button onClick={onSignUp}>
              Sign Up
            </Button>
            <Button
              variant="outline"
              onClick={onSignIn}
              className="hover:bg-muted-foreground/10"
            >
              Sign In
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
