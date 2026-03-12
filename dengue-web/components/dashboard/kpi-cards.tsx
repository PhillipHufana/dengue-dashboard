"use client";

import { useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Activity, AlertTriangle, MapPin, BarChart3 } from "lucide-react";
import { useChoropleth, useCityCompareSeries } from "@/lib/query/hooks";
import { useDashboardStore } from "@/lib/store/dashboard-store";
import type { ChoroplethFC } from "@/lib/api";

const PERIOD_WEEKS: Record<string, number> = {
  "1w": 1,
  "2w": 2,
  "1m": 4,
  "3m": 12,
  "6m": 26,
  "1y": 52,
};

type MetricClass = "cases_class" | "burden_class" | "surge_class";

export function KpiCards() {
  const runId = useDashboardStore((s) => s.runId);
  const modelName = useDashboardStore((s) => s.modelName);
  const period = useDashboardStore((s) => s.period);
  const riskMetric = useDashboardStore((s) => s.riskMetric);
  const dataMode = useDashboardStore((s) => s.dataMode);
  const effectiveMetric =
    riskMetric === "action_priority" ? (dataMode === "observed" ? "cases" : "surge") : riskMetric;

  const { data: geo, isLoading, error } = useChoropleth(runId, modelName, period, dataMode);
  const { data: cityCompare } = useCityCompareSeries(runId, dataMode === "forecast");
  const geoSafe = geo as (ChoroplethFC & {
    city_forecast_cases?: number | null;
    city_incidence_per_100k?: number | null;
    city_surge_ratio?: number | null;
  }) | undefined;

  const cityForecastCases = geoSafe?.city_forecast_cases ?? null;
  const cityIncidence = geoSafe?.city_incidence_per_100k ?? null;
  const citySurgeRatio = geoSafe?.city_surge_ratio ?? null;
  const geoFeatures = useMemo(() => geoSafe?.features ?? [], [geoSafe?.features]);

  const compareCityTotals = useMemo(() => {
    if (!cityCompare?.series?.length) return null;
    const w = PERIOD_WEEKS[period] ?? 4;
    const fut = cityCompare.series.filter((x) => x.is_future).slice(0, w);
    const prophet = fut.reduce((a, x) => a + Number(x.yhat_prophet ?? 0), 0);
    const arima = fut.reduce((a, x) => a + Number(x.yhat_arima ?? 0), 0);
    return { prophet, arima };
  }, [cityCompare, period]);

  const veryHighCount = useMemo(() => {
    const key: MetricClass = effectiveMetric === "cases" ? "cases_class" : effectiveMetric === "incidence" ? "burden_class" : "surge_class";
    return geoFeatures.filter((f) => (f?.properties as Record<string, string | undefined>)?.[key] === "very_high").length;
  }, [geoFeatures, effectiveMetric]);

  const hotspot = useMemo(() => {
    const valueKey =
      effectiveMetric === "cases"
        ? (dataMode === "observed" ? "observed_cases" : "forecast_cases")
        : effectiveMetric === "incidence"
        ? (dataMode === "observed" ? "observed_incidence_per_100k" : "forecast_incidence_per_100k")
        : "forecast_surge_ratio";

    let best: (typeof geoFeatures)[number] | null = null;
    let bestVal = -Infinity;
    for (const f of geoFeatures) {
      const props = f?.properties as Record<string, unknown>;
      const v = Number(props?.[valueKey] ?? 0);
      if (Number.isFinite(v) && v > bestVal) {
        bestVal = v;
        best = f;
      }
    }
    if (!best) return null;
    const props = best.properties as Record<string, unknown>;
    return {
      name: String(props?.display_name ?? props?.name ?? "-"),
      value: bestVal,
    };
  }, [geoFeatures, effectiveMetric, dataMode]);

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-3 md:gap-4 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i} className="bg-card border-border">
            <CardContent className="p-3 md:p-6 animate-pulse">
              <div className="flex items-center justify-between">
                <div className="h-8 w-8 rounded-lg bg-secondary" />
                <div className="h-4 w-16 rounded bg-secondary" />
              </div>
              <div className="mt-4 space-y-2">
                <div className="h-6 w-20 rounded bg-secondary" />
                <div className="h-4 w-24 rounded bg-secondary" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (error && !geo) {
    return <div className="text-sm text-destructive">Failed to load dashboard data.</div>;
  }

  return (
    <div className="grid grid-cols-2 gap-3 md:gap-4 lg:grid-cols-4">
      <Card className="bg-card border-border">
        <CardContent className="p-3 md:p-6">
          <div className="flex items-center justify-between">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary">
              <Activity className="h-4 w-4 text-primary" />
            </div>
            <span className="text-xs md:text-sm text-primary font-medium">{period.toUpperCase()}</span>
          </div>
          <div className="mt-4">
            <p className="text-xl font-bold">
              {cityForecastCases != null ? Number(cityForecastCases).toLocaleString() : "-"}
            </p>
            {dataMode === "observed" ? (
              <p className="text-xs text-muted-foreground">City observed cases (past {period.toUpperCase()})</p>
            ) : (
              <div className="text-xs text-muted-foreground">
                <p>City forecast cases (next {period.toUpperCase()})</p>
                {compareCityTotals ? (
                  <p>P {compareCityTotals.prophet.toFixed(1)} | A {compareCityTotals.arima.toFixed(1)}</p>
                ) : null}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card border-border">
        <CardContent className="p-3 md:p-6">
          <div className="flex items-center justify-between">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary">
              <BarChart3 className="h-4 w-4 text-primary" />
            </div>
            <span className="text-xs md:text-sm text-primary font-medium">{period.toUpperCase()}</span>
          </div>
          <div className="mt-4">
            <p className="text-xl font-bold">
              {effectiveMetric === "surge"
                ? citySurgeRatio != null
                  ? Number(citySurgeRatio).toFixed(2)
                  : "-"
                : cityIncidence != null
                ? Number(cityIncidence).toFixed(2)
                : "-"}
            </p>
            <p className="text-xs text-muted-foreground">
              {effectiveMetric === "surge"
                ? `City surge ratio (${period.toUpperCase()} vs past 8W)`
                : dataMode === "observed"
                ? "City observed incidence (/100k)"
                : "City forecast incidence (/100k)"}
            </p>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card border-border">
        <CardContent className="p-3 md:p-6">
          <div className="flex items-center justify-between">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary">
              <AlertTriangle className="h-4 w-4 text-destructive" />
            </div>
            <span className="text-xs md:text-sm text-destructive font-medium">{period.toUpperCase()}</span>
          </div>
          <div className="mt-4">
            <p className="text-xl font-bold">{veryHighCount}</p>
            <p className="text-xs text-muted-foreground">
              Barangays (Very High {effectiveMetric === "cases" ? "cases" : effectiveMetric === "incidence" ? "burden" : "surge"})
            </p>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card border-border">
        <CardContent className="p-3 md:p-6">
          <div className="flex items-center justify-between">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary">
              <MapPin className="h-4 w-4 text-primary" />
            </div>
            <span className="text-xs md:text-sm text-primary font-medium">{period.toUpperCase()}</span>
          </div>
          <div className="mt-4">
            <p className="text-xl font-bold">
              {hotspot
                ? effectiveMetric === "cases"
                  ? hotspot.value.toLocaleString()
                  : hotspot.value.toFixed(2)
                : "-"}
            </p>
            <p className="text-xs text-muted-foreground">
              {hotspot?.name ?? "-"}{" "}
              {hotspot
                ? effectiveMetric === "cases"
                  ? "(cases)"
                  : effectiveMetric === "incidence"
                  ? "(/100k)"
                  : "(surge ratio)"
                : ""}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
