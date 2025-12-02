"use client"

import { useState, useMemo, useEffect, useRef } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"
import { Play, Pause, SkipBack, SkipForward } from "lucide-react"
import { LeafletMapClient, barangays, getSeverity } from "./leaflet-map-client"

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

interface ChoroplethMapProps {
  selectedBarangayId: number | null
  onBarangaySelect: (barangayId: number | null) => void
}

export function ChoroplethMap({ selectedBarangayId, onBarangaySelect }: ChoroplethMapProps) {
  const [selectedWeek, setSelectedWeek] = useState(11)
  const [isPlaying, setIsPlaying] = useState(false)
  const [mapView, setMapView] = useState<"choropleth" | "hotspots">("choropleth")
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    if (isPlaying) {
      intervalRef.current = setInterval(() => {
        setSelectedWeek((prev) => (prev >= 11 ? 0 : prev + 1))
      }, 1000)
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [isPlaying])

  const stats = useMemo(() => {
    const currentData = barangays.map((b) => ({
      ...b,
      cases: b.weeklyData[selectedWeek],
      severity: getSeverity(b.weeklyData[selectedWeek]),
    }))
    return {
      totalCases: currentData.reduce((acc, b) => acc + b.cases, 0),
      critical: currentData.filter((b) => b.severity.level === "critical").length,
      high: currentData.filter((b) => b.severity.level === "high").length,
      medium: currentData.filter((b) => b.severity.level === "medium").length,
      low: currentData.filter((b) => b.severity.level === "low").length,
      hottest: currentData.reduce((max, b) => (b.cases > max.cases ? b : max), currentData[0]),
    }
  }, [selectedWeek])

  const selectedBarangay = selectedBarangayId ? barangays.find((b) => b.id === selectedBarangayId) : null

  return (
    <Card className="bg-card border-border">
      <CardHeader className="p-3 md:pb-3 md:p-6">
        <div className="flex flex-col gap-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2 flex-wrap">
              <CardTitle className="text-base md:text-lg font-semibold">Choropleth Map</CardTitle>
              <Badge variant="outline" className="text-[10px] md:text-xs">
                Week of {weeks[selectedWeek]}
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant={mapView === "choropleth" ? "default" : "outline"}
                size="sm"
                onClick={() => setMapView("choropleth")}
                className="h-7 md:h-8 text-[10px] md:text-xs px-2 md:px-3"
              >
                Choropleth
              </Button>
              <Button
                variant={mapView === "hotspots" ? "default" : "outline"}
                size="sm"
                onClick={() => setMapView("hotspots")}
                className="h-7 md:h-8 text-[10px] md:text-xs px-2 md:px-3"
              >
                Hotspots
              </Button>
            </div>
          </div>

          {selectedBarangay && (
            <div className="flex items-center gap-2 p-2 rounded-lg bg-primary/10 border border-primary/30">
              <span className="text-xs md:text-sm text-primary">Selected:</span>
              <Badge variant="default" className="text-[10px] md:text-xs">
                {selectedBarangay.name}
              </Badge>
              <Button
                variant="ghost"
                size="sm"
                className="h-5 md:h-6 text-[10px] md:text-xs ml-auto"
                onClick={() => onBarangaySelect(null)}
              >
                Clear
              </Button>
            </div>
          )}

          <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1 scrollbar-hide">
            <div className="flex-shrink-0 rounded-lg bg-secondary/50 p-2 min-w-[70px] md:min-w-[80px] text-center">
              <div className="text-sm md:text-lg font-bold text-foreground">{stats.totalCases.toLocaleString()}</div>
              <div className="text-[9px] md:text-[10px] text-muted-foreground">Total</div>
            </div>
            <div className="flex-shrink-0 rounded-lg bg-red-500/10 p-2 min-w-[60px] md:min-w-[70px] text-center">
              <div className="text-sm md:text-lg font-bold text-red-500">{stats.critical}</div>
              <div className="text-[9px] md:text-[10px] text-red-500/70">Critical</div>
            </div>
            <div className="flex-shrink-0 rounded-lg bg-orange-500/10 p-2 min-w-[60px] md:min-w-[70px] text-center">
              <div className="text-sm md:text-lg font-bold text-orange-500">{stats.high}</div>
              <div className="text-[9px] md:text-[10px] text-orange-500/70">High</div>
            </div>
            <div className="flex-shrink-0 rounded-lg bg-yellow-500/10 p-2 min-w-[60px] md:min-w-[70px] text-center">
              <div className="text-sm md:text-lg font-bold text-yellow-500">{stats.medium}</div>
              <div className="text-[9px] md:text-[10px] text-yellow-500/70">Medium</div>
            </div>
            <div className="flex-shrink-0 rounded-lg bg-green-500/10 p-2 min-w-[60px] md:min-w-[70px] text-center">
              <div className="text-sm md:text-lg font-bold text-green-500">{stats.low}</div>
              <div className="text-[9px] md:text-[10px] text-green-500/70">Low</div>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-3 pt-0 md:p-6 md:pt-0 space-y-3 md:space-y-4">
        <div className="relative h-[300px] md:h-[450px] w-full overflow-hidden rounded-lg border border-border">
          <LeafletMapClient
            selectedWeek={selectedWeek}
            mapView={mapView}
            selectedBarangayId={selectedBarangayId}
            onBarangaySelect={onBarangaySelect}
          />

          <div className="absolute bottom-2 left-2 md:bottom-3 md:left-3 z-[1000] rounded-lg bg-background/90 backdrop-blur-sm border border-border p-2 md:p-3">
            <div className="text-[10px] md:text-xs font-medium text-muted-foreground mb-1.5 md:mb-2">Severity</div>
            <div className="flex flex-col gap-1 md:gap-1.5">
              {[
                { level: "Critical", color: "#dc2626", range: ">250" },
                { level: "High", color: "#ea580c", range: "151-250" },
                { level: "Medium", color: "#ca8a04", range: "76-150" },
                { level: "Low", color: "#16a34a", range: "0-75" },
              ].map((item) => (
                <div key={item.level} className="flex items-center gap-1.5 md:gap-2 text-[10px] md:text-xs">
                  <div className="h-2.5 w-2.5 md:h-3 md:w-3 rounded" style={{ backgroundColor: item.color }} />
                  <span className="text-foreground">{item.level}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="absolute top-2 right-2 md:top-3 md:right-3 z-[1000] rounded-lg bg-red-500/10 border border-red-500/30 p-1.5 md:p-2 backdrop-blur-sm">
            <div className="text-[8px] md:text-[10px] text-red-500 font-medium">HOTSPOT</div>
            <div className="text-xs md:text-sm font-bold text-red-500 truncate max-w-[80px] md:max-w-none">
              {stats.hottest.name}
            </div>
            <div className="text-[10px] md:text-xs text-red-500/70">{stats.hottest.cases} cases</div>
          </div>
        </div>

        {/* Time Slider Controls */}
        <div className="space-y-2 md:space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs md:text-sm font-medium text-foreground">Time Period</span>
            <span className="text-[10px] md:text-sm text-muted-foreground">
              {weeks[0]} - {weeks[11]}, 2025
            </span>
          </div>

          <div className="space-y-1.5 md:space-y-2">
            <Slider
              value={[selectedWeek]}
              min={0}
              max={11}
              step={1}
              onValueChange={([value]) => setSelectedWeek(value)}
              className="w-full"
            />
            <div className="hidden sm:flex justify-between text-[9px] md:text-[10px] text-muted-foreground">
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

          <div className="flex items-center justify-center gap-1.5 md:gap-2">
            <Button
              variant="outline"
              size="icon"
              className="h-7 w-7 md:h-8 md:w-8 bg-transparent"
              onClick={() => setSelectedWeek(0)}
            >
              <SkipBack className="h-3 w-3 md:h-4 md:w-4" />
            </Button>
            <Button
              variant="default"
              size="icon"
              className="h-9 w-9 md:h-10 md:w-10"
              onClick={() => setIsPlaying(!isPlaying)}
            >
              {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 ml-0.5" />}
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="h-7 w-7 md:h-8 md:w-8 bg-transparent"
              onClick={() => setSelectedWeek(11)}
            >
              <SkipForward className="h-3 w-3 md:h-4 md:w-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
