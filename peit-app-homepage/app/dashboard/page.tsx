/**
 * Dashboard Page
 *
 * Displays user's job history. Requires authentication.
 * Fetches jobs from Supabase with RLS filtering by user_id.
 */

import { redirect } from "next/navigation"
import { createClient } from "@/lib/supabase/server"
import { Header } from "@/components/header"
import { JobHistoryList, type Job } from "@/components/dashboard/job-history-list"
import { Button } from "@/components/ui/button"
import { Plus } from "lucide-react"

export default async function DashboardPage() {
  const supabase = await createClient()

  // Check if user is authenticated
  const {
    data: { user },
  } = await supabase.auth.getUser()

  if (!user) {
    redirect("/")
  }

  // Fetch user's jobs (RLS automatically filters by user_id)
  const { data: jobs, error } = await supabase
    .from("jobs")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(50)

  if (error) {
    console.error("Error fetching jobs:", error)
  }

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="container mx-auto px-4 py-8">
        <div className="max-w-4xl mx-auto">
          {/* Header section */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-3xl font-bold">Job History</h1>
              <p className="text-muted-foreground mt-1">
                View your recent processing jobs (last 7 days)
              </p>
            </div>
            <Button asChild>
              <a href="/" className="gap-2">
                <Plus className="h-4 w-4" />
                New Map
              </a>
            </Button>
          </div>

          {/* Job list */}
          <JobHistoryList jobs={(jobs as Job[]) || []} />
        </div>
      </main>
    </div>
  )
}
