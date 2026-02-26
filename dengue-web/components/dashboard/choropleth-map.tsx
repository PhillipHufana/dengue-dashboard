"use client";

import { useState, useMemo, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { Play, Pause, SkipBack, SkipForward } from "lucide-react";
import { cleanName } from "@/lib/api";
import dynamic from "next/dynamic";
const MapContainer = dynamic(() => import("react-leaflet").then(m => m.MapContainer), { ssr: false });
const TileLayer = dynamic(() => import("react-leaflet").then(m => m.TileLayer), { ssr: false });
const GeoJSON = dynamic(() => import("react-leaflet").then(m => m.GeoJSON), { ssr: false });

import "leaflet/dist/leaflet.css";

import { useChoropleth, useSummary } from "@/lib/query/hooks";
import { useDashboardStore } from "@/lib/store/dashboard-store";


// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type JenksClass = "very_low" | "low" | "medium" | "high" | "very_high" | "unknown";
interface BarangayForecast {
  name: string;
  display_name?: string;
  week_start: string;
  forecast: number | null;
  risk_level: JenksClass;
  forecast_cases?: number | null;
  forecast_incidence_per_100k?: number | null;
  risk_level_cases?: JenksClass;
  risk_level_incidence?: JenksClass | null;
  cases_class?: JenksClass;
  burden_class?: JenksClass;
}

function formatRange(a: number, b: number, unit: string) {
  const lo = Number.isFinite(a) ? a.toFixed(2) : "—";
  const hi = Number.isFinite(b) ? b.toFixed(2) : "—";
  return `${lo}–${hi} ${unit}`;
}

const getColor = (level: string | null): string => {
  switch (level) {
    case "very_high":
      return "#7f1d1d";
    case "high":
      return "#ef4444";
    case "medium":
      return "#f59e0b";
    case "low":
      return "#10b981";
    case "very_low":
      return "#34d399";
    case "critical":
      return "#7f1d1d";
    default:
      return "#9ca3af";
  }
};

const weeks = ["Sep 9","Sep 16","Sep 23","Sep 30","Oct 7","Oct 14","Oct 21","Oct 28","Nov 4","Nov 11","Nov 18","Nov 25"];

interface ChoroplethMapProps {
  selectedBarangay: { pretty: string; clean: string } | null;
  onBarangaySelect: (value: { pretty: string; clean: string } | null) => void;
}

export function ChoroplethMap({ selectedBarangay, onBarangaySelect }: ChoroplethMapProps) {
  const [selectedWeek, setSelectedWeek] = useState(11);
  const [isPlaying, setIsPlaying] = useState(false);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const riskMetric = useDashboardStore((s) => s.riskMetric);
  const setRiskMetric = useDashboardStore((s) => s.setRiskMetric);

  // ✅ global sync period
  const period = useDashboardStore((s) => s.period);

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

  const runId = useDashboardStore((s) => s.runId);
  const modelName = useDashboardStore((s) => s.modelName);
  

  // ✅ pass period to both
  const { data: geo, isLoading: loadingGeo } = useChoropleth(runId, modelName, period);
  const { data: summary, isLoading: loadingSummary } = useSummary(runId, modelName, period);


  const legend = useMemo(() => {
  const b =
    riskMetric === "incidence"
      ? (geo as any)?.jenks_breaks_incidence
      : (geo as any)?.jenks_breaks_cases;

  if (!Array.isArray(b) || b.length < 6) return null;

  const unit = riskMetric === "incidence" ? "/100k" : "cases";
  const labels = ["Very Low", "Low", "Medium", "High", "Very High"];
  const classes = ["very_low", "low", "medium", "high", "very_high"] as const;

  return classes.map((cls, i) => ({
    cls,
    label: labels[i],
    range: formatRange(b[i], b[i + 1], unit),
  }));
}, [geo, riskMetric]);

  const barangayForecast: BarangayForecast[] = summary?.barangay_latest ?? [];
  const forecastByName = useMemo(() => {
    const m = new Map<string, BarangayForecast>();
    for (const b of barangayForecast) m.set(cleanName(b.name), b);
    return m;
  }, [barangayForecast]);
  const stats = useMemo(() => {
    if (!geo?.features?.length) {
      return {
        total: 0,
        very_high: 0,
        high: 0,
        medium: 0,
        low: 0,
        very_low: 0,
        hottestName: null as string | null,
        hottestValue: -Infinity as number,
      };
    }
    let hottestName: string | null = null;
    let hottestValue = -Infinity;
    let total = 0;
    let very_high = 0;
    let high = 0;
    let medium = 0;
    let low = 0;
    let very_low = 0;

    for (const f of geo.features as any[]) {
      const props = f.properties;

      if (riskMetric === "cases") {
        // Keep your old case totals if you want (or migrate later)
        const v = Number(props.forecast_cases ?? props.latest_forecast ?? 0);
        total += v;

        if (v > hottestValue) {
          hottestValue = v;
          hottestName = props.name ?? null;
        }

        const cls = props.cases_class ?? "unknown";
        if (cls === "very_high") very_high += 1;
        else if (cls === "high") high += 1;
        else if (cls === "medium") medium += 1;
        else if (cls === "low") low += 1;
        else if (cls === "very_low") very_low += 1;

        const r = props.risk_level_cases ?? props.risk_level ?? "unknown";
        // If you still use old 4-class for cases, you can keep old UI labels for cases
        // (but you asked for burden everywhere; we can later switch cases to Jenks too)
      } else {
        const inc = Number(props.forecast_incidence_per_100k ?? 0);
        total += inc;

        if (inc > hottestValue) {
          hottestValue = inc;
          hottestName = props.name ?? null;
        }

        const cls = props.burden_class ?? props.risk_level_incidence ?? "unknown";
        if (cls === "very_high") very_high += 1;
        else if (cls === "high") high += 1;
        else if (cls === "medium") medium += 1;
        else if (cls === "low") low += 1;
        else if (cls === "very_low") very_low += 1;
      }
    }

    return { total, very_high, high, medium, low, very_low, hottestName, hottestValue };
  }, [geo, riskMetric]);

  const nameToLabel = useMemo(() => {
    if (!geo) return new Map<string, string>();
    return new Map(geo.features.map((f) => [f.properties.name, f.properties.display_name]));
  }, [geo]);

  const style = (feature: any) => {
    const label = feature.properties.display_name;
    const selected = selectedBarangay?.pretty === label;
    const level =
      riskMetric === "cases"
        ? (feature.properties.cases_class ?? "unknown")
        : (feature.properties.burden_class ?? "unknown");
    return {
      fillColor: getColor(level),
      fillOpacity: 0.75,
      color: selected ? "#ffffff" : "#333",
      weight: selected ? 3 : 1,
    };
  };

  const onEachFeature = (feature: any, layer: any) => {
    const key = feature.properties.name;
    const label = feature.properties.display_name;
    const match = forecastByName.get(cleanName(key));

    const level =
      riskMetric === "cases"
        ? (feature.properties.cases_class ?? "unknown")
        : (feature.properties.burden_class ?? "unknown");

    const forecastValue =
      riskMetric === "cases"
        ? Number(match?.forecast_cases ?? match?.forecast ?? feature.properties.latest_forecast ?? 0)
        : Number(match?.forecast_incidence_per_100k ?? feature.properties.forecast_incidence_per_100k ?? 0);

    const forecastLabel = riskMetric === "cases" ? "Forecast cases" : "Forecast /100k";

    const pop = feature.properties.population;
    const popLabel = pop ? Number(pop).toLocaleString() : "—";

    const forecastDisplay =
      riskMetric === "cases"
        ? Number(forecastValue).toLocaleString()
        : Number(forecastValue).toFixed(2);

    layer.bindTooltip(
      `
        <strong>${label}</strong><br/>
        Period: <strong>${period.toUpperCase()}</strong><br/>
        Population: <strong>${popLabel}</strong><br/>
        Class: <strong>${level}</strong><br/>
        ${forecastLabel}: <strong>${forecastDisplay}</strong>
        <div style="font-size:11px;color:#aaa;margin-top:4px">Click to view trend</div>
      `,
      { sticky: true }
    );

    layer.on("click", () => {
      const pretty = feature.properties.display_name;
      const clean = feature.properties.name;
      if (selectedBarangay?.clean === clean) onBarangaySelect(null);
      else onBarangaySelect({ pretty, clean });
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
              <CardTitle className="text-lg font-semibold">Choropleth Map</CardTitle>
              <Badge variant="outline" className="text-xs">
                {/* ✅ show selected global period */}
                {period.toUpperCase()} • Week of {weeks[selectedWeek]}
              </Badge>
            </div>

            <Badge variant="secondary" className="text-xs">
              {riskMetric === "cases" ? "Cases" : "Incidence (/100k)"}
            </Badge>
          </div>
          {selectedBarangay && (
            <div className="flex items-center gap-2 p-2 rounded-lg bg-primary/10 border border-primary/20">
              <span className="text-primary text-sm">Selected:</span>
              <Badge>{selectedBarangay.pretty}</Badge>
              <Button size="sm" variant="ghost" className="ml-auto h-6" onClick={() => onBarangaySelect(null)}>
                Clear
              </Button>
            </div>
          )}

          {!loadingSummary && (
            <div className="flex gap-2 overflow-x-auto pb-1">
              {(
                riskMetric === "incidence"
                  ? [
                      { label: "Total", value: stats.total.toFixed(2) },
                      { label: "Very High", value: stats.very_high, color: "text-red-500" },
                      { label: "High", value: stats.high, color: "text-orange-500" },
                      { label: "Medium", value: stats.medium, color: "text-yellow-500" },
                      { label: "Low", value: stats.low, color: "text-emerald-500" },
                      { label: "Very Low", value: stats.very_low, color: "text-green-500" },
                    ]
                  : [
                      { label: "Total", value: stats.total.toLocaleString() },
                      { label: "Very High", value: stats.very_high, color: "text-red-500" },
                      { label: "High", value: stats.high, color: "text-orange-500" },
                      { label: "Medium", value: stats.medium, color: "text-yellow-500" },
                      { label: "Low", value: stats.low, color: "text-emerald-500" },
                      { label: "Very Low", value: stats.very_low, color: "text-green-500" },
                    ]
              ).map((item) => (
                <div
                  key={item.label}
                  className="shrink-0 bg-secondary/50 rounded-lg p-2 min-w-[60px] text-center"
                >
                  <div className={`text-lg font-bold ${item.color ?? ""}`}>{item.value}</div>
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
            <div className="flex items-center justify-center h-full">Loading map...</div>
          ) : geo ? (
            <MapContainer center={[7.1907, 125.4553]} zoom={11} scrollWheelZoom className="w-full h-full">
              <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" opacity={0.35} />
              <GeoJSON
                key={`${riskMetric}-${period}-${(geo as any)?.run_id ?? ""}-${(geo as any)?.model_name ?? ""}`}
                data={geo}
                style={style}
                onEachFeature={onEachFeature}
              />
            </MapContainer>
          ) : (
            <div className="text-red-500 p-4">Failed to load map.</div>
          )}

          <div className="absolute top-2 right-2 bg-red-500/10 border border-red-500/40 p-2 rounded-lg backdrop-blur-sm z-50">
            <div className="text-[10px] text-red-500 font-medium">HOTSPOT</div>
            <div className="text-sm font-bold text-red-500">
              {nameToLabel.get(stats.hottestName ?? "") ?? stats.hottestName ?? "—"}
            </div>
            <div className="text-xs text-red-500/70">
              {stats.hottestValue > -Infinity ? stats.hottestValue.toFixed(2) : "—"}{" "}
              {riskMetric === "incidence" ? "/100k" : "cases"}
            </div>
          </div>
          <div className="absolute bottom-2 left-2 bg-background/95 border p-3 rounded-lg backdrop-blur-sm z-50">
          <div className="text-xs font-medium mb-2 text-muted-foreground">
            {riskMetric === "incidence" ? "Incidence classes" : "Cases classes"}
          </div>

          {legend ? (
            <div className="space-y-1">
              {legend.map((row) => (
                <div key={row.cls} className="flex items-center justify-between gap-3 text-xs">
                  <div className="flex items-center gap-2">
                    <div className="h-3 w-3 rounded" style={{ backgroundColor: getColor(row.cls) }} />
                    <span>{row.label}</span>
                  </div>
                  <span className="text-muted-foreground tabular-nums">{row.range}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-muted-foreground">Legend unavailable</div>
          )}
        </div>
        </div>

        {/* Slider controls remain local (week animation) */}
        <div className="space-y-3">
          <div className="flex justify-between">
            <span className="text-sm font-medium">Time Period</span>
            <span className="text-xs text-muted-foreground">
              {weeks[0]} – {weeks[11]}, 2025
            </span>
          </div>

          <Slider value={[selectedWeek]} min={0} max={11} step={1} onValueChange={([v]) => setSelectedWeek(v)} />

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