/**
 * Account Settings Page
 *
 * Allows users to manage their profile (avatar) and delete their account.
 * Requires authentication - redirects to home if not logged in.
 */

import { redirect } from "next/navigation"
import { createClient } from "@/lib/supabase/server"
import { Header } from "@/components/header"
import { AvatarUpload } from "@/components/account/avatar-upload"
import { DeleteAccount } from "@/components/account/delete-account"
import type { Profile } from "@/lib/supabase/profiles"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
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

  // Fetch custom avatar from profiles table
  const { data: profile } = await supabase
    .from("profiles")
    .select("*")
    .eq("id", user.id)
    .single<Profile>()

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
                Manage your profile picture and display name
              </CardDescription>
            </CardHeader>
            <CardContent>
              <AvatarUpload user={user} customAvatarUrl={profile?.custom_avatar_url} customDisplayName={profile?.custom_display_name} />
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
