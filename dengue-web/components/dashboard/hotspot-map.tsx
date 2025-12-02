"use client"

import { useState, useMemo, useCallback } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"
import { Play, Pause, SkipBack, SkipForward, MapPin, Layers } from "lucide-react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

// Generate 182 barangays with coordinates (simulating Metro Manila area)
const generateBarangayData = () => {
  const barangayNames = [
    "Poblacion",
    "San Jose",
    "San Antonio",
    "San Isidro",
    "Santo Niño",
    "Sta. Cruz",
    "Sta. Maria",
    "San Miguel",
    "San Rafael",
    "San Vicente",
    "Bagumbayan",
    "Maligaya",
    "Mabuhay",
    "Kamuning",
    "Barangka",
    "Plainview",
    "Addition Hills",
    "Highway Hills",
    "Burol",
    "Paliparan",
    "Langkaan",
    "Salawag",
    "Sampaloc",
    "Sabang",
    "Salitran",
    "Datu",
    "Fatima",
    "San Agustin",
    "San Dionisio",
    "San Francisco",
    "San Juan",
    "San Nicolas",
    "San Pedro",
    "San Roque",
    "Santa Ana",
    "Santa Barbara",
    "Santa Elena",
    "Santa Lucia",
    "Santa Monica",
    "Santa Rosa",
    "Santiago",
    "Santo Cristo",
    "Santo Domingo",
    "Assumption",
    "Bel-Air",
    "Cembo",
    "Comembo",
    "Dasmariñas",
    "East Rembo",
    "Forbes Park",
    "Guadalupe Nuevo",
    "Guadalupe Viejo",
    "Kasilawan",
    "La Paz",
    "Magallanes",
    "Olympia",
    "Palanan",
    "Pio del Pilar",
    "Pitogo",
    "Post Proper North",
    "Post Proper South",
    "Rizal",
    "San Isidro Labrador",
    "Santa Clara",
    "Singkamas",
    "South Cembo",
    "Tejeros",
    "Valenzuela",
    "West Rembo",
    "Bangkal",
    "Buting",
    "Carmona",
    "Dela Paz",
    "East Kamias",
    "Escopa",
    "Kapasigan",
    "Kapitolyo",
    "Manggahan",
    "Maybunga",
    "Oranbo",
    "Pasig",
    "Pinagbuhatan",
    "Pineda",
    "Rosario",
    "Sagad",
    "San Joaquin",
    "Santa Lucia Old",
    "Santolan",
    "Sumilang",
    "Ugong",
    "Bambang",
    "Bignay",
    "Caniogan",
    "Concepcion",
    "Dulong Bayan",
    "Gulod",
    "Malanday",
    "Malis",
    "Panghulo",
    "Potrero",
    "Sta. Clara Del Monte",
    "Sto. Cristo",
    "Sto. Rosario",
    "Tugatog",
    "Ubihan",
    "Baesa",
    "Bagong Barrio",
    "Balintawak",
    "Capri",
    "Coloong",
    "Deparo",
    "Gen. T. de Leon",
    "Isla",
    "Karuhatan",
    "Lawang Bato",
    "Lingunan",
    "Mabolo",
    "Malanday Norte",
    "Malinta",
    "Mapulang Lupa",
    "Marulas",
    "Maysan",
    "Parada",
    "Pariancillo Villa",
    "Paso de Blas",
    "Pasolo",
    "Poblacion Norte",
    "Poblacion Sur",
    "Polo",
    "Punturin",
    "Rincon",
    "Tagalag",
    "Ugong Norte",
    "Viente Reales",
    "Wawang Pulo",
    "Arkong Bato",
    "Balangkas",
    "Bignay Sur",
    "Bisig",
    "Canumay",
    "Coloong Sur",
    "Dalandanan",
    "Hen. de Leon",
    "Isla Norte",
    "Isla Sur",
    "Karuhatan Sur",
    "Lawang Bato Sur",
    "Lingunan Sur",
    "Mabolo Sur",
    "Malanday Sur",
    "Malinta Sur",
    "Mapulang Lupa Sur",
    "Marulas Sur",
    "Maysan Sur",
    "Parada Sur",
    "Pasolo Sur",
    "Polo Sur",
    "Punturin Sur",
    "Rincon Sur",
    "Tagalag Sur",
    "Ugong Sur",
    "Veinte Reales Sur",
    "Bagong Silang",
    "Batasan Hills",
    "Commonwealth",
    "Holy Spirit",
    "Payatas",
    "Bagong Pag-asa",
    "Bahay Toro",
    "Balingasa",
    "Bungad",
    "Damar",
    "Damayan",
    "Del Monte",
    "Katipunan",
    "Lourdes",
    "Maharlika",
    "Manresa",
    "Masambong",
    "N.S. Amoranto",
    "Nayong Kanluran",
    "Paang Bundok",
    "Pag-ibig sa Nayon",
    "Paltok",
    "Paraiso",
    "Phil-Am",
    "Project 6",
    "Ramon Magsaysay",
    "Saint Peter",
  ]

  return barangayNames.slice(0, 182).map((name, i) => {
    // Generate coordinates in Metro Manila area (roughly 14.5-14.7 lat, 120.9-121.1 lng)
    const lat = 14.55 + Math.random() * 0.2 - 0.1 + (i % 13) * 0.015
    const lng = 121.0 + Math.random() * 0.15 - 0.075 + (Math.floor(i / 13) % 14) * 0.01

    // Generate historical data for 12 weeks
    const weeklyData = Array.from({ length: 12 }, (_, weekIdx) => {
      const baseCases = Math.floor(Math.random() * 300) + 20
      const seasonalFactor = 1 + Math.sin((weekIdx / 12) * Math.PI) * 0.5
      return Math.floor(baseCases * seasonalFactor)
    })

    return {
      id: i + 1,
      name: `${name}${i >= barangayNames.length ? ` ${Math.floor(i / barangayNames.length) + 1}` : ""}`,
      lat,
      lng,
      weeklyData,
    }
  })
}

const barangays = generateBarangayData()

const getSeverity = (cases: number) => {
  if (cases > 250) return { level: "critical", color: "#ef4444", size: 28 }
  if (cases > 150) return { level: "high", color: "#f97316", size: 22 }
  if (cases > 75) return { level: "medium", color: "#eab308", size: 16 }
  return { level: "low", color: "#22c55e", size: 10 }
}

const weeks = [
  "Sep 9",
  "Sep 16",
  "Sep 23",
  "Sep 30",
  "Oct 7",
  "Oct 14",
  "Oct 21",
  "Oct 28",
  "Nov 4",
  "Nov 11",
  "Nov 18",
  "Nov 25",
]

export function HotspotMap() {
  const [selectedWeek, setSelectedWeek] = useState(11)
  const [isPlaying, setIsPlaying] = useState(false)
  const [hoveredBarangay, setHoveredBarangay] = useState<(typeof barangays)[0] | null>(null)
  const [mapView, setMapView] = useState<"heatmap" | "markers">("heatmap")

  // Animation effect
  const handlePlayPause = useCallback(() => {
    setIsPlaying((prev) => !prev)
  }, [])

  // Auto-advance when playing
  useState(() => {
    if (!isPlaying) return
    const interval = setInterval(() => {
      setSelectedWeek((prev) => (prev >= 11 ? 0 : prev + 1))
    }, 1000)
    return () => clearInterval(interval)
  })

  const currentData = useMemo(() => {
    return barangays.map((b) => ({
      ...b,
      cases: b.weeklyData[selectedWeek],
      severity: getSeverity(b.weeklyData[selectedWeek]),
    }))
  }, [selectedWeek])

  const stats = useMemo(() => {
    const data = currentData
    return {
      totalCases: data.reduce((acc, b) => acc + b.cases, 0),
      critical: data.filter((b) => b.severity.level === "critical").length,
      high: data.filter((b) => b.severity.level === "high").length,
      medium: data.filter((b) => b.severity.level === "medium").length,
      low: data.filter((b) => b.severity.level === "low").length,
      hottest: data.reduce((max, b) => (b.cases > max.cases ? b : max), data[0]),
    }
  }, [currentData])

  // Map bounds for positioning (normalized to 0-100 scale)
  const mapBounds = useMemo(() => {
    const lats = barangays.map((b) => b.lat)
    const lngs = barangays.map((b) => b.lng)
    return {
      minLat: Math.min(...lats),
      maxLat: Math.max(...lats),
      minLng: Math.min(...lngs),
      maxLng: Math.max(...lngs),
    }
  }, [])

  const getPosition = (lat: number, lng: number) => {
    const x = ((lng - mapBounds.minLng) / (mapBounds.maxLng - mapBounds.minLng)) * 90 + 5
    const y = ((mapBounds.maxLat - lat) / (mapBounds.maxLat - mapBounds.minLat)) * 85 + 5
    return { x, y }
  }

  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CardTitle className="text-lg font-semibold">Outbreak Hotspot Map</CardTitle>
              <Badge variant="outline" className="text-xs">
                Week of {weeks[selectedWeek]}
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              <Select value={mapView} onValueChange={(v: "heatmap" | "markers") => setMapView(v)}>
                <SelectTrigger className="h-8 w-[120px] bg-secondary text-xs">
                  <Layers className="mr-1 h-3 w-3" />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="heatmap">Heatmap</SelectItem>
                  <SelectItem value="markers">Markers</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Summary Stats */}
          <div className="grid grid-cols-5 gap-2 text-center">
            <div className="rounded-lg bg-secondary/50 p-2">
              <div className="text-lg font-bold text-foreground">{stats.totalCases.toLocaleString()}</div>
              <div className="text-[10px] text-muted-foreground">Total Cases</div>
            </div>
            <div className="rounded-lg bg-red-500/10 p-2">
              <div className="text-lg font-bold text-red-400">{stats.critical}</div>
              <div className="text-[10px] text-red-400/70">Critical</div>
            </div>
            <div className="rounded-lg bg-orange-500/10 p-2">
              <div className="text-lg font-bold text-orange-400">{stats.high}</div>
              <div className="text-[10px] text-orange-400/70">High</div>
            </div>
            <div className="rounded-lg bg-yellow-500/10 p-2">
              <div className="text-lg font-bold text-yellow-400">{stats.medium}</div>
              <div className="text-[10px] text-yellow-400/70">Medium</div>
            </div>
            <div className="rounded-lg bg-green-500/10 p-2">
              <div className="text-lg font-bold text-green-400">{stats.low}</div>
              <div className="text-[10px] text-green-400/70">Low</div>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Map Container */}
        <div className="relative h-[400px] w-full overflow-hidden rounded-lg bg-slate-900/50 border border-border">
          {/* Background Grid */}
          <div className="absolute inset-0 opacity-20">
            <svg className="h-full w-full">
              <defs>
                <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                  <path
                    d="M 40 0 L 0 0 0 40"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="0.5"
                    className="text-border"
                  />
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#grid)" />
            </svg>
          </div>

          {/* Hotspots */}
          <div className="absolute inset-0">
            {currentData.map((barangay) => {
              const pos = getPosition(barangay.lat, barangay.lng)
              const isHovered = hoveredBarangay?.id === barangay.id

              if (mapView === "heatmap") {
                return (
                  <div
                    key={barangay.id}
                    className="absolute transform -translate-x-1/2 -translate-y-1/2 transition-all duration-300 cursor-pointer"
                    style={{
                      left: `${pos.x}%`,
                      top: `${pos.y}%`,
                    }}
                    onMouseEnter={() => setHoveredBarangay(barangay)}
                    onMouseLeave={() => setHoveredBarangay(null)}
                  >
                    {/* Glow effect */}
                    <div
                      className="absolute rounded-full blur-md opacity-60"
                      style={{
                        width: barangay.severity.size * 2.5,
                        height: barangay.severity.size * 2.5,
                        backgroundColor: barangay.severity.color,
                        left: "50%",
                        top: "50%",
                        transform: "translate(-50%, -50%)",
                      }}
                    />
                    {/* Core dot */}
                    <div
                      className={`rounded-full transition-transform ${isHovered ? "scale-150" : ""}`}
                      style={{
                        width: barangay.severity.size,
                        height: barangay.severity.size,
                        backgroundColor: barangay.severity.color,
                        boxShadow: `0 0 ${barangay.severity.size}px ${barangay.severity.color}`,
                      }}
                    />
                  </div>
                )
              }

              return (
                <div
                  key={barangay.id}
                  className="absolute transform -translate-x-1/2 -translate-y-1/2 cursor-pointer"
                  style={{
                    left: `${pos.x}%`,
                    top: `${pos.y}%`,
                  }}
                  onMouseEnter={() => setHoveredBarangay(barangay)}
                  onMouseLeave={() => setHoveredBarangay(null)}
                >
                  <MapPin
                    className={`transition-transform ${isHovered ? "scale-150" : ""}`}
                    style={{
                      color: barangay.severity.color,
                      width: 16,
                      height: 16,
                    }}
                    fill={barangay.severity.color}
                  />
                </div>
              )
            })}
          </div>

          {/* Tooltip */}
          {hoveredBarangay && (
            <div
              className="absolute z-50 rounded-lg bg-popover border border-border p-3 shadow-xl pointer-events-none"
              style={{
                left: `${Math.min(getPosition(hoveredBarangay.lat, hoveredBarangay.lng).x + 2, 75)}%`,
                top: `${Math.min(getPosition(hoveredBarangay.lat, hoveredBarangay.lng).y - 5, 80)}%`,
              }}
            >
              <div className="font-semibold text-foreground">{hoveredBarangay.name}</div>
              <div className="mt-1 flex items-center gap-2">
                <div
                  className="h-2 w-2 rounded-full"
                  style={{ backgroundColor: getSeverity(hoveredBarangay.cases).color }}
                />
                <span className="text-sm text-muted-foreground capitalize">
                  {getSeverity(hoveredBarangay.cases).level}
                </span>
              </div>
              <div className="mt-1 text-lg font-bold" style={{ color: getSeverity(hoveredBarangay.cases).color }}>
                {hoveredBarangay.cases} cases
              </div>
            </div>
          )}

          {/* Legend */}
          <div className="absolute bottom-3 left-3 rounded-lg bg-background/80 backdrop-blur-sm border border-border p-2">
            <div className="text-[10px] font-medium text-muted-foreground mb-1.5">Severity</div>
            <div className="flex flex-col gap-1">
              {[
                { level: "Critical", color: "#ef4444", range: ">250" },
                { level: "High", color: "#f97316", range: "151-250" },
                { level: "Medium", color: "#eab308", range: "76-150" },
                { level: "Low", color: "#22c55e", range: "0-75" },
              ].map((item) => (
                <div key={item.level} className="flex items-center gap-2 text-[10px]">
                  <div className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color }} />
                  <span className="text-muted-foreground">{item.level}</span>
                  <span className="text-muted-foreground/60">({item.range})</span>
                </div>
              ))}
            </div>
          </div>

          {/* Hottest Barangay Badge */}
          <div className="absolute top-3 right-3 rounded-lg bg-red-500/10 border border-red-500/30 p-2">
            <div className="text-[10px] text-red-400 font-medium">HOTSPOT</div>
            <div className="text-sm font-bold text-red-400">{stats.hottest.name}</div>
            <div className="text-xs text-red-400/70">{stats.hottest.cases} cases</div>
          </div>
        </div>

        {/* Time Slider Controls */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-foreground">Time Period</span>
            <span className="text-sm text-muted-foreground">
              {weeks[0]} - {weeks[11]}, 2025
            </span>
          </div>

          {/* Slider */}
          <div className="space-y-2">
            <Slider
              value={[selectedWeek]}
              min={0}
              max={11}
              step={1}
              onValueChange={([value]) => setSelectedWeek(value)}
              className="w-full"
            />
            <div className="flex justify-between text-[10px] text-muted-foreground">
              {weeks.map((week, i) => (
                <span
                  key={week}
                  className={`cursor-pointer transition-colors ${i === selectedWeek ? "text-primary font-medium" : "hover:text-foreground"}`}
                  onClick={() => setSelectedWeek(i)}
                >
                  {week.split(" ")[0]}
                </span>
              ))}
            </div>
          </div>

          {/* Playback Controls */}
          <div className="flex items-center justify-center gap-2">
            <Button variant="outline" size="icon" className="h-8 w-8 bg-transparent" onClick={() => setSelectedWeek(0)}>
              <SkipBack className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="h-10 w-10 bg-primary text-primary-foreground hover:bg-primary/90"
              onClick={handlePlayPause}
            >
              {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 ml-0.5" />}
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8 bg-transparent"
              onClick={() => setSelectedWeek(11)}
            >
              <SkipForward className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
