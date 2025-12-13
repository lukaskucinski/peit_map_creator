"use client"

import { Bookmark } from "lucide-react"
import { Button } from "@/components/ui/button"

interface ClaimJobPromptProps {
  onSignUp: () => void
  onSignIn: () => void
}

export function ClaimJobPrompt({ onSignUp, onSignIn }: ClaimJobPromptProps) {
  return (
    <div className="mt-4 p-4 rounded-lg border border-muted bg-muted/30">
      <div className="flex flex-col items-center text-center gap-3">
        <div className="flex items-center gap-2 text-sm font-medium text-foreground">
          <Bookmark className="h-4 w-4 text-primary" />
          Save this map to your history
        </div>
        <p className="text-xs text-muted-foreground">
          Sign up to access your maps from any device
        </p>
        <div className="flex gap-2">
          <Button size="sm" onClick={onSignUp}>
            Sign Up
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={onSignIn}
            className="hover:bg-muted-foreground/10"
          >
            Sign In
          </Button>
        </div>
      </div>
    </div>
  )
}
