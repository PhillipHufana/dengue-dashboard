"use client";

import { useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Activity, AlertTriangle, MapPin, BarChart3 } from "lucide-react";
import { useActionPriority, useChoropleth, useCityCompareSeries } from "@/lib/query/hooks";
import { useDashboardStore } from "@/lib/store/dashboard-store";
import type { ActionPriorityResponse, ChoroplethFC, RankingRow } from "@/lib/api";
import { usePathname } from "next/navigation";
import { formatCases, formatRate, formatSurgeX } from "@/lib/number-format";
import { formatDateRange, humanizeName } from "@/lib/display-text";

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
  const pathname = usePathname();
  const isAdminView = pathname?.startsWith("/admin") ?? false;
  const runId = useDashboardStore((s) => s.runId);
  const modelName = useDashboardStore((s) => s.modelName);
  const period = useDashboardStore((s) => s.period);
  const riskMetric = useDashboardStore((s) => s.riskMetric);
  const dataMode = useDashboardStore((s) => s.dataMode);
  const isForecastMode = dataMode === "forecast";
  const useAction = isForecastMode && riskMetric === "action_priority";
  const effectiveMetric = useAction ? "surge" : riskMetric;

  const { data: geo, isLoading, error } = useChoropleth(runId, modelName, period, dataMode);
  const actionQuery = useActionPriority(period, runId, modelName, dataMode, useAction);
  const { data: cityCompare } = useCityCompareSeries(runId, dataMode === "forecast");
  const geoSafe = geo as (ChoroplethFC & {
    city_forecast_cases?: number | null;
    city_incidence_per_100k?: number | null;
    city_surge_ratio?: number | null;
    period_start_week?: string | null;
    period_end_week?: string | null;
  }) | undefined;

  const cityForecastCases = geoSafe?.city_forecast_cases ?? null;
  const cityIncidence = geoSafe?.city_incidence_per_100k ?? null;
  const citySurgeRatio = geoSafe?.city_surge_ratio ?? null;
  const periodLabel = formatDateRange(geoSafe?.period_start_week, geoSafe?.period_end_week) ?? period.toUpperCase();
  const geoFeatures = useMemo(() => geoSafe?.features ?? [], [geoSafe?.features]);
  const actionData = actionQuery.data as ActionPriorityResponse | undefined;
  const actionRows = useMemo(() => actionData?.rows ?? [], [actionData?.rows]);

  const compareCityTotals = useMemo(() => {
    if (!cityCompare?.series?.length) return null;
    const w = PERIOD_WEEKS[period] ?? 4;
    const fut = cityCompare.series.filter((x) => x.is_future).slice(0, w);
    const prophet = fut.reduce((a, x) => a + Number(x.yhat_prophet ?? 0), 0);
    const arima = fut.reduce((a, x) => a + Number(x.yhat_arima ?? 0), 0);
    return { prophet, arima };
  }, [cityCompare, period]);

  const actionSummary = useMemo(() => {
    if (!useAction) return null;
    const rows = actionRows;
    const top = rows[0];
    return {
      cityTotalCases: Number(actionData?.summary?.city_total_cases ?? rows.reduce((a: number, r: RankingRow) => {
        return a + Number(r.forecast_w_cases ?? 0);
      }, 0)),
      priorityCount: Number(actionData?.summary?.priority_count ?? rows.filter((r: RankingRow) => Boolean(r.priority_eligible)).length),
      veryHighCount: Number(actionData?.summary?.very_high_count ?? rows.filter((r: RankingRow) => String(r.surge_class ?? "unknown") === "very_high").length),
      topName: String(actionData?.summary?.top_name ?? top?.pretty_name ?? top?.name ?? "-"),
      topValue: Number(actionData?.summary?.top_value ?? (top?.surge_score ?? 0)),
    };
  }, [useAction, actionRows, actionData]);

  const veryHighCount = useMemo(() => {
    if (useAction && actionSummary) return actionSummary.veryHighCount;
    const key: MetricClass = effectiveMetric === "cases" ? "cases_class" : effectiveMetric === "incidence" ? "burden_class" : "surge_class";
    return geoFeatures.filter((f) => {
      const props = (f?.properties ?? {}) as unknown as Record<string, unknown>;
      return String(props[key] ?? "unknown") === "very_high";
    }).length;
  }, [useAction, actionSummary, geoFeatures, effectiveMetric]);

  const hotspot = useMemo(() => {
    if (useAction && actionSummary) {
      return {
        name: actionSummary.topName,
        value: actionSummary.topValue,
      };
    }
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
  }, [useAction, actionSummary, geoFeatures, effectiveMetric, dataMode]);

  const cardsLoading = isLoading || (useAction && actionQuery.isLoading);

  if (cardsLoading) {
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

  if ((error && !geo) || (useAction && actionQuery.error && !actionData)) {
    return <div className="text-sm text-destructive">Failed to load dashboard data.</div>;
  }

  return (
    <div className="grid grid-cols-2 gap-3 md:gap-4 lg:grid-cols-4">
      <Card className={dataMode === "observed" ? "bg-card border-[#67B99A]" : "bg-card border-blue-300"}>
        <CardContent className="p-3 md:p-6">
          <div className="flex items-center justify-between">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary">
              <Activity className="h-4 w-4 text-primary" />
            </div>
            <span className={`text-xs md:text-sm font-medium ${dataMode === "observed" ? "text-[#2F7D5E] dark:text-[#88D4AB]" : "text-blue-700 dark:text-blue-300"}`}>{periodLabel}</span>
          </div>
          <div className="mt-4">
            <p className="text-2xl md:text-3xl font-bold">
              {useAction && actionSummary
                ? formatCases(actionSummary.cityTotalCases)
                : cityForecastCases != null
                ? formatCases(cityForecastCases)
                : "-"}
            </p>
            {dataMode === "observed" ? (
              <p className="text-xs text-muted-foreground">Observed city cases</p>
            ) : (
              <div className="text-xs text-muted-foreground">
                <p>Forecasted city cases</p>
                {isAdminView && compareCityTotals ? (
                  <p>P {formatCases(compareCityTotals.prophet)} | A {formatCases(compareCityTotals.arima)}</p>
                ) : null}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className={dataMode === "observed" ? "bg-card border-[#67B99A]" : "bg-card border-blue-300"}>
        <CardContent className="p-3 md:p-6">
          <div className="flex items-center justify-between">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary">
              <BarChart3 className="h-4 w-4 text-primary" />
            </div>
            <span className={`text-xs md:text-sm font-medium ${dataMode === "observed" ? "text-[#2F7D5E] dark:text-[#88D4AB]" : "text-blue-700 dark:text-blue-300"}`}>{periodLabel}</span>
          </div>
          <div className="mt-4">
            <p className="text-2xl md:text-3xl font-bold">
              {useAction && actionSummary
                ? formatCases(actionSummary.priorityCount)
                : effectiveMetric === "surge"
                ? citySurgeRatio != null
                  ? formatSurgeX(citySurgeRatio)
                  : "-"
                : cityIncidence != null
                ? formatRate(cityIncidence)
                : "-"}
            </p>
            <p className="text-xs text-muted-foreground">
              {useAction
                ? "Eligible surge barangays"
                : effectiveMetric === "surge"
                ? "Forecasted surge vs baseline"
                : dataMode === "observed"
                ? "Observed incidence (/100k)"
                : "Forecasted incidence (/100k)"}
            </p>
          </div>
        </CardContent>
      </Card>

      <Card className={dataMode === "observed" ? "bg-card border-[#67B99A]" : "bg-card border-blue-300"}>
        <CardContent className="p-3 md:p-6">
          <div className="flex items-center justify-between">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary">
              <AlertTriangle className="h-4 w-4 text-destructive" />
            </div>
            <span className="text-xs md:text-sm text-destructive font-medium">{periodLabel}</span>
          </div>
          <div className="mt-4">
            <p className="text-2xl md:text-3xl font-bold">{veryHighCount}</p>
            <p className="text-xs text-muted-foreground">
              Very High barangays ({effectiveMetric === "cases" ? "cases" : effectiveMetric === "incidence" ? "incidence" : "surge"})
            </p>
          </div>
        </CardContent>
      </Card>

      <Card className={dataMode === "observed" ? "bg-card border-[#67B99A]" : "bg-card border-blue-300"}>
        <CardContent className="p-3 md:p-6">
          <div className="flex items-center justify-between">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary">
              <MapPin className="h-4 w-4 text-primary" />
            </div>
            <span className={`text-xs md:text-sm font-medium ${dataMode === "observed" ? "text-[#2F7D5E] dark:text-[#88D4AB]" : "text-blue-700 dark:text-blue-300"}`}>{periodLabel}</span>
          </div>
          <div className="mt-4">
            <p className="text-2xl md:text-3xl font-bold">
              {hotspot
                ? effectiveMetric === "cases"
                  ? formatCases(hotspot.value)
                  : effectiveMetric === "surge"
                  ? formatSurgeX(hotspot.value)
                  : formatRate(hotspot.value)
                : "-"}
            </p>
            <p className="text-xs text-muted-foreground">
              {humanizeName(hotspot?.name ?? "-")}{" "}
              {hotspot
                ? effectiveMetric === "cases"
                  ? "(cases)"
                  : effectiveMetric === "incidence"
                  ? "(/100k)"
                  : "(change)"
                : ""}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
