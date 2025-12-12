"use client"

import { useState, useEffect, useRef } from "react"
import { Star } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { createClient } from "@/lib/supabase/client"
import { getProfile } from "@/lib/supabase/profiles"
import { AuthModal } from "@/components/auth/auth-modal"
import { UserMenu } from "@/components/auth/user-menu"
import type { User } from "@supabase/supabase-js"

// Landcover icon component (from layer-landcover.svg)
function LandcoverIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 100 100"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M49.932 22.56a4.725 2.593 0 0 0-3.274.76L1.383 48.166a4.725 2.593 0 0 0 0 3.668L46.658 76.68a4.725 2.593 0 0 0 6.684 0l45.275-24.846a4.725 2.593 0 0 0 0-3.668L53.342 23.32a4.725 2.593 0 0 0-3.41-.76zM50 28.82l8.713 4.782a25.922 25.922 0 0 0-3.606 1.705c-2.827 1.61-5.458 3.774-6.994 6.636c-6.097-.96-12.326-1.538-18.468-1.953L50 28.82zm15.297 8.395L88.596 50l-7.639 4.191c-7.813-5.86-17.33-9.24-27.441-11.29c1.018-1.175 2.451-2.33 4.064-3.249c2.43-1.383 5.237-2.227 6.963-2.304a2.5 2.5 0 0 0 .754-.133zm-43.793 7.244a2.5 2.5 0 0 0 .506.078c19.426 1.07 40.051 2.978 54.074 12.328l-3.334 1.83c-7.592-4.899-16.302-8.454-27.129-7.892c-6.456.335-13.67 2.145-21.84 5.988L11.406 50l10.098-5.541zm27.258 11.08c7.27.138 13.278 2.534 18.96 5.916L50 71.18L29.277 59.807c7.526-3.144 13.88-4.374 19.485-4.268z" />
    </svg>
  )
}

// GitHub icon component
function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
      />
    </svg>
  )
}

export function Header() {
  const [user, setUser] = useState<User | null>(null)
  const [customAvatarUrl, setCustomAvatarUrl] = useState<string | null>(null)
  const [customDisplayName, setCustomDisplayName] = useState<string | null>(null)
  const [profileLoaded, setProfileLoaded] = useState(false)
  const [authModalOpen, setAuthModalOpen] = useState(false)
  const [authModalTab, setAuthModalTab] = useState<"signin" | "signup">("signin")
  // Memoize supabase client to prevent useEffect from re-running on every render
  const [supabase] = useState(() => createClient())

  // Track current user ID to avoid unnecessary re-fetches
  const currentUserIdRef = useRef<string | null>(null)

  // Fetch custom profile data (avatar and display name) from profiles table
  const fetchProfile = async (userId: string) => {
    try {
      const profile = await getProfile(userId)
      setCustomAvatarUrl(profile?.custom_avatar_url ?? null)
      setCustomDisplayName(profile?.custom_display_name ?? null)
    } catch (error) {
      console.error("Error fetching profile:", error)
      setCustomAvatarUrl(null)
      setCustomDisplayName(null)
    } finally {
      setProfileLoaded(true)
    }
  }

  useEffect(() => {
    // Get initial session
    supabase.auth.getSession().then(async ({ data: { session } }) => {
      const newUser = session?.user ?? null
      setUser(newUser)
      currentUserIdRef.current = newUser?.id ?? null
      if (newUser) {
        await fetchProfile(newUser.id)
      } else {
        setProfileLoaded(true)
      }
    })

    // Listen for auth changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (_event, session) => {
      const newUser = session?.user ?? null
      const previousUserId = currentUserIdRef.current
      const newUserId = newUser?.id ?? null

      // Only update if user actually changed
      if (previousUserId !== newUserId) {
        setUser(newUser)
        currentUserIdRef.current = newUserId
        if (newUser) {
          setProfileLoaded(false)
          await fetchProfile(newUser.id)
        } else {
          setCustomAvatarUrl(null)
          setCustomDisplayName(null)
          setProfileLoaded(true)
        }
      }
    })

    return () => subscription.unsubscribe()
  }, [supabase]) // supabase is stable (memoized via useState)

  const openAuthModal = (tab: "signin" | "signup") => {
    setAuthModalTab(tab)
    setAuthModalOpen(true)
  }

  return (
    <>
      <header className="border-b border-border bg-card">
        <div className="flex h-16 items-center justify-between px-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <LandcoverIcon className="h-6 w-6 text-primary-foreground" />
            </div>
            <span className="text-lg font-semibold text-foreground">
              <span className="hidden sm:inline">PEIT Map Creator - Permitting and Environmental Information Tool</span>
              <span className="sm:hidden">PEIT Map Creator</span>
            </span>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            {/* GitHub Button - Functional */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  asChild
                >
                  <a
                    href="https://github.com/lukaskucinski/peit_map_creator"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <GitHubIcon className="h-4 w-4" />
                    <span className="hidden sm:inline">GitHub</span>
                  </a>
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">
                <p>PEIT is still under development. Follow our progress here</p>
              </TooltipContent>
            </Tooltip>

            {/* Donations Button */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  asChild
                >
                  <a
                    href="https://buymeacoffee.com/kucimaps"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Star className="h-4 w-4" />
                    <span className="hidden sm:inline">Donations</span>
                  </a>
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">
                <p>Help keep our servers running - every contribution counts!</p>
              </TooltipContent>
            </Tooltip>

            {user && profileLoaded ? (
              // Logged in and profile loaded: Show user menu
              <UserMenu user={user} customAvatarUrl={customAvatarUrl} customDisplayName={customDisplayName} />
            ) : user && !profileLoaded ? (
              // Logged in but loading profile: Show placeholder
              <div className="h-9 w-9 rounded-full bg-muted animate-pulse" />
            ) : (
              // Logged out: Show Sign In / Sign Up buttons
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  className="hidden sm:inline-flex"
                  onClick={() => openAuthModal("signin")}
                >
                  Sign In
                </Button>
                <Button
                  size="sm"
                  className="hidden sm:inline-flex"
                  onClick={() => openAuthModal("signup")}
                >
                  Sign Up
                </Button>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Auth Modal */}
      <AuthModal
        open={authModalOpen}
        onOpenChange={setAuthModalOpen}
        defaultTab={authModalTab}
      />
    </>
  )
}
