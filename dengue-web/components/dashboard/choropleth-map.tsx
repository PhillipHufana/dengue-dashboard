"use client";

import { useState, useMemo, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Play, Pause, SkipBack, SkipForward } from "lucide-react";

import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import "leaflet/dist/leaflet.css";

import { useChoropleth, useSummary } from "@/lib/query/hooks";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface BarangayForecast {
  name: string;
  forecast: number | null;
  week_start: string;
}


const getColor = (risk: string | null) => {
  switch (risk) {
    case "critical": return "#7f1d1d";
    case "high": return "#ef4444";
    case "medium": return "#f59e0b";
    case "low": return "#10b981";
    default: return "#9ca3af";
  }
};

// Dummy weeks (you can replace later using your API)
const weeks = [
  "Sep 9", "Sep 16", "Sep 23", "Sep 30",
  "Oct 7", "Oct 14", "Oct 21", "Oct 28",
  "Nov 4", "Nov 11", "Nov 18", "Nov 25",
];

// ---------------------------------------------------------------------------
// Component Start
// ---------------------------------------------------------------------------

interface ChoroplethMapProps {
  selectedBarangayId: number | null;
  onBarangaySelect: (barangayId: number | null) => void;
}

export function ChoroplethMap({
  selectedBarangayId,
  onBarangaySelect,
}: ChoroplethMapProps) {

  // ----------------------------------------------------------------------------
  // Local time slider + animation
  // ----------------------------------------------------------------------------
  const [selectedWeek, setSelectedWeek] = useState(11);
  const [isPlaying, setIsPlaying] = useState(false);
  const [mapView, setMapView] = useState<"choropleth" | "hotspots">("choropleth");
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (isPlaying) {
      intervalRef.current = setInterval(() => {
        setSelectedWeek((prev) => (prev >= 11 ? 0 : prev + 1));
      }, 1000);
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isPlaying]);

  // ----------------------------------------------------------------------------
  // Real API Data
  // ----------------------------------------------------------------------------
  const { data: geo, isLoading: loadingGeo } = useChoropleth();
  const { data: summary, isLoading: loadingSummary } = useSummary();

  const barangayForecast = summary?.barangay_latest ?? [];

  // ----------------------------------------------------------------------------
  // Stats (REAL FORECAST DATA from /forecast/summary)
  // ----------------------------------------------------------------------------
    const stats = useMemo(() => {
    const list = (barangayForecast ?? []) as BarangayForecast[];

    if (!list.length) {
      return {
        totalCases: 0,
        critical: 0,
        high: 0,
        medium: 0,
        low: 0,
        hottest: { name: "N/A", forecast: 0 },
      };
    }

    const totalCases = list.reduce(
      (sum: number, b: BarangayForecast) => sum + (b.forecast ?? 0),
      0
    );

    const critical = list.filter(
      (b: BarangayForecast) => (b.forecast ?? 0) > 250
    ).length;

    const high = list.filter(
      (b: BarangayForecast) =>
        (b.forecast ?? 0) > 150 && (b.forecast ?? 0) <= 250
    ).length;

    const medium = list.filter(
      (b: BarangayForecast) =>
        (b.forecast ?? 0) > 75 && (b.forecast ?? 0) <= 150
    ).length;

    const low = list.filter(
      (b: BarangayForecast) => (b.forecast ?? 0) <= 75
    ).length;

    const hottest = list.reduce(
      (max: BarangayForecast, b: BarangayForecast) =>
        (b.forecast ?? 0) > (max.forecast ?? 0) ? b : max,
      list[0]
    );

    return {
      totalCases,
      critical,
      high,
      medium,
      low,
      hottest,
    };
  }, [barangayForecast]);

  // ----------------------------------------------------------------------------
  // GeoJSON Rendering Setup
  // ----------------------------------------------------------------------------
  const style = (feature: any) => ({
    fillColor: getColor(feature.properties.risk_level),
    fillOpacity: 0.7,
    color: "#333",
    weight: 1,
  });

  const onEachFeature = (feature: any, layer: any) => {
    const name = feature.properties.ADM4_EN;
    const risk = feature.properties.risk_level;

    layer.bindTooltip(
      `<strong>${name}</strong><br/>Risk: ${risk || "N/A"}`,
      { sticky: true }
    );

    layer.on("click", () => {
      onBarangaySelect(feature.id === selectedBarangayId ? null : feature.id);
    });
  };

  // ----------------------------------------------------------------------------
  // JSX
  // ----------------------------------------------------------------------------

  return (
    <Card className="bg-card border-border">
      {/* ---------------------------------------------------------------------- */}
      {/* Header */}
      {/* ---------------------------------------------------------------------- */}

      <CardHeader className="p-3 md:pb-3 md:p-6">
        <div className="flex flex-col gap-3">

          {/* Title & View Toggle */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2 flex-wrap">
              <CardTitle className="text-base md:text-lg font-semibold">
                Choropleth Map
              </CardTitle>
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

          {/* Selected Barangay Indicator */}
          {selectedBarangayId && (
            <div className="flex items-center gap-2 p-2 rounded-lg bg-primary/10 border border-primary/30">
              <span className="text-xs md:text-sm text-primary">Selected:</span>
              <Badge variant="default" className="text-[10px] md:text-xs">
                {selectedBarangayId}
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

          {/* Stats Row */}
          {!loadingSummary && (
            <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1 scrollbar-hide">
              <div className="flex-shrink-0 rounded-lg bg-secondary/50 p-2 min-w-[70px] md:min-w-[80px] text-center">
                <div className="text-sm md:text-lg font-bold text-foreground">
                  {stats.totalCases.toLocaleString()}
                </div>
                <div className="text-[9px] md:text-[10px] text-muted-foreground">Total</div>
              </div>

              <div className="flex-shrink-0 rounded-lg bg-red-500/10 p-2 min-w-[60px] text-center">
                <div className="text-sm md:text-lg font-bold text-red-500">
                  {stats.critical}
                </div>
                <div className="text-[9px] text-red-500/70">Critical</div>
              </div>

              <div className="flex-shrink-0 rounded-lg bg-orange-500/10 p-2 min-w-[60px] text-center">
                <div className="text-sm md:text-lg font-bold text-orange-500">
                  {stats.high}
                </div>
                <div className="text-[9px] text-orange-500/70">High</div>
              </div>

              <div className="flex-shrink-0 rounded-lg bg-yellow-500/10 p-2 min-w-[60px] text-center">
                <div className="text-sm md:text-lg font-bold text-yellow-500">
                  {stats.medium}
                </div>
                <div className="text-[9px] text-yellow-500/70">Medium</div>
              </div>

              <div className="flex-shrink-0 rounded-lg bg-green-500/10 p-2 min-w-[60px] text-center">
                <div className="text-sm md:text-lg font-bold text-green-500">
                  {stats.low}
                </div>
                <div className="text-[9px] text-green-500/70">Low</div>
              </div>
            </div>
          )}
        </div>
      </CardHeader>

      {/* ---------------------------------------------------------------------- */}
      {/* MAP + LEGEND + HOTSPOT BOX */}
      {/* ---------------------------------------------------------------------- */}

      <CardContent className="p-3 pt-0 md:p-6 md:pt-0 space-y-3 md:space-y-4">
        <div className="relative h-[300px] md:h-[450px] w-full overflow-hidden rounded-lg border border-border">

          {/* Actual Map */}
          {loadingGeo ? (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              Loading map...
            </div>
          ) : geo ? (
            <MapContainer
              center={[7.1907, 125.4553]}
              zoom={11}
              className="w-full h-full"
              scrollWheelZoom={false}
            >
              <TileLayer
                attribution='&copy; OpenStreetMap'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />

              <GeoJSON
                data={geo}
                style={style}
                onEachFeature={onEachFeature}
              />
            </MapContainer>
          ) : (
            <div className="text-red-500 text-sm p-4">Failed to load map.</div>
          )}

          {/* Hotspot badge */}
          <div className="absolute top-2 right-2 md:top-3 md:right-3 z-[1000] rounded-lg bg-red-500/10 border border-red-500/30 p-1.5 md:p-2 backdrop-blur-sm">
            <div className="text-[8px] md:text-[10px] text-red-500 font-medium">HOTSPOT</div>
            <div className="text-xs md:text-sm font-bold text-red-500 truncate max-w-[80px] md:max-w-none">
              {stats.hottest?.name ?? "N/A"}
            </div>
            <div className="text-[10px] md:text-xs text-red-500/70">
              {stats.hottest?.forecast ?? 0} cases
            </div>
          </div>

          {/* Legend */}
          <div className="absolute bottom-2 left-2 md:bottom-3 md:left-3 z-[1000] rounded-lg bg-background/90 backdrop-blur-sm border border-border p-2 md:p-3">
            <div className="text-[10px] md:text-xs font-medium text-muted-foreground mb-1.5 md:mb-2">
              Severity
            </div>

            <div className="flex flex-col gap-1 md:gap-1.5">
              {[
                { level: "Critical", color: "#7f1d1d" },
                { level: "High", color: "#ef4444" },
                { level: "Medium", color: "#f59e0b" },
                { level: "Low", color: "#10b981" },
              ].map((item) => (
                <div key={item.level} className="flex items-center gap-2 text-[10px] md:text-xs">
                  <div
                    className="h-3 w-3 rounded"
                    style={{ backgroundColor: item.color }}
                  />
                  <span>{item.level}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ------------------------------------------------------------------ */}
        {/* TIME SLIDER CONTROLS */}
        {/* ------------------------------------------------------------------ */}

        <div className="space-y-2 md:space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs md:text-sm font-medium text-foreground">
              Time Period
            </span>
            <span className="text-[10px] md:text-sm text-muted-foreground">
              {weeks[0]} - {weeks[11]}, 2025
            </span>
          </div>

          <Slider
            value={[selectedWeek]}
            min={0}
            max={11}
            step={1}
            onValueChange={([v]) => setSelectedWeek(v)}
          />

          <div className="flex items-center justify-center gap-2">
            <Button
              variant="outline"
              size="icon"
              className="h-7 w-7"
              onClick={() => setSelectedWeek(0)}
            >
              <SkipBack className="h-4 w-4" />
            </Button>

            <Button
              variant="default"
              size="icon"
              className="h-9 w-9"
              onClick={() => setIsPlaying(!isPlaying)}
            >
              {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            </Button>

            <Button
              variant="outline"
              size="icon"
              className="h-7 w-7"
              onClick={() => setSelectedWeek(11)}
            >
              <SkipForward className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
