"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import dynamic from "next/dynamic";
const MapContainer = dynamic(() => import("react-leaflet").then((m) => m.MapContainer), { ssr: false });
const TileLayer = dynamic(() => import("react-leaflet").then((m) => m.TileLayer), { ssr: false });
const GeoJSON = dynamic(() => import("react-leaflet").then((m) => m.GeoJSON), { ssr: false });
const Marker = dynamic(() => import("react-leaflet").then((m) => m.Marker), { ssr: false });
const MapFocusController = dynamic(() => import("./map-focus-controller").then((m) => m.MapFocusController), { ssr: false });

import "leaflet/dist/leaflet.css";
import { divIcon } from "leaflet";
import type { Feature, Geometry, MultiPolygon, Polygon } from "geojson";

import { useActionPriority, useChoropleth, useRankings } from "@/lib/query/hooks";
import { useDashboardStore } from "@/lib/store/dashboard-store";
import type { ActionPriorityResponse, ChoroplethFC, ChoroplethFeatureProps, RankingRow } from "@/lib/api";
import { formatCases, formatRate, formatSurgeX } from "@/lib/number-format";
import { formatDateRange, humanizeClass, humanizeName } from "@/lib/display-text";

const getColor = (level: string | null): string => {
  switch (level) {
    case "very_high":
      return "#F93716";
    case "high":
      return "#EF6C00";
    case "medium":
      return "#FFB74D";
    case "low":
      return "#3085BE";
    case "very_low":
      return "#69BCE8";
    default:
      return "#9ca3af";
  }
};

function formatRange(a: number, b: number, unit: string, metric: string) {
  const lo = Number.isFinite(a) ? a : 0;
  const hi = Number.isFinite(b) ? b : 0;
  if (metric === "cases") return `${formatCases(lo)}-${formatCases(hi)} ${unit}`;
  if (metric === "surge") return `${formatRate(lo)}-${formatRate(hi)} ${unit}`;
  return `${formatRate(lo)}-${formatRate(hi)} ${unit}`;
}

interface ChoroplethMapProps {
  selectedBarangay: { pretty: string; clean: string } | null;
  onBarangaySelect: (value: { pretty: string; clean: string } | null) => void;
  focusToken?: number;
}

type ChoroplethMeta = ChoroplethFC & {
  run_id?: string;
  model_name?: string;
  data_last_updated?: string | null;
  period_start_week?: string | null;
  period_end_week?: string | null;
  jenks_breaks_incidence?: number[];
  jenks_breaks_cases?: number[];
  jenks_breaks_surge?: number[];
};

type MapFeature = Feature<Geometry, ChoroplethFeatureProps>;

type MapLayer = {
  bindTooltip: (content: string, options: { sticky: boolean }) => void;
  on: (event: string, handler: () => void) => void;
};

function featureCentroid(feature: MapFeature): [number, number] | null {
  const geometry = feature.geometry;
  if (!geometry) return null;
  if (geometry.type === "GeometryCollection") return null;

  const geometryWithCoords = geometry as Polygon | MultiPolygon;
  if (!("coordinates" in geometryWithCoords)) return null;

  const points: Array<[number, number]> = [];
  const collect = (value: unknown) => {
    if (!Array.isArray(value)) return;
    if (typeof value[0] === "number" && typeof value[1] === "number") {
      points.push([Number(value[1]), Number(value[0])]);
      return;
    }
    for (const child of value) collect(child);
  };

  collect(geometryWithCoords.coordinates);
  if (!points.length) return null;

  const [latSum, lngSum] = points.reduce(
    (acc, [lat, lng]) => [acc[0] + lat, acc[1] + lng],
    [0, 0],
  );
  return [latSum / points.length, lngSum / points.length];
}

export function ChoroplethMap({ selectedBarangay, onBarangaySelect, focusToken = 0 }: ChoroplethMapProps) {
  const riskMetric = useDashboardStore((s) => s.riskMetric);
  const dataMode = useDashboardStore((s) => s.dataMode);
  const period = useDashboardStore((s) => s.period);
  const runId = useDashboardStore((s) => s.runId);
  const modelName = useDashboardStore((s) => s.modelName);
  const isForecastMode = dataMode === "forecast";
  const useAction = isForecastMode && riskMetric === "action_priority";
  const effectiveMetric = useAction ? "surge" : riskMetric;

  const { data: geo, isLoading: loadingGeo } = useChoropleth(runId, modelName, period, dataMode);
  const { data: rankingData } = useRankings(period, runId, modelName, effectiveMetric, dataMode);
  const actionQuery = useActionPriority(period, runId, modelName, dataMode, useAction);
  const geoMeta = geo as ChoroplethMeta | undefined;
  const mapLoading = loadingGeo || (useAction && actionQuery.isLoading);
  const [showMapLabels, setShowMapLabels] = useState(false);

  useEffect(() => {
    const update = () => {
      const width = window.innerWidth;
      setShowMapLabels(width >= 1280 || (dataMode === "observed" && width < 768));
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, [dataMode]);

  const rankingByName = useMemo(() => {
    const out = new Map<string, RankingRow>();
    const rows = useAction
      ? ((actionQuery.data as ActionPriorityResponse | undefined)?.rows ?? [])
      : (rankingData?.rankings ?? []);
    for (const row of rows) out.set(row.name, row);
    return out;
  }, [useAction, actionQuery.data, rankingData?.rankings]);

  const legend = useMemo(() => {
    const b =
      effectiveMetric === "incidence"
        ? geoMeta?.jenks_breaks_incidence
        : effectiveMetric === "surge"
        ? (rankingData?.jenks_breaks_surge ?? geoMeta?.jenks_breaks_surge)
        : geoMeta?.jenks_breaks_cases;
    if (!Array.isArray(b) || b.length < 6) return null;
    const unit = effectiveMetric === "incidence" ? "/100k" : effectiveMetric === "surge" ? "x" : "cases";
    const labels = ["Very Low", "Low", "Medium", "High", "Very High"];
    const classes = ["very_low", "low", "medium", "high", "very_high"] as const;
    return classes.map((cls, i) => ({ cls, label: labels[i], range: formatRange(b[i], b[i + 1], unit, effectiveMetric) }));
  }, [effectiveMetric, geoMeta?.jenks_breaks_cases, geoMeta?.jenks_breaks_incidence, geoMeta?.jenks_breaks_surge, rankingData?.jenks_breaks_surge]);

  const periodLabel = useMemo(
    () => formatDateRange(geoMeta?.period_start_week, geoMeta?.period_end_week) ?? period.toUpperCase(),
    [geoMeta?.period_end_week, geoMeta?.period_start_week, period],
  );

  const metricClassForFeature = useCallback((feature: { properties: Record<string, unknown> }, row?: RankingRow) => {
    if (effectiveMetric === "surge") {
      return String(useAction ? (row?.surge_class ?? "very_low") : (row?.surge_class ?? feature.properties.surge_class ?? "unknown"));
    }
    if (effectiveMetric === "incidence") {
      return String(row?.burden_class ?? feature.properties.burden_class ?? "unknown");
    }
    return String(row?.cases_class ?? feature.properties.cases_class ?? "unknown");
  }, [effectiveMetric, useAction]);

  const metricValueForFeature = useCallback((feature: { properties: Record<string, unknown> }, row?: RankingRow) => {
    if (effectiveMetric === "surge") {
      return Number(useAction ? (row?.surge_score ?? 0) : (row?.surge_score ?? feature.properties.forecast_surge_ratio ?? 0));
    }
    if (effectiveMetric === "incidence") {
      return Number(row?.total_forecast_incidence_per_100k ?? feature.properties.forecast_incidence_per_100k ?? 0);
    }
    return Number(
      dataMode === "observed"
        ? (row?.observed_cases_w ?? row?.total_forecast_cases ?? row?.total_forecast ?? feature.properties.latest_cases ?? 0)
        : (row?.forecast_w_cases ?? row?.total_forecast_cases ?? row?.total_forecast ?? feature.properties.forecast_cases ?? feature.properties.latest_forecast ?? 0)
    );
  }, [dataMode, effectiveMetric, useAction]);

  const selectedCenter = useMemo(() => {
    if (!selectedBarangay?.clean || !geo?.features?.length) return null;
    const feature = geo.features.find((f) => String(f.properties.name ?? "") === selectedBarangay.clean) as MapFeature | undefined;
    return feature ? featureCentroid(feature) : null;
  }, [geo, selectedBarangay]);

  const stats = useMemo(() => {
    if (!geo?.features?.length) {
      return { total: 0, very_high: 0, high: 0, medium: 0, low: 0, very_low: 0 };
    }
    let total = 0;
    let very_high = 0;
    let high = 0;
    let medium = 0;
    let low = 0;
    let very_low = 0;

    for (const f of geo.features as Array<{ properties: Record<string, unknown> }>) {
      const name = String(f.properties.name ?? "");
      const row = rankingByName.get(name);
      const value = metricValueForFeature(f, row);
      const cls = metricClassForFeature(f, row);

      total += value;
      if (cls === "very_high") very_high += 1;
      else if (cls === "high") high += 1;
      else if (cls === "medium") medium += 1;
      else if (cls === "low") low += 1;
      else if (cls === "very_low") very_low += 1;
    }

    return { total, very_high, high, medium, low, very_low };
  }, [geo, rankingByName, metricClassForFeature, metricValueForFeature]);

  const asOfDate = useMemo(() => {
    const raw = geoMeta?.data_last_updated ?? null;
    if (!raw) return "-";
    const d = new Date(raw);
    if (Number.isNaN(d.getTime())) return String(raw);
    return d.toLocaleDateString([], { year: "numeric", month: "short", day: "2-digit" });
  }, [geoMeta?.data_last_updated]);

  const highlightedNames = useMemo(() => {
    if (!geo?.features?.length) return [];
    return geo.features
      .filter((f) => {
        const key = String(f.properties.name ?? "");
        const row = rankingByName.get(key);
        const level = metricClassForFeature(f, row);
        return level === "very_high";
      })
      .map((f) => humanizeName(String(f.properties.display_name ?? f.properties.name ?? "")))
      .sort((a, b) => a.localeCompare(b));
  }, [geo, rankingByName, metricClassForFeature]);

  const mapLabels = useMemo(() => {
    if (!geo?.features?.length) return [];
    return geo.features
      .map((f) => {
        const key = String(f.properties.name ?? "");
        const row = rankingByName.get(key);
        const level = metricClassForFeature(f, row);
        if (level !== "very_high") return null;
        const center = featureCentroid(f as MapFeature);
        if (!center) return null;
        return {
          key,
          level,
          center,
          label: humanizeName(String(f.properties.display_name ?? f.properties.name ?? "")),
        };
      })
      .filter((item): item is { key: string; level: string; center: [number, number]; label: string } => item !== null);
  }, [geo, rankingByName, metricClassForFeature]);

  const style = (feature?: MapFeature) => {
    if (!feature) {
      return {
        fillColor: "#9ca3af",
        fillOpacity: dataMode === "observed" ? 0.66 : 0.8,
        color: "#334155",
        weight: 1,
      };
    }
    const key = String(feature.properties.name ?? "");
    const row = rankingByName.get(key);
    const level = metricClassForFeature(feature, row);
    const selected = selectedBarangay?.clean === key;
    return {
      fillColor: getColor(level),
      fillOpacity: dataMode === "observed" ? 0.68 : 0.8,
      color: selected ? "#ffffff" : level === "very_high" ? "#1e3a8a" : "#334155",
      weight: selected ? 3 : level === "very_high" ? 2.5 : level === "high" ? 2 : 1,
    };
  };

  const onEachFeature = (feature: MapFeature, layer: MapLayer) => {
    const key = String(feature.properties.name ?? "");
    const row = rankingByName.get(key);
    const label = humanizeName(String(feature.properties.display_name ?? key));
    const level = metricClassForFeature(feature, row);
    const value = metricValueForFeature(feature, row);
    const pop = feature.properties.population ? Number(feature.properties.population).toLocaleString() : "-";
    const labelValue = effectiveMetric === "cases" ? formatCases(value) : effectiveMetric === "surge" ? formatSurgeX(value) : formatRate(value);
    const mainLabel =
      effectiveMetric === "surge"
        ? "Forecasted surge"
        : effectiveMetric === "incidence"
        ? (dataMode === "observed" ? "Observed incidence (/100k)" : "Forecasted incidence (/100k)")
        : (dataMode === "observed" ? "Observed cases" : "Forecasted cases");
    const surgeDetail =
      effectiveMetric === "surge"
        ? `<br/>Baseline: <strong>${formatCases(row?.baseline_expected_w ?? feature.properties.baseline_expected_w ?? 0)}</strong>`
        : "";

    layer.bindTooltip(
      `<div style="font-size:11px;line-height:1.3;"><strong>${label}</strong><br/>
      View: <strong>${dataMode === "observed" ? "Observed" : "Forecasted"}</strong><br/>
      Date range: <strong>${periodLabel}</strong><br/>
      Population: <strong>${pop}</strong><br/>
      Class: <strong>${humanizeClass(level)}</strong><br/>
      ${mainLabel}: <strong>${labelValue}</strong>${surgeDetail}
      <div style="font-size:10px;color:#888;margin-top:4px">Click to view trend</div></div>`,
      { sticky: true }
    );

    layer.on("click", () => {
      if (selectedBarangay?.clean === key) onBarangaySelect(null);
      else onBarangaySelect({ pretty: label, clean: key });
    });
  };

  return (
    <Card className={`flex flex-col xl:h-[780px] ${
      dataMode === "observed"
        ? "border-[#67B99A] bg-card shadow-[inset_0_2px_0_rgba(103,185,154,0.3)]"
        : "border-blue-300 bg-card shadow-[inset_0_1px_0_rgba(59,130,246,0.18)]"
    }`}>
      <CardHeader className="p-3 md:p-6">
        <div className="flex flex-col gap-3">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <CardTitle className="text-lg font-semibold">Choropleth Map</CardTitle>
              <Badge variant="outline" className="text-xs">
                {periodLabel} • As of {asOfDate}
              </Badge>
            </div>
            <Badge
              variant="secondary"
              className={`text-xs ${
                dataMode === "observed"
                  ? "bg-[#88D4AB] text-[#1F5F46] dark:bg-[#67B99A]/30 dark:text-[#BFEFD0]"
                  : "bg-blue-100 text-blue-900 dark:bg-blue-900/40 dark:text-blue-200"
              }`}
            >
              {dataMode === "observed"
                ? effectiveMetric === "cases"
                  ? "Observed Cases"
                  : "Observed Incidence"
                : effectiveMetric === "cases"
                ? "Forecasted Cases"
                : effectiveMetric === "incidence"
                ? "Forecasted Incidence"
                : "Forecasted Surge"}
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
          {!mapLoading ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
              {[
                { label: "Total", value: effectiveMetric === "cases" ? formatCases(stats.total) : effectiveMetric === "surge" ? formatSurgeX(stats.total) : formatRate(stats.total) },
                { label: "Very High", value: stats.very_high, color: "text-[#F93716]" },
                { label: "High", value: stats.high, color: "text-[#EF6C00]" },
                { label: "Medium", value: stats.medium, color: "text-[#FFB74D]" },
                { label: "Low", value: stats.low, color: "text-[#3085BE]" },
                { label: "Very Low", value: stats.very_low, color: "text-[#69BCE8]" },
              ].map((item) => (
                <div key={item.label} className="bg-secondary/50 rounded-lg p-2 min-w-0 text-center">
                  <div className={`text-xl md:text-2xl font-bold ${item.color ?? ""}`}>{item.value}</div>
                  <div className="text-[11px] text-muted-foreground truncate">{item.label}</div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </CardHeader>

      <CardContent className="p-3 md:p-6 space-y-3 flex-1 min-h-0">
        <div className="relative h-80 md:h-[450px] xl:h-full w-full rounded-lg border overflow-hidden">
          {mapLoading ? (
            <div className="flex items-center justify-center h-full">Loading map...</div>
          ) : geo ? (
            <MapContainer center={[7.1907, 125.4553]} zoom={11} scrollWheelZoom className="w-full h-full">
              <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" opacity={0.35} />
              <MapFocusController center={selectedCenter} focusToken={focusToken} zoom={13} />
              <GeoJSON
                key={`${effectiveMetric}-${dataMode}-${period}-${geoMeta?.run_id ?? ""}-${geoMeta?.model_name ?? ""}`}
                data={geo}
                style={style}
                onEachFeature={onEachFeature}
              />
              {showMapLabels ? mapLabels.map((item) => (
                <Marker
                  key={item.key}
                  position={item.center}
                  interactive
                  eventHandlers={{
                    click: () => {
                      if (selectedBarangay?.clean === item.key) {
                        onBarangaySelect(null);
                      } else {
                        onBarangaySelect({ pretty: item.label, clean: item.key });
                      }
                    },
                  }}
                  icon={divIcon({
                    className: "barangay-map-label",
                    html: `<div style="display:flex;align-items:center;gap:6px;color:#5b2510;font-size:10px;font-weight:700;white-space:nowrap;cursor:pointer;"><span style="width:8px;height:8px;border-radius:9999px;background:#F93716;display:inline-block;flex:0 0 auto;"></span><span style="background:rgba(255,255,255,0.76);padding:3px 6px;border-radius:8px;border:1px solid rgba(91,37,16,0.12);box-shadow:0 1px 4px rgba(0,0,0,0.14);">${item.label}</span></div>`,
                  })}
                />
              )) : null}
            </MapContainer>
          ) : (
            <div className="text-red-500 p-4">Failed to load map.</div>
          )}

          <div className="absolute top-2 right-2 max-w-[60vw] md:max-w-[320px] bg-white/85 dark:bg-slate-950/80 border border-slate-300 dark:border-slate-700 p-2 rounded-lg backdrop-blur-sm z-50">
            <div className="text-[10px] text-slate-700 dark:text-slate-200 font-medium">
              {effectiveMetric === "cases"
                ? "VERY HIGH CASE BARANGAYS"
                : effectiveMetric === "incidence"
                ? "VERY HIGH INCIDENCE BARANGAYS"
                : "VERY HIGH SURGE BARANGAYS"}
            </div>
            <div className="mt-1 flex flex-wrap gap-1">
              {highlightedNames.length ? (
                highlightedNames.map((name) => (
                  <Badge key={name} variant="secondary" className="text-[10px]">
                    {name}
                  </Badge>
                ))
              ) : (
                <span className="text-xs text-muted-foreground">None in current view</span>
              )}
            </div>
          </div>

          <div className="absolute bottom-2 left-2 max-w-[56vw] md:max-w-[360px] bg-background/95 border p-1.5 md:p-3 rounded-lg backdrop-blur-sm z-50">
            <div className="text-[9px] md:text-xs font-medium mb-1 md:mb-2 text-muted-foreground">
              {effectiveMetric === "incidence" ? "Incidence Levels" : effectiveMetric === "surge" ? "Surge Levels" : "Case Levels"}
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
