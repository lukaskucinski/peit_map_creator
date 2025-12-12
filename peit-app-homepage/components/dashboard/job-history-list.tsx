"use client"

import { formatDistanceToNow } from "date-fns"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  ExternalLink,
  Download,
  FileText,
  FileSpreadsheet,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
} from "lucide-react"

export interface Job {
  id: string
  filename: string
  project_name: string | null
  project_id: string | null
  status: "processing" | "complete" | "failed"
  created_at: string
  completed_at: string | null
  total_features: number | null
  layers_with_data: number | null
  map_url: string | null
  pdf_url: string | null
  xlsx_url: string | null
  zip_download_path: string | null
  error_message: string | null
  expires_at: string
}

interface JobHistoryListProps {
  jobs: Job[]
}

export function JobHistoryList({ jobs }: JobHistoryListProps) {
  const apiUrl = process.env.NEXT_PUBLIC_MODAL_API_URL || ""

  if (jobs.length === 0) {
    return (
      <Card>
        <CardContent className="pt-6 text-center">
          <div className="flex flex-col items-center gap-2">
            <Clock className="h-12 w-12 text-muted-foreground" />
            <p className="text-muted-foreground">
              No maps yet. Process a file to get started!
            </p>
            <Button variant="outline" className="mt-4" asChild>
              <a href="/">Create New Map</a>
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  const getStatusIcon = (status: Job["status"]) => {
    switch (status) {
      case "processing":
        return <Loader2 className="h-4 w-4 animate-spin text-primary" />
      case "complete":
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case "failed":
        return <XCircle className="h-4 w-4 text-destructive" />
    }
  }

  const getStatusBadgeVariant = (status: Job["status"]) => {
    switch (status) {
      case "processing":
        return "default"
      case "complete":
        return "secondary"
      case "failed":
        return "destructive"
    }
  }

  return (
    <div className="space-y-4">
      {/* Data retention notice */}
      <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
        <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
        <div>
          <strong>Data Retention:</strong> Maps are automatically deleted after 7
          days. Download the ZIP file for long-term data preservation.
        </div>
      </div>

      {jobs.map((job) => (
        <Card key={job.id}>
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <CardTitle className="text-lg truncate">
                  {job.project_name || job.filename}
                </CardTitle>
                <CardDescription className="truncate">
                  {job.project_id && (
                    <span className="mr-2">ID: {job.project_id}</span>
                  )}
                  {job.project_name && (
                    <span className="text-xs">({job.filename})</span>
                  )}
                </CardDescription>
              </div>
              <Badge
                variant={getStatusBadgeVariant(job.status)}
                className="gap-1 flex-shrink-0"
              >
                {getStatusIcon(job.status)}
                {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {/* Job metadata */}
              <div className="grid grid-cols-2 gap-2 text-sm text-muted-foreground">
                <div>
                  <span className="font-medium">Created:</span>{" "}
                  {formatDistanceToNow(new Date(job.created_at), {
                    addSuffix: true,
                  })}
                </div>
                {job.completed_at && (
                  <div>
                    <span className="font-medium">Completed:</span>{" "}
                    {formatDistanceToNow(new Date(job.completed_at), {
                      addSuffix: true,
                    })}
                  </div>
                )}
                {job.status === "complete" && job.total_features !== null && (
                  <>
                    <div>
                      <span className="font-medium">Features:</span>{" "}
                      {job.total_features.toLocaleString()}
                    </div>
                    <div>
                      <span className="font-medium">Layers:</span>{" "}
                      {job.layers_with_data}
                    </div>
                  </>
                )}
              </div>

              {/* Error message */}
              {job.status === "failed" && job.error_message && (
                <div className="text-sm text-destructive bg-destructive/10 p-2 rounded">
                  {job.error_message}
                </div>
              )}

              {/* Action buttons for completed jobs */}
              {job.status === "complete" && (
                <div className="flex flex-wrap gap-2 pt-2">
                  {job.map_url && (
                    <Button
                      size="sm"
                      variant="default"
                      onClick={() => window.open(job.map_url!, "_blank")}
                      className="gap-1"
                    >
                      <ExternalLink className="h-4 w-4" />
                      View Map
                    </Button>
                  )}
                  {job.zip_download_path && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        window.open(
                          `${apiUrl}${job.zip_download_path}`,
                          "_blank"
                        )
                      }
                      className="gap-1"
                    >
                      <Download className="h-4 w-4" />
                      Download ZIP
                    </Button>
                  )}
                  {job.pdf_url && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => window.open(job.pdf_url!, "_blank")}
                      className="gap-1"
                    >
                      <FileText className="h-4 w-4" />
                      PDF
                    </Button>
                  )}
                  {job.xlsx_url && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => window.open(job.xlsx_url!, "_blank")}
                      className="gap-1"
                    >
                      <FileSpreadsheet className="h-4 w-4" />
                      Excel
                    </Button>
                  )}
                </div>
              )}

              {/* Expiration notice */}
              <p className="text-xs text-muted-foreground">
                Expires{" "}
                {formatDistanceToNow(new Date(job.expires_at), {
                  addSuffix: true,
                })}
              </p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
