"use client";

import { useState, useMemo } from "react";
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

import {
  TrendingUp,
  Search,
  MapPin,
  AlertTriangle,
  ChevronUp,
  ChevronDown,
} from "lucide-react";

import { useSummary } from "@/lib/query/hooks";
import { cleanName } from "./choropleth-map";

interface ForecastRankingsProps {
  selectedBarangay: { pretty: string; clean: string } | null;
  onBarangaySelect: (value: { pretty: string; clean: string } | null) => void;
}

interface BarangayLatest {
  name: string;
  forecast: number | null;
  week_start: string;
  risk_level: "low" | "medium" | "high" | "critical" | "unknown";
}

interface RankedBarangay {
  pretty: string;
  clean: string;
  riskLevel: string;
  totalCases: number;
  dailyAverage: number;
  trendPercent: number;
}

type TimePeriod = "1w" | "2w" | "1m" | "3m";

const timePeriodLabels: Record<TimePeriod, string> = {
  "1w": "1 Week",
  "2w": "2 Weeks",
  "1m": "1 Month",
  "3m": "3 Months",
};

const periodMultiplier: Record<TimePeriod, number> = {
  "1w": 1,
  "2w": 2,
  "1m": 4,
  "3m": 12,
};

export function ForecastRankings({
  selectedBarangay,
  onBarangaySelect,
}: ForecastRankingsProps) {
  const { data, isLoading } = useSummary();

  const [timePeriod, setTimePeriod] = useState<TimePeriod>("1m");
  const [searchQuery, setSearchQuery] = useState("");
  const [showAll, setShowAll] = useState(false);

  const barangays: BarangayLatest[] = data?.barangay_latest ?? [];

  // -----------------------------------------------------------
  // 🔍 FILTER + RANKING (TYPED)
  // -----------------------------------------------------------

  const ranked: RankedBarangay[] = useMemo(() => {
    if (!barangays.length) return [];

    const multiplier = periodMultiplier[timePeriod];

    return barangays
      .map((b: BarangayLatest): RankedBarangay => {
        const forecast = b.forecast ?? 0;

        const totalCases = forecast * multiplier;
        const dailyAverage = Number((forecast / 7).toFixed(1));

        const trendPercent =
          forecast > 0 ? Math.round(((forecast - forecast * 0.8) / (forecast * 0.8)) * 100) : 0;

        return {
          pretty: b.name.replace(/\b\w/g, (c) => c.toUpperCase()),
          clean: cleanName(b.name),
          riskLevel: b.risk_level,
          totalCases,
          dailyAverage,
          trendPercent,
        };
      })
      .sort((a: RankedBarangay, b: RankedBarangay) => b.totalCases - a.totalCases);
  }, [barangays, timePeriod]);

  const filtered = useMemo(() => {
    return ranked.filter((b: RankedBarangay) =>
      b.pretty.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [ranked, searchQuery]);

  const displayed = showAll ? filtered : filtered.slice(0, 10);

  // -----------------------------------------------------------
  // COLORS
  // -----------------------------------------------------------

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
      <Card className="bg-card border-border p-4">
        <div>Loading rankings...</div>
      </Card>
    );
  }

  return (
    <Card className="bg-card border-border">
      <CardHeader className="p-3 pb-2 md:p-6 md:pb-3">
        <div className="flex flex-col gap-3">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-primary" />
              <CardTitle className="text-base md:text-lg font-semibold">
                Forecast Rankings
              </CardTitle>
            </div>
          </div>

          <Tabs value={timePeriod} onValueChange={(v) => setTimePeriod(v as TimePeriod)}>
            <TabsList className="grid grid-cols-4 w-full h-8">
              {(Object.keys(timePeriodLabels) as TimePeriod[]).map((p) => (
                <TabsTrigger key={p} value={p} className="text-[10px] md:text-xs">
                  {p.toUpperCase()}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="Search barangay..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 h-8 text-xs bg-secondary/50"
            />
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-3 pt-0 md:p-6 md:pt-0">
        <ScrollArea className="h-80 md:h-[400px]">
          <div className="space-y-2">
            {displayed.map((b: RankedBarangay, index: number) => {
              const rank =
                ranked.findIndex((x: RankedBarangay) => x.clean === b.clean) + 1;
              const isSelected = selectedBarangay?.clean === b.clean;

              return (
                <div
                  key={b.clean}
                  onClick={() =>
                    onBarangaySelect(
                      isSelected ? null : { pretty: b.pretty, clean: b.clean }
                    )
                  }
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
                    <div className="flex items-center gap-1.5">
                      <p className="font-medium text-sm truncate">{b.pretty}</p>
                      {isSelected && <MapPin className="h-3 w-3 text-primary" />}
                    </div>

                    <div className="flex items-center gap-2 mt-1">
                      <Badge
                        variant="outline"
                        className={`text-[9px] ${getRiskColor(b.riskLevel)}`}
                      >
                        {b.riskLevel.toUpperCase()}
                      </Badge>
                      <span className="text-[10px] text-muted-foreground">
                        ~{b.dailyAverage}/day
                      </span>
                    </div>
                  </div>

                  <div className="text-right">
                    <p className="font-bold text-sm">
                      {b.totalCases.toLocaleString()}
                    </p>

                    <div
                      className={`flex items-center justify-end gap-1 text-[10px] ${
                        b.trendPercent > 0
                          ? "text-red-400"
                          : b.trendPercent < 0
                          ? "text-green-400"
                          : "text-muted-foreground"
                      }`}
                    >
                      {b.trendPercent > 0 ? (
                        <ChevronUp className="h-3 w-3" />
                      ) : b.trendPercent < 0 ? (
                        <ChevronDown className="h-3 w-3" />
                      ) : null}
                      {Math.abs(b.trendPercent)}%
                    </div>
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
            {showAll
              ? "Show Top 10"
              : `Show All ${filtered.length} Barangays`}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
