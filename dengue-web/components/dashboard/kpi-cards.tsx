"use client";

import { useMemo } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { TrendingUp, Activity, AlertTriangle, MapPin, BarChart3 } from "lucide-react";
import { useSummary } from "@/lib/query/hooks";

// Types based on your real API
type BarangayLatest = {
  name: string;
  forecast: number | null;
  week_start: string;
};

type SummaryResponse = {
  city_latest: {
    week_start: string;
    city_cases: number;
    created_at: string;
  } | null;
  barangay_latest: BarangayLatest[];
  total_forecasted_cases: number;
};

export function KpiCards() {
  // 🔥 Hooks MUST be at the very top
  const { data, isLoading, error } = useSummary();

  // Ensure we always have a usable structure to avoid conditional hook execution
  const summary: SummaryResponse | null = data ?? null;
  const city = summary?.city_latest ?? null;

  const barangays: BarangayLatest[] = summary?.barangay_latest ?? [];
  const totalForecasted = summary?.total_forecasted_cases ?? 0;

  const hotspotThreshold = 5;

  // 🔥 useMemo must ALWAYS run (even while loading) — use fallback []
  const hotspotBarangays = useMemo(
    () => barangays.filter((b) => (b.forecast ?? 0) >= hotspotThreshold),
    [barangays]
  );

  const topBarangay = useMemo(() => {
    if (!barangays.length) return null;
    return [...barangays].sort((a, b) => (b.forecast ?? 0) - (a.forecast ?? 0))[0];
  }, [barangays]);

  // Now we can render conditionally — AFTER hooks
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

  if (error || !summary) {
    return <div className="text-sm text-destructive">Failed to load dashboard summary.</div>;
  }

  return (
    <div className="grid grid-cols-2 gap-3 md:gap-4 lg:grid-cols-4">
      {/* Card 1 — Latest city cases */}
      <Card className="bg-card border-border">
        <CardContent className="p-3 md:p-6">
          <div className="flex items-center justify-between">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary">
              <Activity className="h-4 w-4 text-primary" />
            </div>
            <span className="text-xs md:text-sm text-primary font-medium">Latest</span>
          </div>

          <div className="mt-4">
            <p className="text-xl font-bold">
              {city?.city_cases?.toLocaleString() ?? "—"}
            </p>
            <p className="text-xs text-muted-foreground">
              City-wide dengue cases
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Card 2 — Total forecast */}
      <Card className="bg-card border-border">
        <CardContent className="p-3 md:p-6">
          <div className="flex items-center justify-between">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary">
              <BarChart3 className="h-4 w-4 text-primary" />
            </div>
            <span className="text-xs md:text-sm text-primary font-medium">Forecast</span>
          </div>

          <div className="mt-4">
            <p className="text-xl font-bold">{totalForecasted.toFixed(2)}</p>
            <p className="text-xs text-muted-foreground">Total forecasted cases</p>
          </div>
        </CardContent>
      </Card>

      {/* Card 3 — Hotspots */}
      <Card className="bg-card border-border">
        <CardContent className="p-3 md:p-6">
          <div className="flex items-center justify-between">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary">
              <AlertTriangle className="h-4 w-4 text-destructive" />
            </div>
            <span className="text-xs md:text-sm text-destructive font-medium">Hotspots</span>
          </div>

          <div className="mt-4">
            <p className="text-xl font-bold">{hotspotBarangays.length}</p>
            <p className="text-xs text-muted-foreground">
              Barangays ≥ {hotspotThreshold} forecast
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Card 4 — Top Barangay */}
      <Card className="bg-card border-border">
        <CardContent className="p-3 md:p-6">
          <div className="flex items-center justify-between">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary">
              <MapPin className="h-4 w-4 text-primary" />
            </div>
            <span className="text-xs md:text-sm text-primary font-medium">Highest</span>
          </div>

          <div className="mt-4">
            <p className="text-xl font-bold">
              {topBarangay?.forecast?.toFixed(2) ?? "—"}
            </p>
            <p className="text-xs text-muted-foreground">{topBarangay?.name ?? "—"}</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
