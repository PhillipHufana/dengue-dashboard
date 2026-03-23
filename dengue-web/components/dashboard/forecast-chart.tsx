"use client";

import { useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MapPin, Activity, TrendingUp } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { useBarangaySeries, useCityCompareSeries } from "@/lib/query/hooks";
import { useDashboardStore } from "@/lib/store/dashboard-store";
import { Button } from "@/components/ui/button";
import { ButtonGroup } from "@/components/ui/button-group";
import { formatCaseRange, formatCases } from "@/lib/number-format";
import { formatDateRange, humanizeName } from "@/lib/display-text";
import {
  LineChart,
  Line,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from "recharts";

interface ForecastChartProps {
  selectedBarangay: { pretty: string; clean: string } | null;
}

function CustomTooltip({
  active,
  payload,
  label,
  mode,
}: {
  active?: boolean;
  payload?: Array<{ payload?: Record<string, number | string | boolean | null | undefined> }>;
  label?: string;
  mode: "observed" | "forecast";
}) {
  if (!active || !payload || !payload.length) return null;
  const row = (payload[0]?.payload ?? {}) as Record<string, number | string | boolean | null | undefined>;

  const isCityCompare = mode === "forecast" && (row.yhat_prophet !== undefined || row.yhat_arima !== undefined);

  return (
    <div className="rounded-lg border bg-background p-2 shadow-lg text-xs">
      <p className="font-semibold mb-1 border-b pb-1">{label}</p>

      {row.cases != null && (
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground flex items-center gap-1">
            <Activity className="h-3 w-3 text-emerald-500" /> Actual
          </span>
          <span className="font-medium text-emerald-500">{formatCases(row.cases)}</span>
        </div>
      )}

      {isCityCompare ? (
        <>
          <div className="flex items-center justify-between mt-1">
            <span className="text-muted-foreground flex items-center gap-1">
              <TrendingUp className="h-3 w-3 text-blue-500" /> Prophet
            </span>
            <span>{row.yhat_prophet != null ? formatCases(row.yhat_prophet) : "-"}</span>
          </div>
          {row.yhat_prophet_lower != null || row.yhat_prophet_upper != null ? (
            <div className="text-[10px] text-muted-foreground">
              Range: {formatCaseRange(row.yhat_prophet_lower, row.yhat_prophet_upper)}
            </div>
          ) : null}
          <div className="flex items-center justify-between mt-1">
            <span className="text-muted-foreground flex items-center gap-1">
              <TrendingUp className="h-3 w-3 text-violet-400" /> ARIMA
            </span>
            <span>{row.yhat_arima != null ? formatCases(row.yhat_arima) : "-"}</span>
          </div>
          {row.yhat_arima_lower != null || row.yhat_arima_upper != null ? (
            <div className="text-[10px] text-muted-foreground">
              Range: {formatCaseRange(row.yhat_arima_lower, row.yhat_arima_upper)}
            </div>
          ) : null}
        </>
      ) : (
        <div className="flex items-center justify-between mt-1">
          <span className="text-muted-foreground flex items-center gap-1">
            <TrendingUp className="h-3 w-3 text-blue-400" /> Forecast
          </span>
          <span>{row.forecast != null ? formatCases(row.forecast) : "-"}</span>
        </div>
      )}

      {row.is_future ? (
        <p className="mt-1 text-[10px] text-muted-foreground italic border-t pt-1">Forecast period</p>
      ) : null}
    </div>
  );
}

export function ForecastChart({ selectedBarangay }: ForecastChartProps) {
  const runId = useDashboardStore((s) => s.runId);
  const modelName = useDashboardStore((s) => s.modelName);
  const horizonType = useDashboardStore((s) => s.horizonType);
  const freq = useDashboardStore((s) => s.freq);
  const riskMetric = useDashboardStore((s) => s.riskMetric);
  const dataMode = useDashboardStore((s) => s.dataMode);
  const brgyName = selectedBarangay?.clean ?? null;
  const [view, setView] = useState<"focused" | "full">("focused");

  const barangayQuery = useBarangaySeries(brgyName, freq, runId, modelName, horizonType);
  const cityCompareQuery = useCityCompareSeries(runId, !brgyName);

  const isCityView = !brgyName;
  const isLoading = isCityView ? cityCompareQuery.isLoading : barangayQuery.isLoading;
  const isError = isCityView ? cityCompareQuery.isError : barangayQuery.isError;
  const series = useMemo(() => {
    if (isCityView) return cityCompareQuery.data?.series ?? [];
    return barangayQuery.data?.series ?? [];
  }, [isCityView, cityCompareQuery.data?.series, barangayQuery.data?.series]);

  const displaySeries = useMemo(() => {
    const baseSeries = dataMode === "observed" ? series.filter((d: { is_future?: boolean }) => !d.is_future) : series;
    if (view === "full") return baseSeries;
    const historyCount = freq === "weekly" ? 16 : freq === "monthly" ? 12 : 10;
    const idx = baseSeries.findIndex((d: { is_future?: boolean }) => !!d.is_future);
    if (idx < 0) return baseSeries.slice(-historyCount);
    const start = Math.max(0, idx - historyCount);
    return baseSeries.slice(start);
  }, [series, view, freq, dataMode]);

  const locationName = humanizeName(selectedBarangay?.pretty ?? "City Wide");
  const isBarangay = selectedBarangay !== null;

  const freqLabel = {
    weekly: "Weekly",
    monthly: "Monthly",
    yearly: "Yearly",
  }[freq];

  const forecastStartIndex = series.findIndex((d: { is_future?: boolean }) => !!d.is_future);
  const forecastStartDate = forecastStartIndex > -1 ? (series[forecastStartIndex] as { date?: string }).date ?? null : null;
  const rangeLabel = useMemo(() => {
    if (!displaySeries.length) return null;
    const start = String((displaySeries[0] as { date?: string }).date ?? "");
    const end = String((displaySeries[displaySeries.length - 1] as { date?: string }).date ?? "");
    return formatDateRange(start, end);
  }, [displaySeries]);

  const modeSubtitle = dataMode === "observed"
    ? `Observed cases${rangeLabel ? `: ${rangeLabel}` : ""}`
    : isCityView
    ? `Forecasted and observed city series${rangeLabel ? `: ${rangeLabel}` : ""}`
    : riskMetric === "action_priority"
    ? `Forecasted action priority context${rangeLabel ? `: ${rangeLabel}` : ""}`
    : riskMetric === "cases"
    ? `Forecasted cases${rangeLabel ? `: ${rangeLabel}` : ""}`
    : riskMetric === "incidence"
    ? `Forecasted incidence${rangeLabel ? `: ${rangeLabel}` : ""}`
    : `Forecasted surge${rangeLabel ? `: ${rangeLabel}` : ""}`;

  if (isLoading) {
    return (
      <Card className="bg-card border-border">
        <CardHeader className="p-4 pb-2">
          <div className="flex flex-col gap-2">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-4 w-12 rounded-full" />
              </div>
              <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-secondary/50 border">
                <Skeleton className="h-3 w-3 rounded-full" />
                <Skeleton className="h-3 w-32" />
              </div>
            </div>
            <Skeleton className="h-3 w-40" />
          </div>
        </CardHeader>

        <CardContent className="p-4 pt-0">
          <div className="h-60 w-full">
            <Skeleton className="w-full h-full" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (isError) return <div className="p-4 text-red-500">Failed to load timeseries.</div>;

  return (
    <Card className={dataMode === "observed" ? "bg-card border-[#67B99A]" : "bg-card border-blue-300"}>
      <CardHeader className="p-4 pb-2">
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <Badge variant="secondary" className="text-[10px]">
              {freqLabel}
            </Badge>
            <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-secondary/50 border max-w-[62%]">
              <MapPin className={`h-3 w-3 ${isBarangay ? "text-primary" : "text-muted-foreground"}`} />
              <span className={`text-xs font-medium ${isBarangay ? "text-primary" : "text-muted-foreground"}`}>
                {locationName}
              </span>
            </div>
          </div>

          <div className="flex flex-col gap-2 min-[420px]:flex-row min-[420px]:items-center min-[420px]:justify-between">
            <CardTitle className="text-base font-semibold">{dataMode === "observed" ? "Observed Cases" : "Forecasted Cases"}</CardTitle>

            <ButtonGroup className="w-fit">
              <Button
                size="sm"
                className="h-8 px-3 text-xs font-medium rounded-r-none"
                variant={view === "focused" ? "default" : "outline"}
                onClick={() => setView("focused")}
              >
                Focused
              </Button>
              <Button
                size="sm"
                className="h-8 px-3 text-xs font-medium rounded-l-none border-l-0"
                variant={view === "full" ? "default" : "outline"}
                onClick={() => setView("full")}
              >
                Full
              </Button>
            </ButtonGroup>
          </div>

          {!isBarangay && dataMode === "forecast" ? <p className="text-[10px] text-muted-foreground">City chart shows both model estimates for comparison</p> : null}
          <p className="text-[10px] text-muted-foreground">{modeSubtitle}</p>
        </div>
      </CardHeader>

      <CardContent className="p-4 pt-0">
        <div className="h-60 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={displaySeries} margin={{ top: 10, left: -15, right: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: "#888", fontSize: 9 }} axisLine={{ stroke: "#333" }} tickLine={false} interval={19} />
              <YAxis tick={{ fill: "#888", fontSize: 9 }} axisLine={{ stroke: "#333" }} tickLine={false} width={35} />
              <Tooltip content={<CustomTooltip mode={dataMode} />} />

              {dataMode === "forecast" && forecastStartDate ? (
                <ReferenceLine
                  x={forecastStartDate}
                  stroke="#666"
                  strokeDasharray="5 5"
                  label={{ value: "Forecast", position: "top", fill: "#999", fontSize: 10 }}
                />
              ) : null}

              <Line type="monotone" dataKey="cases" stroke="#10b981" strokeWidth={2} dot={false} name="Actual Cases" connectNulls={false} />

              {isCityView && dataMode === "forecast" ? (
                <>
                  <Line type="monotone" dataKey="yhat_prophet" stroke="#3b82f6" strokeWidth={2} dot={false} name="Prophet" connectNulls />
                  <Line type="monotone" dataKey="yhat_prophet_lower" stroke="#93c5fd" strokeWidth={1} dot={false} strokeDasharray="3 3" name="Prophet CI Lower" connectNulls />
                  <Line type="monotone" dataKey="yhat_prophet_upper" stroke="#93c5fd" strokeWidth={1} dot={false} strokeDasharray="3 3" name="Prophet CI Upper" connectNulls />
                  <Line type="monotone" dataKey="yhat_arima" stroke="#a78bfa" strokeWidth={2} dot={false} strokeDasharray="4 3" name="ARIMA" connectNulls />
                  <Line type="monotone" dataKey="yhat_arima_lower" stroke="#c4b5fd" strokeWidth={1} dot={false} strokeDasharray="2 2" name="ARIMA CI Lower" connectNulls />
                  <Line type="monotone" dataKey="yhat_arima_upper" stroke="#c4b5fd" strokeWidth={1} dot={false} strokeDasharray="2 2" name="ARIMA CI Upper" connectNulls />
                </>
              ) : dataMode === "forecast" ? (
                <Line type="monotone" dataKey="forecast" stroke="#60a5fa" strokeWidth={2} strokeDasharray="4 4" dot={false} name="Forecast" connectNulls />
              ) : null}
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="mt-3 flex flex-wrap justify-center gap-4 text-[10px]">
          <div className="flex items-center gap-2">
            <div className="h-0.5 w-5 bg-emerald-500" />
            <span className="text-muted-foreground">Actual</span>
          </div>
          {isCityView && dataMode === "forecast" ? (
            <>
              <div className="flex items-center gap-2">
                <div className="h-0.5 w-5 bg-blue-500" />
                <span className="text-muted-foreground">Prophet</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-0.5 w-5 bg-blue-300" />
                <span className="text-muted-foreground">Prophet CI</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-0.5 w-5 bg-violet-400" style={{ borderBottom: "1px dashed #a78bfa" }} />
                <span className="text-muted-foreground">ARIMA</span>
              </div>
            </>
          ) : dataMode === "forecast" ? (
            <div className="flex items-center gap-2">
              <div className="h-0.5 w-5 bg-blue-400" style={{ borderBottom: "1px dashed #60a5fa" }} />
              <span className="text-muted-foreground">Forecast</span>
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
