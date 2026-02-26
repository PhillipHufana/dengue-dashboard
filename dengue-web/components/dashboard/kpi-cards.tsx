"use client";

import { useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Activity, AlertTriangle, MapPin, BarChart3 } from "lucide-react";
import { useSummary } from "@/lib/query/hooks";
import { useDashboardStore } from "@/lib/store/dashboard-store";
import { useChoropleth } from "@/lib/query/hooks";

type BarangayLatest = {
  name: string;
  display_name?: string;
  forecast: number | null;
  week_start: string;
  risk_level?: string;
};

type SummaryResponse = {
  city_latest: { week_start: string; city_cases: number; created_at: string } | null;
  barangay_latest: BarangayLatest[];
  total_forecasted_cases: number;
};

export function KpiCards() {
  const runId = useDashboardStore((s) => s.runId);
  const modelName = useDashboardStore((s) => s.modelName);
  const period = useDashboardStore((s) => s.period);

  const { data, isLoading, error } = useSummary(runId, modelName, period);

  const { data: geo } = useChoropleth(runId, modelName, period);
  const cityForecastCases = (geo as any)?.city_forecast_cases ?? null;
  const cityIncidence = (geo as any)?.city_incidence_per_100k ?? null;
  const summary: SummaryResponse | null = data ?? null;
  const city = summary?.city_latest ?? null;

  const barangays: BarangayLatest[] = summary?.barangay_latest ?? [];
  const totalForecasted = summary?.total_forecasted_cases ?? 0;

  const riskMetric = useDashboardStore((s) => s.riskMetric);

 
  const veryHighCount = useMemo(() => {
    const feats = (geo as any)?.features ?? [];
    const key = riskMetric === "cases" ? "cases_class" : "burden_class";
    return feats.filter((f: any) => f?.properties?.[key] === "very_high").length;
  }, [geo, riskMetric]);

  const hotspot = useMemo(() => {
    const feats = (geo as any)?.features ?? [];
    const valueKey =
      riskMetric === "cases" ? "forecast_cases" : "forecast_incidence_per_100k";

    let best: any = null;
    let bestVal = -Infinity;

    for (const f of feats) {
      const v = Number(f?.properties?.[valueKey]);
      if (Number.isFinite(v) && v > bestVal) {
        bestVal = v;
        best = f;
      }
    }

    if (!best) return null;

    return {
      name: best.properties?.display_name ?? best.properties?.name ?? "—",
      value: bestVal,
    };
  }, [geo, riskMetric]);




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
              {cityForecastCases != null ? Number(cityForecastCases).toLocaleString() : "—"}
            </p>
            <p className="text-xs text-muted-foreground">
              City forecast cases (next {period.toUpperCase()})
            </p>
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
              {cityIncidence != null ? Number(cityIncidence).toFixed(2) : "—"}
            </p>
            <p className="text-xs text-muted-foreground">City cumulative incidence (/100k)</p>
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
              Barangays (Very High {riskMetric === "cases" ? "cases" : "burden"})
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
                ? riskMetric === "cases"
                  ? hotspot.value.toLocaleString()
                  : hotspot.value.toFixed(2)
                : "—"}
            </p>
            <p className="text-xs text-muted-foreground">
              {hotspot?.name ?? "—"}{" "}
              {hotspot ? (riskMetric === "cases" ? "(cases)" : "(/100k)") : ""}
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
