"use client";

import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import dynamic from "next/dynamic";
const MapContainer = dynamic(() => import("react-leaflet").then((m) => m.MapContainer), { ssr: false });
const TileLayer = dynamic(() => import("react-leaflet").then((m) => m.TileLayer), { ssr: false });
const GeoJSON = dynamic(() => import("react-leaflet").then((m) => m.GeoJSON), { ssr: false });

import "leaflet/dist/leaflet.css";

import { useChoropleth, useRankings } from "@/lib/query/hooks";
import { useDashboardStore } from "@/lib/store/dashboard-store";
import type { ChoroplethFC, RankingRow } from "@/lib/api";

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
    default:
      return "#9ca3af";
  }
};

function formatRange(a: number, b: number, unit: string) {
  const lo = Number.isFinite(a) ? a.toFixed(2) : "-";
  const hi = Number.isFinite(b) ? b.toFixed(2) : "-";
  return `${lo}-${hi} ${unit}`;
}

interface ChoroplethMapProps {
  selectedBarangay: { pretty: string; clean: string } | null;
  onBarangaySelect: (value: { pretty: string; clean: string } | null) => void;
}

type ChoroplethMeta = ChoroplethFC & {
  run_id?: string;
  model_name?: string;
  data_last_updated?: string | null;
  jenks_breaks_incidence?: number[];
  jenks_breaks_cases?: number[];
  jenks_breaks_surge?: number[];
};

type MapFeature = {
  properties: Record<string, unknown>;
};

type MapLayer = {
  bindTooltip: (content: string, options: { sticky: boolean }) => void;
  on: (event: string, handler: () => void) => void;
};

export function ChoroplethMap({ selectedBarangay, onBarangaySelect }: ChoroplethMapProps) {
  const riskMetric = useDashboardStore((s) => s.riskMetric);
  const dataMode = useDashboardStore((s) => s.dataMode);
  const period = useDashboardStore((s) => s.period);
  const runId = useDashboardStore((s) => s.runId);
  const modelName = useDashboardStore((s) => s.modelName);

  const effectiveMetric =
    riskMetric === "action_priority" ? (dataMode === "observed" ? "cases" : "surge") : riskMetric;

  const { data: geo, isLoading: loadingGeo } = useChoropleth(runId, modelName, period, dataMode);
  const { data: rankingData } = useRankings(period, runId, modelName, effectiveMetric, dataMode);
  const geoMeta = geo as ChoroplethMeta | undefined;

  const rankingByName = useMemo(() => {
    const out = new Map<string, RankingRow>();
    for (const row of rankingData?.rankings ?? []) out.set(row.name, row);
    return out;
  }, [rankingData?.rankings]);

  const legend = useMemo(() => {
    const b =
      effectiveMetric === "incidence"
        ? geoMeta?.jenks_breaks_incidence
        : effectiveMetric === "surge"
        ? geoMeta?.jenks_breaks_surge
        : geoMeta?.jenks_breaks_cases;
    if (!Array.isArray(b) || b.length < 6) return null;
    const unit = effectiveMetric === "incidence" ? "/100k" : effectiveMetric === "surge" ? "ratio" : "cases";
    const labels = ["Very Low", "Low", "Medium", "High", "Very High"];
    const classes = ["very_low", "low", "medium", "high", "very_high"] as const;
    return classes.map((cls, i) => ({ cls, label: labels[i], range: formatRange(b[i], b[i + 1], unit) }));
  }, [geoMeta, effectiveMetric]);

  const stats = useMemo(() => {
    if (!geo?.features?.length) {
      return { total: 0, very_high: 0, high: 0, medium: 0, low: 0, very_low: 0, hottestName: null as string | null, hottestValue: -Infinity };
    }
    let total = 0;
    let very_high = 0;
    let high = 0;
    let medium = 0;
    let low = 0;
    let very_low = 0;
    let hottestName: string | null = null;
    let hottestValue = -Infinity;

    for (const f of geo.features as Array<{ properties: Record<string, unknown> }>) {
      const name = String(f.properties.name ?? "");
      const row = rankingByName.get(name);
      const value =
        effectiveMetric === "surge"
          ? Number(row?.surge_score ?? f.properties.forecast_surge_ratio ?? 0)
          : effectiveMetric === "incidence"
          ? Number(row?.total_forecast_incidence_per_100k ?? f.properties.forecast_incidence_per_100k ?? 0)
          : Number(row?.total_forecast_cases ?? row?.total_forecast ?? f.properties.forecast_cases ?? f.properties.latest_forecast ?? 0);
      const cls =
        effectiveMetric === "surge"
          ? String(row?.surge_class ?? f.properties.surge_class ?? "unknown")
          : effectiveMetric === "incidence"
          ? String(row?.burden_class ?? f.properties.burden_class ?? "unknown")
          : String(row?.cases_class ?? f.properties.cases_class ?? "unknown");

      total += value;
      if (value > hottestValue) {
        hottestValue = value;
        hottestName = name;
      }
      if (cls === "very_high") very_high += 1;
      else if (cls === "high") high += 1;
      else if (cls === "medium") medium += 1;
      else if (cls === "low") low += 1;
      else if (cls === "very_low") very_low += 1;
    }

    return { total, very_high, high, medium, low, very_low, hottestName, hottestValue };
  }, [geo, rankingByName, effectiveMetric]);

  const asOfDate = useMemo(() => {
    const raw = geoMeta?.data_last_updated ?? null;
    if (!raw) return "-";
    const d = new Date(raw);
    if (Number.isNaN(d.getTime())) return String(raw);
    return d.toLocaleDateString([], { year: "numeric", month: "short", day: "2-digit" });
  }, [geoMeta?.data_last_updated]);

  const nameToLabel = useMemo(() => {
    if (!geo) return new Map<string, string>();
    return new Map(geo.features.map((f) => [f.properties.name, f.properties.display_name]));
  }, [geo]);

  const style = (feature: MapFeature) => {
    const key = String(feature.properties.name ?? "");
    const row = rankingByName.get(key);
    const level =
      effectiveMetric === "surge"
        ? String(row?.surge_class ?? feature.properties.surge_class ?? "unknown")
        : effectiveMetric === "incidence"
        ? String(row?.burden_class ?? feature.properties.burden_class ?? "unknown")
        : String(row?.cases_class ?? feature.properties.cases_class ?? "unknown");
    const selected = selectedBarangay?.pretty === feature.properties.display_name;
    return {
      fillColor: getColor(level),
      fillOpacity: 0.75,
      color: selected ? "#ffffff" : "#333",
      weight: selected ? 3 : 1,
    };
  };

  const onEachFeature = (feature: MapFeature, layer: MapLayer) => {
    const key = String(feature.properties.name ?? "");
    const row = rankingByName.get(key);
    const label = String(feature.properties.display_name ?? key);
    const level =
      effectiveMetric === "surge"
        ? String(row?.surge_class ?? feature.properties.surge_class ?? "unknown")
        : effectiveMetric === "incidence"
        ? String(row?.burden_class ?? feature.properties.burden_class ?? "unknown")
        : String(row?.cases_class ?? feature.properties.cases_class ?? "unknown");
    const value =
      effectiveMetric === "surge"
        ? Number(row?.surge_score ?? feature.properties.forecast_surge_ratio ?? 0)
        : effectiveMetric === "incidence"
        ? Number(row?.total_forecast_incidence_per_100k ?? feature.properties.forecast_incidence_per_100k ?? 0)
        : Number(row?.total_forecast_cases ?? row?.total_forecast ?? feature.properties.forecast_cases ?? feature.properties.latest_forecast ?? 0);
    const pop = feature.properties.population ? Number(feature.properties.population).toLocaleString() : "-";
    const labelValue = effectiveMetric === "cases" ? value.toLocaleString() : value.toFixed(2);
    const mainLabel =
      effectiveMetric === "surge" ? "Forecast surge ratio" : effectiveMetric === "incidence" ? (dataMode === "observed" ? "Observed /100k" : "Forecast /100k") : (dataMode === "observed" ? "Observed cases" : "Forecast cases");
    const surgeDetail =
      effectiveMetric === "surge"
        ? `<br/>Baseline expected (${period.toUpperCase()}): <strong>${Number(row?.baseline_expected_w ?? feature.properties.baseline_expected_w ?? 0).toFixed(2)}</strong>`
        : "";

    layer.bindTooltip(
      `<strong>${label}</strong><br/>
      Mode: <strong>${dataMode === "observed" ? "Observed (Past W)" : "Forecast (Next W)"}</strong><br/>
      Period: <strong>${period.toUpperCase()}</strong><br/>
      Population: <strong>${pop}</strong><br/>
      Class: <strong>${level}</strong><br/>
      ${mainLabel}: <strong>${labelValue}</strong>${surgeDetail}
      <div style="font-size:11px;color:#aaa;margin-top:4px">Click to view trend</div>`,
      { sticky: true }
    );

    layer.on("click", () => {
      if (selectedBarangay?.clean === key) onBarangaySelect(null);
      else onBarangaySelect({ pretty: label, clean: key });
    });
  };

  return (
    <Card className="bg-card border-border h-full xl:h-[780px] flex flex-col">
      <CardHeader className="p-3 md:p-6">
        <div className="flex flex-col gap-3">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <CardTitle className="text-lg font-semibold">Choropleth Map</CardTitle>
              <Badge variant="outline" className="text-xs">
                {period.toUpperCase()} • As of {asOfDate}
              </Badge>
            </div>
            <Badge variant="secondary" className="text-xs">
              {dataMode === "observed"
                ? effectiveMetric === "cases"
                  ? "Observed Cases (Past W)"
                  : "Observed Incidence (Past W)"
                : effectiveMetric === "cases"
                ? "Forecast Cases (Next W)"
                : effectiveMetric === "incidence"
                ? "Forecast Incidence (Next W)"
                : "Forecast Surge (Next W vs Past 8W)"}
            </Badge>
          </div>
          {selectedBarangay ? (
            <div className="flex items-center gap-2 p-2 rounded-lg bg-primary/10 border border-primary/20 min-w-0">
              <span className="text-primary text-sm">Selected:</span>
              <Badge className="max-w-[52vw] md:max-w-none truncate">{selectedBarangay.pretty}</Badge>
              <Button size="sm" variant="ghost" className="ml-auto h-6" onClick={() => onBarangaySelect(null)}>
                Clear
              </Button>
            </div>
          ) : null}
          {!loadingGeo ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
              {[
                { label: "Total", value: effectiveMetric === "cases" ? stats.total.toLocaleString() : stats.total.toFixed(2) },
                { label: "Very High", value: stats.very_high, color: "text-red-500" },
                { label: "High", value: stats.high, color: "text-orange-500" },
                { label: "Medium", value: stats.medium, color: "text-yellow-500" },
                { label: "Low", value: stats.low, color: "text-emerald-500" },
                { label: "Very Low", value: stats.very_low, color: "text-green-500" },
              ].map((item) => (
                <div key={item.label} className="bg-secondary/50 rounded-lg p-2 min-w-0 text-center">
                  <div className={`text-base md:text-lg font-bold ${item.color ?? ""}`}>{item.value}</div>
                  <div className="text-[11px] text-muted-foreground truncate">{item.label}</div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </CardHeader>

      <CardContent className="p-3 md:p-6 space-y-3 flex-1 min-h-0">
        <div className="relative h-full w-full rounded-lg border overflow-hidden">
          {loadingGeo ? (
            <div className="flex items-center justify-center h-full">Loading map...</div>
          ) : geo ? (
            <MapContainer center={[7.1907, 125.4553]} zoom={11} scrollWheelZoom className="w-full h-full">
              <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" opacity={0.35} />
              <GeoJSON
                key={`${effectiveMetric}-${dataMode}-${period}-${geoMeta?.run_id ?? ""}-${geoMeta?.model_name ?? ""}`}
                data={geo}
                style={style}
                onEachFeature={onEachFeature}
              />
            </MapContainer>
          ) : (
            <div className="text-red-500 p-4">Failed to load map.</div>
          )}

          <div className="absolute top-2 right-2 max-w-[52vw] md:max-w-[280px] bg-red-500/10 border border-red-500/40 p-2 rounded-lg backdrop-blur-sm z-50">
            <div className="text-[10px] text-red-500 font-medium">HOTSPOT</div>
            <div className="text-sm font-bold text-red-500 truncate" title={nameToLabel.get(stats.hottestName ?? "") ?? stats.hottestName ?? "N/A"}>
              {nameToLabel.get(stats.hottestName ?? "") ?? stats.hottestName ?? "-"}
            </div>
            <div className="text-xs text-red-500/70">
              {stats.hottestValue > -Infinity ? stats.hottestValue.toFixed(2) : "-"} {effectiveMetric === "incidence" ? "/100k" : effectiveMetric === "surge" ? "ratio" : "cases"}
            </div>
          </div>

          <div className="absolute bottom-2 left-2 max-w-[56vw] md:max-w-[360px] bg-background/95 border p-1.5 md:p-3 rounded-lg backdrop-blur-sm z-50">
            <div className="text-[9px] md:text-xs font-medium mb-1 md:mb-2 text-muted-foreground">
              {effectiveMetric === "incidence" ? "Incidence classes" : effectiveMetric === "surge" ? "Surge classes" : "Cases classes"}
            </div>
            {legend ? (
              <div className="space-y-0.5 md:space-y-1">
                {legend.map((row) => (
                  <div key={row.cls} className="flex items-center justify-between gap-1.5 md:gap-2 text-[9px] md:text-xs">
                    <div className="flex items-center gap-1 md:gap-2 min-w-0">
                      <div className="h-2 w-2 md:h-3 md:w-3 rounded" style={{ backgroundColor: getColor(row.cls) }} />
                      <span className="truncate">{row.label}</span>
                    </div>
                    <span className="text-muted-foreground tabular-nums text-[8px] md:text-xs">{row.range}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-muted-foreground">Legend unavailable</div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
