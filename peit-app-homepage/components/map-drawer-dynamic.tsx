"use client"

import dynamic from "next/dynamic"
import { Loader2 } from "lucide-react"

// Dynamically import MapDrawer with SSR disabled
// Leaflet requires browser APIs (window, document) that aren't available during SSR
const MapDrawer = dynamic(
  () => import("./map-drawer").then((mod) => mod.MapDrawer),
  {
    ssr: false,
    loading: () => (
      <div className="fixed inset-0 top-16 z-50 flex flex-col bg-background">
        <div className="flex items-center justify-center flex-1">
          <div className="flex flex-col items-center gap-3 text-muted-foreground">
            <Loader2 className="h-8 w-8 animate-spin" />
            <span className="text-sm">Loading map...</span>
          </div>
        </div>
      </div>
    ),
  }
)

export { MapDrawer }
