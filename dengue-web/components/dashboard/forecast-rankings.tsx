"use client";

import React, { useState, useMemo } from "react";
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import type { RankingRow } from "@/lib/api";
import { useDashboardStore } from "@/lib/store/dashboard-store";
import { TrendingUp, Search, ChevronUp, ChevronDown } from "lucide-react";
import { useActionPriority, useRankings } from "@/lib/query/hooks";
import { usePathname } from "next/navigation";
import { formatCases, formatRate, formatSurgeX } from "@/lib/number-format";

interface ForecastRankingsProps {
  selectedBarangay: { pretty: string; clean: string } | null;
  onBarangaySelect: (value: { pretty: string; clean: string } | null) => void;
}

export const ForecastRankings = React.memo(function ForecastRankings({
  selectedBarangay,
  onBarangaySelect,
}: ForecastRankingsProps) {
  type RiskFilter = "all" | "very_high" | "high" | "medium" | "low" | "very_low";
  const riskMetric = useDashboardStore((s) => s.riskMetric);
  const timePeriod = useDashboardStore((s) => s.period);
  const dataMode = useDashboardStore((s) => s.dataMode);

  const [searchQuery, setSearchQuery] = useState("");
  const [showAll, setShowAll] = useState(false);
  const [riskFilter, setRiskFilter] = useState<RiskFilter>("all");

  const runId = useDashboardStore((s) => s.runId);
  const modelName = useDashboardStore((s) => s.modelName);
  const pathname = usePathname();
  const isAdminView = pathname?.startsWith("/admin") ?? false;

  const useAction = riskMetric === "action_priority";
  const effectiveMetric =
    riskMetric === "action_priority" ? (dataMode === "observed" ? "cases" : "surge") : riskMetric;
  const rankingsQuery = useRankings(timePeriod, runId, modelName, effectiveMetric, dataMode);
  const actionQuery = useActionPriority(timePeriod, runId, modelName, dataMode, useAction);
  const data = useAction ? actionQuery.data : rankingsQuery.data;
  const isLoading = useAction ? actionQuery.isLoading : rankingsQuery.isLoading;
  const rankingTitle =
    useAction
      ? dataMode === "observed"
        ? "Recommended places to respond to now"
        : "Recommended places to prepare for next"
      : dataMode === "observed"
      ? riskMetric === "cases"
        ? "Places with the most reported cases"
        : "Places with the highest current risk rate"
      : riskMetric === "cases"
      ? "Places with the most expected cases"
      : riskMetric === "incidence"
      ? "Places with the highest expected risk rate"
      : "Places where risk is expected to rise fastest";
  const barangays: RankingRow[] = useMemo(() => {
    const baseRows = useAction ? (actionQuery.data?.rows ?? []) : (data?.rankings ?? []);
    const list = baseRows.slice();

    if (useAction) return list;

    list.sort((a, b) => {
      if (riskMetric === "surge") {
        const av = Number(a.surge_score ?? 0);
        const bv = Number(b.surge_score ?? 0);
        return bv - av;
      }
      if (riskMetric === "cases") {
        const av = Number(a.total_forecast_cases ?? a.total_forecast ?? 0);
        const bv = Number(b.total_forecast_cases ?? b.total_forecast ?? 0);
        return bv - av;
      }
      const av = Number(a.total_forecast_incidence_per_100k ?? 0);
      const bv = Number(b.total_forecast_incidence_per_100k ?? 0);
      return bv - av;
    });

    return list;
  }, [useAction, actionQuery.data?.rows, data, riskMetric]);
  const lastUpdated = data?.model_current_date;

  const filtered = useMemo(() => {
    let list = barangays;

    if (riskFilter !== "all") {
      list = list.filter((b) => {
        const cls = effectiveMetric === "surge"
          ? (b.surge_class ?? "unknown")
          :
          effectiveMetric === "cases"
            ? (b.cases_class ?? "unknown")
            : (b.burden_class ?? "unknown");
        return cls === riskFilter;
      });
    }

    return list.filter((b) =>
      b.pretty_name.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [barangays, searchQuery, riskFilter, effectiveMetric]);

  const displayed = showAll ? filtered : filtered.slice(0, 10);

  const getRiskColor = (lvl: string) => {
    switch (lvl) {
      case "very_high":
        return "bg-red-500/20 text-red-400 border-red-500/30";
      case "high":
        return "bg-orange-500/20 text-orange-400 border-orange-500/30";
      case "medium":
        return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
      case "low":
        return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30";
      case "very_low":
        return "bg-green-500/20 text-green-400 border-green-500/30";
      default:
        return "bg-muted/40 text-muted-foreground border-border";
    }
  };

  if (isLoading) {
    return (
      <Card className="bg-card border-border">
        <CardHeader className="p-3 pb-2 md:p-6 md:pb-3">
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <Skeleton className="h-4 w-4 rounded-full" />
              <Skeleton className="h-4 w-32" />
            </div>
            <p className="text-[10px] text-muted-foreground">Loading model date…</p>
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </div>
        </CardHeader>

        <CardContent className="p-3 pt-0 md:p-6 md:pt-0">
          <div className="space-y-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3 p-2 rounded-lg">
                <Skeleton className="h-7 w-7 rounded-full" />
                <div className="flex-1 space-y-1">
                  <Skeleton className="h-3 w-3/5" />
                  <Skeleton className="h-3 w-2/5" />
                </div>
                <div className="space-y-1">
                  <Skeleton className="h-3 w-10" />
                  <Skeleton className="h-3 w-12" />
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-card border-border h-full xl:h-[780px] flex flex-col">
      <CardHeader className="p-3 pb-2 md:p-6 md:pb-3">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-primary" />
            <CardTitle className="text-base md:text-lg font-semibold">{rankingTitle}</CardTitle>
          </div>

          

          {lastUpdated && data ? (
            <div className="text-[10px] text-muted-foreground leading-tight">
              <p>
                Mode: {dataMode === "observed" ? "Respond Now (Past W weeks)" : "Prepare Next (Next W weeks)"}
              </p>
              <p>Data updated through: {data.model_current_date}</p>
              <p>Today: {data.user_current_date}</p>
              <p className="italic opacity-80">Forecast dates are counted from the latest available data.</p>
            </div>
          ) : null}

          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="Search barangay..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 h-8 text-xs bg-secondary/50"
            />
          </div>

          <div className="flex gap-1 p-1 bg-secondary/50 rounded-lg">
            {["all", "very_high", "high", "medium", "low", "very_low"].map((r) => (
              <Button
                key={r}
                size="sm"
                variant={riskFilter === r ? "default" : "ghost"}
                className="text-[10px]"
                onClick={() => setRiskFilter(r as RiskFilter)}
              >
                {r === "all" ? "ALL" : r.replace("_", " ").toUpperCase()}
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-3 pt-0 md:p-6 md:pt-0 flex-1 min-h-0">
        <ScrollArea className="h-full">
          <div className="space-y-2">
            {displayed.map((b, index) => {
              const rank = index + 1;
              const isSelected = selectedBarangay?.clean === b.name;

              const cls =
                effectiveMetric === "surge"
                  ? (b.surge_class ?? "unknown")
                  :
                effectiveMetric === "cases"
                  ? (b.cases_class ?? b.risk_level_cases ?? b.risk_level ?? "unknown")
                  : (b.burden_class ?? b.risk_level_incidence ?? "unknown");

              const value =
                effectiveMetric === "surge"
                  ? Number(b.surge_score ?? 0)
                  :
                effectiveMetric === "cases"
                  ? Number(b.total_forecast_cases ?? b.total_forecast ?? 0)
                  : Number(b.total_forecast_incidence_per_100k ?? 0);

              return (
                <div
                  key={b.name}
                  onClick={() => onBarangaySelect(isSelected ? null : { pretty: b.pretty_name, clean: b.name })}
                  className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-all ${
                    isSelected
                      ? "bg-primary/20 border border-primary"
                      : "bg-secondary/30 hover:bg-secondary/50 border border-transparent"
                  }`}
                >
                  <div
                    className={`flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold ${
                      rank <= 3
                        ? "bg-primary text-primary-foreground"
                        : rank <= 10
                        ? "bg-primary/30 text-primary"
                        : "bg-secondary text-muted-foreground"
                    }`}
                  >
                    {rank}
                  </div>

                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm truncate">{b.pretty_name}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge className={`text-[9px] ${getRiskColor(cls)}`}>
                        {cls.toUpperCase()}
                      </Badge>
                    </div>
                  </div>

                  <div className="text-right">
                    <p className="font-bold text-sm">
                      {effectiveMetric === "surge"
                        ? formatSurgeX(value)
                        : effectiveMetric === "cases"
                        ? formatCases(value)
                        : formatRate(value)}
                    </p>
                    {effectiveMetric === "surge" ? (
                      <div className="text-[10px] text-muted-foreground">
                        Next W: {formatCases(b.forecast_w_cases ?? 0)} | Baseline W: {formatCases(b.baseline_expected_w ?? 0)}
                      </div>
                    ) : null}
                    {isAdminView ? (
                      <div className="text-[10px] text-muted-foreground">
                        Obs {formatCases(b.observed_cases_w ?? 0)} | P {formatCases(b.prophet_forecast_w ?? 0)} | A {formatCases(b.arima_forecast_w ?? 0)}
                      </div>
                    ) : null}
                    {/*
                    <div
                      title={b.trend_message}
                      className={`flex items-center justify-end gap-1 text-[10px] ${
                        b.trend > 0
                          ? "text-red-400"
                          : b.trend < 0
                          ? "text-green-400"
                          : "text-muted-foreground"
                      }`}
                    >
                      {b.trend > 0 && <ChevronUp className="h-3 w-3" />}
                      {b.trend < 0 && <ChevronDown className="h-3 w-3" />}
                      {Math.abs(b.trend)}%
                    </div>
                    */}
                  </div>
                </div>
              );
            })}
          </div>
        </ScrollArea>

        {filtered.length > 10 && (
          <Button
            variant="outline"
            size="sm"
            className="w-full mt-3 text-xs"
            onClick={() => setShowAll(!showAll)}
          >
            {showAll ? "Show Top 10" : `Show All ${filtered.length} Barangays`}
          </Button>
        )}
      </CardContent>
    </Card>
  );
});
