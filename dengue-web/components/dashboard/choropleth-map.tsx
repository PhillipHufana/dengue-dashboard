"use client";

import { useState, useMemo, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Play, Pause, SkipBack, SkipForward } from "lucide-react";

import dynamic from "next/dynamic";
const MapContainer = dynamic(() => import("react-leaflet").then(m => m.MapContainer), { ssr: false });
const TileLayer = dynamic(() => import("react-leaflet").then(m => m.TileLayer), { ssr: false });
const GeoJSON = dynamic(() => import("react-leaflet").then(m => m.GeoJSON), { ssr: false });

import "leaflet/dist/leaflet.css";

import { useChoropleth, useSummary } from "@/lib/query/hooks";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export function cleanName(name: string): string {
  if (!name) return "";

  let x = name.toLowerCase().trim();

  // remove accents
  x = x.normalize("NFD").replace(/[\u0300-\u036f]/g, "");

  // remove (pob.) or any parentheses
  x = x.replace(/\(.*?\)/g, "");

  // convert hyphens to spaces
  x = x.replace(/-/g, " ");

  // remove punctuation
  x = x.replace(/[^a-z0-9 ]/g, "");

  // collapse multiple spaces
  x = x.replace(/\s+/g, " ").trim();

  return x;
}


interface BarangayForecast {
  name: string;
  forecast: number | null;
  week_start: string;
  risk_level: "low" | "medium" | "high" | "critical" | "unknown";
}

// ---------------------------------------------------------------------------
// Risk → Color
// ---------------------------------------------------------------------------

const getColor = (risk: string | null): string => {
  switch (risk) {
    case "critical":
      return "#7f1d1d";
    case "high":
      return "#ef4444";
    case "medium":
      return "#f59e0b";
    case "low":
      return "#10b981";
    default:
      return "#9ca3af";
  }
};

// Dummy slider weeks (replace later with API if needed)
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
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface ChoroplethMapProps {
  selectedBarangay: { pretty: string; clean: string } | null;
  onBarangaySelect: (
    value: { pretty: string; clean: string } | null
  ) => void;
}



export function ChoroplethMap({
  selectedBarangay,
  onBarangaySelect,
}: ChoroplethMapProps) {
  // Animation
  const [selectedWeek, setSelectedWeek] = useState(11);
  const [isPlaying, setIsPlaying] = useState(false);
  const [mapView, setMapView] = useState<"choropleth" | "hotspots">("choropleth");
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (isPlaying) {
      intervalRef.current = setInterval(() => {
        setSelectedWeek((prev) => (prev >= 11 ? 0 : prev + 1));
      }, 900);
    } else if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isPlaying]);

  // API Data
  const { data: geo, isLoading: loadingGeo } = useChoropleth();
  const { data: summary, isLoading: loadingSummary } = useSummary();

  const barangayForecast: BarangayForecast[] = summary?.barangay_latest ?? [];

  // ---------------------------------------------------------------------------
  // Stats — backend-driven risk counts
  // ---------------------------------------------------------------------------

  const stats = useMemo(() => {
    if (!barangayForecast.length) {
      return {
        totalCases: 0,
        critical: 0,
        high: 0,
        medium: 0,
        low: 0,
        hottest: { name: "N/A", forecast: 0 },
      };
    }

    return {
      totalCases: barangayForecast.reduce((sum, b) => sum + (b.forecast ?? 0), 0),

      critical: barangayForecast.filter((b) => b.risk_level === "critical").length,
      high: barangayForecast.filter((b) => b.risk_level === "high").length,
      medium: barangayForecast.filter((b) => b.risk_level === "medium").length,
      low: barangayForecast.filter((b) => b.risk_level === "low").length,

      hottest: barangayForecast.reduce((max, b) =>
        (b.forecast ?? 0) > (max.forecast ?? 0) ? b : max
      ),
    };
  }, [barangayForecast]);

  // ---------------------------------------------------------------------------
  // GeoJSON Styling + Tooltip
  // ---------------------------------------------------------------------------

  const style = (feature: any) => {
    const name = feature.properties.ADM4_EN;
    const selected = selectedBarangay?.pretty === name;

    return {
      fillColor: getColor(feature.properties.risk_level),
      fillOpacity: 0.75,
      color: selected ? "#ffffff" : "#333",
      weight: selected ? 3 : 1,
    };
  };


  const onEachFeature = (feature: any, layer: any) => {
    const name = feature.properties.ADM4_EN;

    const match = barangayForecast.find(
      (bg) => cleanName(bg.name) === cleanName(name)
    );

    const risk = match?.risk_level ?? "unknown";
    const forecast = match?.forecast ?? 0;

    layer.bindTooltip(
      `
        <strong>${name}</strong><br/>
        Risk: <strong>${risk}</strong><br/>
        Forecast: <strong>${forecast.toFixed(2)}</strong><br/>
        <span style="font-size:11px;color:#aaa">Click to view trend</span>
      `,
      { sticky: true }
    );

    layer.on("click", () => {
      const pretty = feature.properties.ADM4_EN;
      const clean = cleanName(pretty);

      if (selectedBarangay?.clean === clean) {
        onBarangaySelect(null);
      } else {
        onBarangaySelect({ pretty, clean });
      }
    });



  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <Card className="bg-card border-border">
      <CardHeader className="p-3 md:p-6">
        <div className="flex flex-col gap-3">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <CardTitle className="text-lg font-semibold">
                Choropleth Map
              </CardTitle>
              <Badge variant="outline" className="text-xs">
                Week of {weeks[selectedWeek]}
              </Badge>
            </div>

            <div className="flex gap-2">
              <Button
                variant={mapView === "choropleth" ? "default" : "outline"}
                size="sm"
                onClick={() => setMapView("choropleth")}
              >
                Choropleth
              </Button>

              <Button
                variant={mapView === "hotspots" ? "default" : "outline"}
                size="sm"
                onClick={() => setMapView("hotspots")}
              >
                Hotspots
              </Button>
            </div>
          </div>

          {selectedBarangay && (
            <div className="flex items-center gap-2 p-2 rounded-lg bg-primary/10 border border-primary/20">
              <span className="text-primary text-sm">Selected:</span>
              <Badge>{selectedBarangay.pretty}</Badge>
              <Button
                size="sm"
                variant="ghost"
                className="ml-auto h-6"
                onClick={() => onBarangaySelect(null)}
              >
                Clear
              </Button>
            </div>
          )}

          {!loadingSummary && (
            <div className="flex gap-2 overflow-x-auto pb-1">
              {[
                { label: "Total", value: stats.totalCases.toLocaleString() },
                { label: "Critical", value: stats.critical, color: "text-red-500" },
                { label: "High", value: stats.high, color: "text-orange-500" },
                { label: "Medium", value: stats.medium, color: "text-yellow-500" },
                { label: "Low", value: stats.low, color: "text-green-500" },
              ].map((item) => (
                <div
                  key={item.label}
                  className="shrink-0 bg-secondary/50 rounded-lg p-2 min-w-[60px] text-center"
                >
                  <div className={`text-lg font-bold ${item.color ?? ""}`}>
                    {item.value}
                  </div>
                  <div className="text-xs text-muted-foreground">{item.label}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className="p-3 md:p-6 space-y-3">
        <div className="relative h-[300px] md:h-[450px] w-full rounded-lg border overflow-hidden">
          {loadingGeo ? (
            <div className="flex items-center justify-center h-full">
              Loading map...
            </div>
          ) : geo ? (
            <MapContainer
              center={[7.1907, 125.4553]}
              zoom={11}
              scrollWheelZoom={true}
              className="w-full h-full"
            >
              <TileLayer
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                opacity={0.35}
              />

              <GeoJSON data={geo} style={style} onEachFeature={onEachFeature} />
            </MapContainer>
          ) : (
            <div className="text-red-500 p-4">Failed to load map.</div>
          )}

          {/* Hotspot Widget */}
          <div className="absolute top-2 right-2 bg-red-500/10 border border-red-500/40 p-2 rounded-lg backdrop-blur-sm z-50">
            <div className="text-[10px] text-red-500 font-medium">HOTSPOT</div>
            <div className="text-sm font-bold text-red-500">
              {stats.hottest?.name}
            </div>
            <div className="text-xs text-red-500/70">
              {stats.hottest?.forecast?.toFixed(2)} cases
            </div>
          </div>

          {/* Legend */}
          <div className="absolute bottom-2 left-2 bg-background/95 border p-3 rounded-lg backdrop-blur-sm z-50">
            <div className="text-xs font-medium mb-2 text-muted-foreground">
              Severity
            </div>
            {[
              { label: "Critical", color: "#7f1d1d" },
              { label: "High", color: "#ef4444" },
              { label: "Medium", color: "#f59e0b" },
              { label: "Low", color: "#10b981" },
            ].map((item) => (
              <div key={item.label} className="flex items-center gap-2 text-xs">
                <div
                  className="h-3 w-3 rounded"
                  style={{ backgroundColor: item.color }}
                />
                {item.label}
              </div>
            ))}
          </div>
        </div>

        {/* Slider Controls */}
        <div className="space-y-3">
          <div className="flex justify-between">
            <span className="text-sm font-medium">Time Period</span>
            <span className="text-xs text-muted-foreground">
              {weeks[0]} – {weeks[11]}, 2025
            </span>
          </div>

          <Slider
            value={[selectedWeek]}
            min={0}
            max={11}
            step={1}
            onValueChange={([v]) => setSelectedWeek(v)}
          />

          <div className="flex justify-center gap-2">
            <Button size="icon" variant="outline" onClick={() => setSelectedWeek(0)}>
              <SkipBack className="h-4 w-4" />
            </Button>

            <Button size="icon" onClick={() => setIsPlaying(!isPlaying)}>
              {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            </Button>

            <Button size="icon" variant="outline" onClick={() => setSelectedWeek(11)}>
              <SkipForward className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
