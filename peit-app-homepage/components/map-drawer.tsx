"use client"

import { useEffect, useRef, useState, useCallback } from "react"
import { MapContainer, TileLayer, FeatureGroup, useMap } from "react-leaflet"
import L from "leaflet"
import "leaflet/dist/leaflet.css"
import "@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css"
import "@geoman-io/leaflet-geoman-free"
import { useTheme } from "next-themes"
import { Button } from "@/components/ui/button"
import { X, Check, Trash2, Search, Layers, AlertCircle, Loader2 } from "lucide-react"
import { layersToGeoJSON, validateDrawnGeometry, getGeometrySummary, reverseGeocodeGeometry, reverseGeocodePoint, type LocationData } from "@/lib/geojson-utils"
import type { FeatureCollection } from "geojson"
import type { FeatureGroup as LeafletFeatureGroup } from "leaflet"
import * as turf from "@turf/turf"

// Fix Leaflet default icon paths (needed for markers)
delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
})

// CONUS center coordinates
const CONUS_CENTER: [number, number] = [39.8283, -98.5795]
const INITIAL_ZOOM = 4

// Base map options
const BASE_MAPS = {
  street: {
    name: "Street Map",
    url: "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  },
  light: {
    name: "Light Theme",
    url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>'
  },
  dark: {
    name: "Dark Theme",
    url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>'
  },
  satellite: {
    name: "Satellite",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attribution: '&copy; <a href="https://www.esri.com/">Esri</a>'
  }
}

interface MapDrawerProps {
  onComplete: (file: File, locationData?: LocationData | null) => void
  onCancel: () => void
  initialGeometry?: FeatureCollection
}

// Component to initialize Geoman drawing controls and handle events
function GeomanControls({
  featureGroupRef,
  onFeatureChange,
  onFirstVertex
}: {
  featureGroupRef: React.RefObject<LeafletFeatureGroup | null>
  onFeatureChange: () => void
  onFirstVertex?: (lat: number, lon: number) => void
}) {
  const map = useMap()
  const firstVertexFired = useRef(false)

  useEffect(() => {
    if (!map || !featureGroupRef.current) return

    // Small delay to ensure map is fully initialized
    const timer = setTimeout(() => {
      // Check if pm is available on the map
      if (!map.pm) {
        console.error("Geoman not initialized on map")
        return
      }

      // Add Geoman controls to the map
      map.pm.addControls({
        position: "topleft",
        drawMarker: true,
        drawCircleMarker: false,
        drawPolyline: true,
        drawRectangle: true,
        drawPolygon: true,
        drawCircle: false,
        drawText: false,
        editMode: true,
        dragMode: true,
        cutPolygon: false,
        removalMode: true,
        rotateMode: false,
      })

      // Set global options
      if (featureGroupRef.current) {
        map.pm.setGlobalOptions({
          layerGroup: featureGroupRef.current,
          snappable: true,
          snapDistance: 15,
        })
      }

      // Handler for first vertex placement (triggers background geocoding)
      const handleVertexAdded = (e: { latlng?: L.LatLng }) => {
        if (!firstVertexFired.current && onFirstVertex && e.latlng) {
          firstVertexFired.current = true
          onFirstVertex(e.latlng.lat, e.latlng.lng)
        }
      }

      // Handler for marker placement (single point features)
      const handleMarkerCreate = (e: { layer?: L.Layer }) => {
        if (!firstVertexFired.current && onFirstVertex && e.layer) {
          const marker = e.layer as L.Marker
          const latlng = marker.getLatLng()
          firstVertexFired.current = true
          onFirstVertex(latlng.lat, latlng.lng)
        }
      }

      // Set up event listeners for feature changes
      map.on("pm:create", onFeatureChange)
      map.on("pm:remove", onFeatureChange)
      map.on("pm:cut", onFeatureChange)

      // Set up event listeners for first vertex (background geocoding)
      map.on("pm:drawstart", () => {
        // Listen for vertex added on the working layer
        map.on("pm:vertexadded", handleVertexAdded)
      })

      // Listen for marker creation separately (markers don't fire vertexadded)
      map.on("pm:create", handleMarkerCreate)
    }, 100)

    return () => {
      clearTimeout(timer)
      // Cleanup event listeners
      map.off("pm:create", onFeatureChange)
      map.off("pm:remove", onFeatureChange)
      map.off("pm:cut", onFeatureChange)
      map.off("pm:drawstart")
      map.off("pm:vertexadded")
      // Cleanup Geoman controls on unmount
      if (map.pm) {
        map.pm.removeControls()
      }
    }
  }, [map, featureGroupRef, onFeatureChange, onFirstVertex])

  return null
}

// Component for address/coordinate search
function SearchControl() {
  const map = useMap()
  const [searchQuery, setSearchQuery] = useState("")
  const [isSearching, setIsSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) return

    setIsSearching(true)
    setSearchError(null)

    try {
      // Check if input looks like coordinates (lat, lng or lat lng)
      const coordMatch = searchQuery.match(/^(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)$/)

      if (coordMatch) {
        const lat = parseFloat(coordMatch[1])
        const lng = parseFloat(coordMatch[2])

        if (lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
          map.setView([lat, lng], 15)
          setIsSearching(false)
          return
        }
      }

      // Use Nominatim geocoder for address search
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(searchQuery)}&limit=1&countrycodes=us`,
        {
          headers: {
            "User-Agent": "PEIT-Map-Creator/1.0"
          }
        }
      )

      if (!response.ok) {
        throw new Error("Search failed")
      }

      const results = await response.json()

      if (results.length > 0) {
        const { lat, lon, boundingbox } = results[0]

        if (boundingbox) {
          map.fitBounds([
            [parseFloat(boundingbox[0]), parseFloat(boundingbox[2])],
            [parseFloat(boundingbox[1]), parseFloat(boundingbox[3])]
          ])
        } else {
          map.setView([parseFloat(lat), parseFloat(lon)], 15)
        }
      } else {
        setSearchError("Location not found")
      }
    } catch {
      setSearchError("Search failed. Please try again.")
    } finally {
      setIsSearching(false)
    }
  }, [map, searchQuery])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSearch()
    }
  }, [handleSearch])

  return (
    <div className="absolute top-3 right-3 z-[1000] flex flex-col gap-1">
      <div className="flex gap-1">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Search address or coordinates..."
          className="w-64 px-3 py-2 text-sm bg-white text-gray-900 placeholder:text-gray-500 border border-gray-300 rounded-lg shadow-md focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
          disabled={isSearching}
        />
        <Button
          size="sm"
          onClick={handleSearch}
          disabled={isSearching || !searchQuery.trim()}
          className="shadow-md"
        >
          <Search className="h-4 w-4" />
        </Button>
      </div>
      {searchError && (
        <div className="bg-red-50 text-red-600 text-xs px-2 py-1 rounded">
          {searchError}
        </div>
      )}
    </div>
  )
}

// Component to load initial geometry into the feature group
function InitialGeometryLoader({
  featureGroupRef,
  initialGeometry,
  onLoaded
}: {
  featureGroupRef: React.RefObject<LeafletFeatureGroup | null>
  initialGeometry: FeatureCollection
  onLoaded: () => void
}) {
  const map = useMap()

  useEffect(() => {
    if (!featureGroupRef.current || !initialGeometry?.features?.length) return

    // Small delay to ensure feature group is ready
    const timer = setTimeout(() => {
      const fg = featureGroupRef.current
      if (!fg) return

      // Clear any existing layers
      fg.clearLayers()

      // Add each feature as a Leaflet layer
      for (const feature of initialGeometry.features) {
        if (!feature.geometry) continue

        try {
          const layer = L.geoJSON(feature, {
            pointToLayer: (_, latlng) => L.marker(latlng),
          })

          // Add each layer from the GeoJSON layer group
          layer.eachLayer((l) => {
            fg.addLayer(l)
          })
        } catch (e) {
          console.error("Failed to add feature:", e)
        }
      }

      // Fit map to the geometry bounds
      if (fg.getLayers().length > 0) {
        try {
          const bounds = fg.getBounds()
          if (bounds.isValid()) {
            map.fitBounds(bounds, { padding: [50, 50] })
          }
        } catch (e) {
          console.error("Failed to fit bounds:", e)
        }
      }

      onLoaded()
    }, 150)

    return () => clearTimeout(timer)
  }, [featureGroupRef, initialGeometry, map, onLoaded])

  return null
}

// Component for base map selector
function BaseMapSelector({
  currentBaseMap,
  onBaseMapChange
}: {
  currentBaseMap: keyof typeof BASE_MAPS
  onBaseMapChange: (key: keyof typeof BASE_MAPS) => void
}) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="absolute bottom-3 right-3 z-[1000]">
      <div className="relative">
        <Button
          size="sm"
          variant="secondary"
          onClick={() => setIsOpen(!isOpen)}
          className="shadow-md bg-white hover:bg-gray-100 text-gray-900"
        >
          <Layers className="h-4 w-4 mr-1" />
          {BASE_MAPS[currentBaseMap].name}
        </Button>

        {isOpen && (
          <div className="absolute bottom-full right-0 mb-1 bg-white rounded-lg shadow-lg border border-gray-200 overflow-hidden min-w-[140px]">
            {Object.entries(BASE_MAPS).map(([key, value]) => (
              <button
                key={key}
                onClick={() => {
                  onBaseMapChange(key as keyof typeof BASE_MAPS)
                  setIsOpen(false)
                }}
                className={`w-full px-3 py-2 text-left text-sm text-gray-900 hover:bg-gray-100 ${
                  currentBaseMap === key ? "bg-gray-100 font-medium" : ""
                }`}
              >
                {value.name}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export function MapDrawer({ onComplete, onCancel, initialGeometry }: MapDrawerProps) {
  const { resolvedTheme } = useTheme()
  const [baseMap, setBaseMap] = useState<keyof typeof BASE_MAPS>("street")
  const [featureCount, setFeatureCount] = useState(0)
  const [validationError, setValidationError] = useState<string | null>(null)
  const featureGroupRef = useRef<LeafletFeatureGroup | null>(null)
  const initialBasemapSet = useRef(false)
  const initialGeometryLoaded = useRef(false)

  // Background geocoding state
  const [cachedLocationData, setCachedLocationData] = useState<LocationData | null>(null)
  const geocodingInProgress = useRef(false)
  const hasGeocodedRef = useRef(false)

  // Set default basemap based on theme (only once on initial mount)
  useEffect(() => {
    if (!initialBasemapSet.current && resolvedTheme) {
      initialBasemapSet.current = true
      if (resolvedTheme === "dark") {
        setBaseMap("dark")
      }
    }
  }, [resolvedTheme])

  // Update feature count when shapes are drawn or removed
  const updateFeatureCount = useCallback(() => {
    if (featureGroupRef.current) {
      const geojson = layersToGeoJSON(featureGroupRef.current)
      setFeatureCount(geojson.features.length)
      setValidationError(null)
    }
  }, [])

  // Background geocoding - triggers on first vertex placed
  const triggerBackgroundGeocode = useCallback(async (lat: number, lon: number) => {
    // Only geocode once per drawing session
    if (hasGeocodedRef.current || geocodingInProgress.current) return

    geocodingInProgress.current = true
    hasGeocodedRef.current = true

    try {
      const location = await reverseGeocodePoint(lat, lon)
      setCachedLocationData(location)
    } catch (error) {
      console.warn('Background geocoding failed:', error)
    } finally {
      geocodingInProgress.current = false
    }
  }, [])

  // Handle initial geometry loaded - geocode centroid for edit mode
  const handleInitialGeometryLoaded = useCallback(() => {
    initialGeometryLoaded.current = true
    updateFeatureCount()

    // Trigger background geocode from centroid of initial geometry
    if (initialGeometry && !hasGeocodedRef.current && featureGroupRef.current) {
      const geojson = layersToGeoJSON(featureGroupRef.current)
      if (geojson.features.length > 0) {
        try {
          const centroid = turf.centroid(geojson)
          const [lon, lat] = centroid.geometry.coordinates
          triggerBackgroundGeocode(lat, lon)
        } catch (error) {
          console.warn('Failed to calculate centroid for initial geometry:', error)
        }
      }
    }
  }, [updateFeatureCount, initialGeometry, triggerBackgroundGeocode])

  const handleClear = useCallback(() => {
    if (featureGroupRef.current) {
      featureGroupRef.current.clearLayers()
      setFeatureCount(0)
      setValidationError(null)
      // Reset geocoding state so next drawing session can trigger new geocode
      hasGeocodedRef.current = false
      setCachedLocationData(null)
    }
  }, [])

  const [isGeneratingFilename, setIsGeneratingFilename] = useState(false)

  const handleDone = useCallback(async () => {
    if (!featureGroupRef.current) return

    const geojson = layersToGeoJSON(featureGroupRef.current)
    const validation = validateDrawnGeometry(geojson)

    if (!validation.valid) {
      setValidationError(validation.error || "Invalid geometry")
      return
    }

    // Use cached location data if available, otherwise geocode now
    let locationData = cachedLocationData

    if (!locationData && !geocodingInProgress.current) {
      // No cached data and no geocoding in progress - geocode synchronously
      setIsGeneratingFilename(true)
      locationData = await reverseGeocodeGeometry(geojson)
      setIsGeneratingFilename(false)
    } else if (geocodingInProgress.current) {
      // Geocoding still in progress - wait for it with a brief spinner
      setIsGeneratingFilename(true)
      // Poll for completion (background geocode typically takes <1s)
      let attempts = 0
      while (geocodingInProgress.current && attempts < 30) {
        await new Promise(resolve => setTimeout(resolve, 100))
        attempts++
      }
      locationData = cachedLocationData
      setIsGeneratingFilename(false)
    }

    // Generate filename from location data
    let filename = 'drawn_geometry.geojson'
    if (locationData) {
      const parts = [locationData.city, locationData.county, locationData.stateAbbr]
        .filter(Boolean)
        .map(s => s.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, ''))
        .filter(s => s.length > 0)
      if (parts.length > 0) {
        filename = `${parts.join('_')}.geojson`
      }
    }

    // Convert to File and pass to parent with location data
    const jsonString = JSON.stringify(geojson, null, 2)
    const blob = new Blob([jsonString], { type: "application/geo+json" })
    const file = new File([blob], filename, { type: "application/geo+json" })

    onComplete(file, locationData)
  }, [onComplete, cachedLocationData])

  const currentGeojson = featureGroupRef.current ? layersToGeoJSON(featureGroupRef.current) : null
  const summary = currentGeojson ? getGeometrySummary(currentGeojson) : "No shapes drawn"

  return (
    <div className="fixed inset-0 top-16 z-50 flex flex-col bg-background">
      {/* Header Bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-card shrink-0">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Draw Your Geometry</h2>
          <p className="text-sm text-muted-foreground">
            Use the tools on the left to draw polygons, lines, or points
          </p>
        </div>
        <Button variant="ghost" size="icon" onClick={onCancel}>
          <X className="h-5 w-5" />
        </Button>
      </div>

      {/* Map Container - fills remaining space */}
      <div className="relative flex-1 min-h-0">
        <MapContainer
          center={CONUS_CENTER}
          zoom={INITIAL_ZOOM}
          className="h-full w-full"
        >
          <TileLayer
            key={baseMap}
            url={BASE_MAPS[baseMap].url}
            attribution={BASE_MAPS[baseMap].attribution}
          />
          <FeatureGroup ref={featureGroupRef}>
            <GeomanControls featureGroupRef={featureGroupRef} onFeatureChange={updateFeatureCount} onFirstVertex={triggerBackgroundGeocode} />
            {initialGeometry && !initialGeometryLoaded.current && (
              <InitialGeometryLoader
                featureGroupRef={featureGroupRef}
                initialGeometry={initialGeometry}
                onLoaded={handleInitialGeometryLoaded}
              />
            )}
          </FeatureGroup>
          <SearchControl />
          <BaseMapSelector currentBaseMap={baseMap} onBaseMapChange={setBaseMap} />
        </MapContainer>
      </div>

      {/* Footer Bar */}
      <div className="flex items-center justify-between px-4 py-3 border-t border-border bg-card shrink-0">
        <div className="flex items-center gap-4">
          <span className="text-sm text-muted-foreground">
            {featureCount > 0 ? summary : "Draw shapes on the map to get started"}
          </span>
          {validationError && (
            <div className="flex items-center gap-1 text-sm text-destructive">
              <AlertCircle className="h-4 w-4" />
              {validationError}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleClear}
            disabled={featureCount === 0}
          >
            <Trash2 className="h-4 w-4 mr-1" />
            Clear All
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={onCancel}
          >
            Cancel
          </Button>
          <Button
            size="sm"
            onClick={handleDone}
            disabled={featureCount === 0 || isGeneratingFilename}
            className="bg-green-600 hover:bg-green-700 text-white"
          >
            {isGeneratingFilename ? (
              <>
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                Processing...
              </>
            ) : (
              <>
                <Check className="h-4 w-4 mr-1" />
                Use This Geometry
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}
