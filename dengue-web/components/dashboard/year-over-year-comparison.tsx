"use client";

import { useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useBarangaySeries, useCitySeries } from "@/lib/query/hooks";
import { useDashboardStore } from "@/lib/store/dashboard-store";
import { formatCases } from "@/lib/number-format";
import { humanizeName } from "@/lib/display-text";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface YearOverYearComparisonProps {
  selectedBarangay: { pretty: string; clean: string } | null;
}

type SeriesPoint = {
  date?: string;
  cases?: number | null;
  is_future?: boolean;
};

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
] as const;

const YEAR_COLORS = [
  "#67B99A",
  "#3085BE",
  "#EF6C00",
  "#F93716",
  "#7C3AED",
  "#8B5E3C",
  "#0F766E",
  "#BE185D",
  "#475569",
];

function ComparisonTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name?: string; value?: number | string; color?: string }>;
  label?: string | number;
}) {
  if (!active || !payload?.length) return null;

  return (
    <div className="rounded-lg border bg-background p-2 shadow-lg text-xs">
      <p className="font-semibold mb-1 border-b pb-1">{label}</p>
      {payload.map((item) => (
        <div key={String(item.name)} className="flex items-center justify-between gap-3 mt-1">
          <div className="flex items-center gap-2 text-muted-foreground">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: item.color ?? "#999" }}
            />
            <span>{item.name}</span>
          </div>
          <span className="font-medium">{formatCases(Number(item.value ?? 0))}</span>
        </div>
      ))}
    </div>
  );
}

export function YearOverYearComparison({ selectedBarangay }: YearOverYearComparisonProps) {
  const runId = useDashboardStore((s) => s.runId);
  const modelName = useDashboardStore((s) => s.modelName);
  const dataMode = useDashboardStore((s) => s.dataMode);
  const brgyName = selectedBarangay?.clean ?? null;

  const cityQuery = useCitySeries("weekly", runId, modelName, "future");
  const barangayQuery = useBarangaySeries(brgyName, "weekly", runId, modelName, "future");

  const isBarangay = !!brgyName;
  const isLoading = isBarangay ? barangayQuery.isLoading : cityQuery.isLoading;
  const isError = isBarangay ? barangayQuery.isError : cityQuery.isError;
  const rawSeries = useMemo(() => {
    if (isBarangay) return (barangayQuery.data?.series ?? []) as SeriesPoint[];
    return (cityQuery.data?.series ?? []) as SeriesPoint[];
  }, [isBarangay, barangayQuery.data?.series, cityQuery.data?.series]);

  const comparison = useMemo(() => {
    const observed = rawSeries.filter((row) => !row.is_future);
    if (!observed.length) return null;

    const monthlyByYear = new Map<number, number[]>();
    for (const row of observed) {
      const rawDate = String(row.date ?? "");
      const parsed = new Date(rawDate);
      if (Number.isNaN(parsed.getTime())) continue;
      const year = parsed.getFullYear();
      const month = parsed.getMonth();
      const arr = monthlyByYear.get(year) ?? Array.from({ length: 12 }, () => 0);
      arr[month] += Number(row.cases ?? 0);
      monthlyByYear.set(year, arr);
    }

    const years = [...monthlyByYear.keys()]
      .filter((year) => year !== 2016 && (monthlyByYear.get(year) ?? []).some((value) => value > 0))
      .sort((a, b) => b - a);
    if (!years.length) return null;

    const chartData = MONTHS.map((month, monthIndex) => {
      const point: Record<string, string | number> = { month };
      for (const year of years) {
        point[String(year)] = monthlyByYear.get(year)?.[monthIndex] ?? 0;
      }
      return point;
    });

    const totals = years.map((year) => ({
      year,
      total: (monthlyByYear.get(year) ?? []).reduce((sum, value) => sum + value, 0),
    }));

    return {
      years,
      totals,
      chartData,
    };
  }, [rawSeries]);
  const [selectedYears, setSelectedYears] = useState<number[] | null>(null);

  if (dataMode !== "observed") return null;

  if (isLoading) {
    return (
      <Card className="bg-card border-[#67B99A]">
        <CardHeader className="p-4 pb-2">
          <Skeleton className="h-5 w-56" />
        </CardHeader>
        <CardContent className="p-4 pt-0">
          <Skeleton className="h-80 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (isError || !comparison) {
    return (
      <Card className="bg-card border-[#67B99A]">
        <CardHeader className="p-4 pb-2">
          <CardTitle className="text-base font-semibold">Year-to-Year Observed Comparison</CardTitle>
        </CardHeader>
        <CardContent className="p-4 pt-0 text-sm text-muted-foreground">
          Not enough observed weekly history to compute a year-to-year comparison.
        </CardContent>
      </Card>
    );
  }

  const locationLabel = isBarangay ? humanizeName(selectedBarangay?.pretty ?? "") : "City Wide";
  const visibleYears =
    selectedYears === null
      ? comparison.years
      : selectedYears.filter((year) => comparison.years.includes(year));
  const visibleTotals = comparison.totals.filter((item) => visibleYears.includes(item.year));

  const toggleYear = (year: number) => {
    setSelectedYears((current) => {
      const base = current === null ? comparison.years : current;
      if (base.includes(year)) return base.filter((item) => item !== year);
      return [...base, year].sort((a, b) => b - a);
    });
  };

  return (
    <Card className="bg-card border-[#67B99A]">
      <CardHeader className="p-4 pb-2">
        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
          <CardTitle className="text-base font-semibold">Observed Monthly Comparison by Year</CardTitle>
          <Badge variant="secondary" className="w-fit bg-[#88D4AB] text-[#1F5F46] dark:bg-[#67B99A]/30 dark:text-[#BFEFD0]">
            {locationLabel}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          Monthly observed cases compared year by year, with January to December on the x-axis.
        </p>
      </CardHeader>
      <CardContent className="p-4 pt-0 space-y-4">
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant={visibleYears.length === comparison.years.length ? "default" : "outline"}
            className="h-8 text-xs"
            onClick={() =>
              setSelectedYears((current) =>
                current === null || current.length === comparison.years.length ? [] : null,
              )
            }
          >
            All Years
          </Button>
          {comparison.years.map((year) => (
            <Button
              key={year}
              size="sm"
              variant={visibleYears.includes(year) ? "default" : "outline"}
              className="h-8 text-xs"
              onClick={() => toggleYear(year)}
            >
              {year}
            </Button>
          ))}
        </div>

        <div className="flex flex-wrap gap-2">
          {visibleTotals.map((item) => {
            const colorIndex = comparison.years.indexOf(item.year);
            return (
            <div
              key={item.year}
              className="rounded-lg border border-border bg-secondary/30 px-3 py-2 text-xs"
            >
              <div className="flex items-center gap-2">
                <span
                  className="inline-block h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: YEAR_COLORS[colorIndex % YEAR_COLORS.length] }}
                />
                <span className="font-medium">{item.year}</span>
              </div>
              <div className="mt-1 text-muted-foreground">Total: {formatCases(item.total)}</div>
            </div>
          )})}
        </div>

        <div className="h-80 w-full">
          {visibleYears.length ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={comparison.chartData} margin={{ top: 12, right: 12, left: -12, bottom: 18 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#d4d4d8" vertical={false} />
              <XAxis
                dataKey="month"
                tick={{ fill: "#71717a", fontSize: 10 }}
                axisLine={{ stroke: "#d4d4d8" }}
                tickLine={false}
                interval={0}
                angle={-20}
                textAnchor="end"
                height={50}
              />
              <YAxis
                tick={{ fill: "#71717a", fontSize: 10 }}
                axisLine={{ stroke: "#d4d4d8" }}
                tickLine={false}
                width={40}
              />
              <Tooltip content={<ComparisonTooltip />} />
              {comparison.years
                .filter((year) => visibleYears.includes(year))
                .map((year, index) => {
                  const colorIndex = comparison.years.indexOf(year);
                  return (
                <Line
                  key={year}
                  type="monotone"
                  dataKey={String(year)}
                  name={String(year)}
                  stroke={YEAR_COLORS[colorIndex % YEAR_COLORS.length]}
                  strokeWidth={index === 0 ? 2.75 : 2}
                  strokeDasharray={index >= 3 ? "4 4" : undefined}
                  dot={false}
                />
              )})}
            </LineChart>
          </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center rounded-lg border border-dashed border-border text-sm text-muted-foreground">
              No years selected.
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
