"use client";

import React, { useState, useMemo } from "react";
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import type { RankingRow, RankingResponse } from "@/lib/api";
import { useDashboardStore } from "@/lib/store/dashboard-store";
import {
  TrendingUp,
  Search,
  MapPin,
  ChevronUp,
  ChevronDown,
} from "lucide-react";

import { useRankings } from "@/lib/query/hooks";

interface ForecastRankingsProps {
  selectedBarangay: { pretty: string; clean: string } | null;
  onBarangaySelect: (value: { pretty: string; clean: string } | null) => void;
}


type TimePeriod = "1w" | "2w" | "1m" | "3m" | "6m" | "1y";

const timePeriodLabels: Record<TimePeriod, string> = {
  "1w": "1 Week",
  "2w": "2 Weeks",
  "1m": "1 Month",
  "3m": "3 Months",
  "6m": "6 Months",
  "1y": "1 Year",
};

export const ForecastRankings = React.memo(function ForecastRankings({
  selectedBarangay,
  onBarangaySelect,
}: ForecastRankingsProps) {

  const riskMetric = useDashboardStore((s) => s.riskMetric);

  const [timePeriod, setTimePeriod] = useState<TimePeriod>("1m");
  const [searchQuery, setSearchQuery] = useState("");
  const [showAll, setShowAll] = useState(false);
  const [riskFilter, setRiskFilter] =
    useState<"all" | "critical" | "high" | "medium" | "low">("all");

  // 🔥 Calls FastAPI `/forecast/rankings?period=X`
  const runId = useDashboardStore((s) => s.runId);
  const modelName = useDashboardStore((s) => s.modelName);

  const { data, isLoading } = useRankings(timePeriod, runId, modelName);
  const barangays: RankingRow[] = data?.rankings ?? [];

  const lastUpdated = data?.model_current_date;


  // -------------------------------------------------------------
  // 🔎 FILTERING + SORTING (already sorted by backend)
  // -------------------------------------------------------------
  const filtered = useMemo(() => {
    let list = barangays;

    if (riskFilter !== "all") {
      list = list.filter((b) => {
        const risk = riskMetric === "cases" ? b.risk_level_cases : (b.risk_level_incidence ?? "unknown");
        return risk === riskFilter;
      });
    }


    return list.filter((b) =>
      b.pretty_name.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [barangays, searchQuery, riskFilter]);

  const displayed = showAll ? filtered : filtered.slice(0, 10);

  // -------------------------------------------------------------
  // COLORS
  // -------------------------------------------------------------
  const getRiskColor = (risk: string) => {
    switch (risk) {
      case "critical":
        return "bg-red-500/20 text-red-400 border-red-500/30";
      case "high":
        return "bg-orange-500/20 text-orange-400 border-orange-500/30";
      case "medium":
        return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
      default:
        return "bg-green-500/20 text-green-400 border-green-500/30";
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

          <p className="text-[10px] text-muted-foreground">
            Loading model date…
          </p>

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
    <Card className="bg-card border-border">
      <CardHeader className="p-3 pb-2 md:p-6 md:pb-3">
        <div className="flex flex-col gap-3">
          
          {/* Title */}
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-primary" />
            <CardTitle className="text-base md:text-lg font-semibold">
              Forecast Rankings
            </CardTitle>
          </div>

          {/* Time Period Tabs */}
          <Tabs value={timePeriod} onValueChange={(v) => setTimePeriod(v as TimePeriod)}>
            <TabsList className="grid grid-cols-6 w-full h-8">
              {(Object.keys(timePeriodLabels) as TimePeriod[]).map((p) => (
                <TabsTrigger key={p} value={p} className="text-[10px] md:text-xs">
                  {p.toUpperCase()}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          {lastUpdated && (
          <div className="text-[10px] text-muted-foreground leading-tight">
            <p>Model date (latest real data): {data.model_current_date}</p>
            <p>Your current date: {data.user_current_date}</p>
            <p className="italic opacity-80">
              Forecast horizons (1w, 1m, 1y) are relative to the model date.
            </p>
          </div>
        )}


          {/* Search */}
          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="Search barangay..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 h-8 text-xs bg-secondary/50"
            />
          </div>

          {/* Risk filter buttons */}
          <div className="flex gap-1 p-1 bg-secondary/50 rounded-lg">
            {["all", "critical", "high", "medium", "low"].map((r) => (
              <Button
                key={r}
                size="sm"
                variant={riskFilter === r ? "default" : "ghost"}
                className="text-[10px]"
                onClick={() => setRiskFilter(r as any)}
              >
                {r.toUpperCase()}
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>

      {/* Ranking List */}
      <CardContent className="p-3 pt-0 md:p-6 md:pt-0">
        <ScrollArea className="h-80 md:h-[400px]">
          <div className="space-y-2">
            {displayed.map((b, index) => {
              const rank = index + 1;
              const isSelected = selectedBarangay?.clean === b.name;

                const risk =
                  riskMetric === "cases"
                    ? b.risk_level_cases ?? b.risk_level
                    : b.risk_level_incidence ?? "unknown";

                const value =
                  riskMetric === "cases"
                    ? b.total_forecast_cases ?? b.total_forecast
                    : b.total_forecast_incidence_per_100k ?? 0;



              return (
                <div
                  key={b.name}
                  onClick={() =>
                    onBarangaySelect(isSelected ? null : { pretty: b.pretty_name, clean: b.name })
                  }
                  className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-all ${
                    isSelected
                      ? "bg-primary/20 border border-primary"
                      : "bg-secondary/30 hover:bg-secondary/50 border border-transparent"
                  }`}
                >
                  {/* Rank number */}
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

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm truncate">{b.pretty_name}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge className={`text-[9px] ${getRiskColor(b.risk_level)}`}>
                        {b.risk_level.toUpperCase()}
                      </Badge>
                    </div>
                  </div>

                  {/* Forecast + Trend */}
                  <div className="text-right">
                    <p className="font-bold text-sm">
                      {b.total_forecast.toLocaleString()}
                    </p>

                    <div 
                      title={b.trend_message}   // <-- Tooltip on hover
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
                  </div>
                </div>
              );
            })}
          </div>
        </ScrollArea>

        {/* Show More */}
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
