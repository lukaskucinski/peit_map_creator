/**
 * Account Settings Page
 *
 * Displays account information and allows users to delete their account.
 * Requires authentication - redirects to home if not logged in.
 */

import { redirect } from "next/navigation"
import { createClient } from "@/lib/supabase/server"
import { Header } from "@/components/header"
import { DeleteAccount } from "@/components/account/delete-account"
import { ThemeSelector } from "@/components/theme-toggle"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { ArrowLeft } from "lucide-react"

export default async function AccountPage() {
  const supabase = await createClient()

  // Check if user is authenticated
  const {
    data: { user },
  } = await supabase.auth.getUser()

  if (!user) {
    redirect("/")
  }

  // Get display name from OAuth provider
  const displayName =
    user.user_metadata?.full_name ||
    user.user_metadata?.name ||
    user.email?.split("@")[0] ||
    "User"

  // Get avatar from OAuth provider (Google uses 'picture', GitHub uses 'avatar_url')
  const avatarUrl = user.user_metadata?.avatar_url || user.user_metadata?.picture

  // Get initials for fallback
  const getInitials = () => {
    if (displayName && displayName !== "User") {
      return displayName
        .split(" ")
        .map((n: string) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    }
    return user.email?.slice(0, 2).toUpperCase() || "U"
  }

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="container mx-auto px-4 py-8">
        <div className="max-w-2xl mx-auto">
          {/* Back button */}
          <Button variant="ghost" className="mb-6 gap-2" asChild>
            <a href="/">
              <ArrowLeft className="h-4 w-4" />
              Back to Home
            </a>
          </Button>

          <h1 className="text-3xl font-bold mb-6">Account Settings</h1>

          {/* Profile Section */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle>Profile</CardTitle>
              <CardDescription>
                Your profile information from your sign-in provider
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-4">
                <Avatar className="h-16 w-16">
                  <AvatarImage src={avatarUrl || undefined} alt={displayName} />
                  <AvatarFallback className="text-lg">{getInitials()}</AvatarFallback>
                </Avatar>
                <div>
                  <p className="font-medium">{displayName}</p>
                  <p className="text-sm text-muted-foreground">{user.email}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Account Info Section */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle>Account Information</CardTitle>
              <CardDescription>Your account details</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium text-muted-foreground">
                  Email
                </label>
                <p className="text-sm">{user.email}</p>
              </div>
              <div>
                <label className="text-sm font-medium text-muted-foreground">
                  Account Created
                </label>
                <p className="text-sm">
                  {new Date(user.created_at).toLocaleDateString("en-US", {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })}
                </p>
              </div>
              <div>
                <label className="text-sm font-medium text-muted-foreground">
                  Sign-in Method
                </label>
                <p className="text-sm capitalize">
                  {user.app_metadata?.provider || "Email"}
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Appearance Section */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle>Appearance</CardTitle>
              <CardDescription>
                Customize how the app looks on your device
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div>
                <label className="text-sm font-medium text-muted-foreground mb-3 block">
                  Theme
                </label>
                <ThemeSelector />
                <p className="text-xs text-muted-foreground mt-2">
                  Your preference is saved to this browser and will persist across sessions.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Danger Zone */}
          <Card className="border-destructive/50">
            <CardHeader>
              <CardTitle className="text-destructive">Danger Zone</CardTitle>
              <CardDescription>
                Irreversible actions that affect your account
              </CardDescription>
            </CardHeader>
            <CardContent>
              <DeleteAccount userEmail={user.email || ""} userId={user.id} />
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  )
}
