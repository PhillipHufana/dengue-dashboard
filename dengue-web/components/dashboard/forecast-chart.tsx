"use client";

import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MapPin, Activity, TrendingUp } from "lucide-react";

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

import { useTimeseries } from "@/lib/query/useTimeseries";

interface ForecastChartProps {
  selectedBarangayName: string | null;
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload || !payload.length) return null;

  const p = payload[0].payload;

  return (
    <div className="rounded-lg border bg-background p-2 shadow-lg text-xs">
      <p className="font-semibold mb-1 border-b pb-1">{label}</p>

      {p.cases != null && (
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground flex items-center gap-1">
            <Activity className="h-3 w-3 text-emerald-500" /> Actual
          </span>
          <span className="font-medium text-emerald-500">{p.cases}</span>
        </div>
      )}

      <div className="flex items-center justify-between mt-1">
        <span className="text-muted-foreground flex items-center gap-1">
          <TrendingUp className="h-3 w-3 text-blue-400" /> Forecast
        </span>
        {p.forecast != null ? p.forecast.toFixed(2) : "—"}
      </div>

      {p.is_future && (
        <p className="mt-1 text-[10px] text-muted-foreground italic border-t pt-1">
          Forecast period
        </p>
      )}
    </div>
  );
}

export function ForecastChart({ selectedBarangayName }: ForecastChartProps) {
  const { data, isError, isLoading } = useTimeseries(selectedBarangayName);

  const series = data?.series ?? [];
  const locationName =
    selectedBarangayName ?? "City-Wide (All 182 Barangays)";
  const isBarangay = selectedBarangayName !== null;

  const forecastStartIndex = series.findIndex((d) => d.is_future);
  const forecastStartDate =
    forecastStartIndex > -1 ? series[forecastStartIndex].date : null;

  if (isLoading) return <div className="p-4">Loading chart...</div>;
  if (isError) return <div className="p-4 text-red-500">Failed to load timeseries.</div>;

  return (
    <Card className="bg-card border-border">
      <CardHeader className="p-4 pb-2">
        <div className="flex flex-col gap-2">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <CardTitle className="text-base font-semibold">
                Predictive Forecast
              </CardTitle>
              <Badge variant="secondary" className="text-[10px]">
                Weekly
              </Badge>
            </div>

            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-secondary/50 border">
              <MapPin
                className={`h-3 w-3 ${
                  isBarangay ? "text-primary" : "text-muted-foreground"
                }`}
              />
              <span
                className={`text-xs font-medium ${
                  isBarangay ? "text-primary" : "text-muted-foreground"
                }`}
              >
                {locationName}
              </span>
            </div>
          </div>

          {!isBarangay && (
            <p className="text-[10px] text-muted-foreground">
              Tap a barangay on the map to view its forecast
            </p>
          )}
        </div>
      </CardHeader>

      <CardContent className="p-4 pt-0">
        <div className="h-[240px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={series} margin={{ top: 10, left: -15, right: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />

              <XAxis
                dataKey="date"
                tick={{ fill: "#888", fontSize: 9 }}
                axisLine={{ stroke: "#333" }}
                tickLine={false}
                interval={19}
              />

              <YAxis
                tick={{ fill: "#888", fontSize: 9 }}
                axisLine={{ stroke: "#333" }}
                tickLine={false}
                width={35}
              />

              <Tooltip content={<CustomTooltip />} />

              {forecastStartDate && (
                <ReferenceLine
                  x={forecastStartDate}
                  stroke="#666"
                  strokeDasharray="5 5"
                  label={{
                    value: "Forecast",
                    position: "top",
                    fill: "#999",
                    fontSize: 10,
                  }}
                />
              )}

              {/* Actual */}
              <Line
                type="monotone"
                dataKey="cases"
                stroke="#10b981"
                strokeWidth={2}
                dot={false}
                name="Actual Cases"
                connectNulls={false}
              />

              {/* Forecast */}
              <Line
                type="monotone"
                dataKey="forecast"
                stroke="#60a5fa"
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
                name="Forecast"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Legend */}
        <div className="mt-3 flex justify-center gap-4 text-[10px]">
          <div className="flex items-center gap-2">
            <div className="h-0.5 w-5 bg-emerald-500" />
            <span className="text-muted-foreground">Actual</span>
          </div>
          <div className="flex items-center gap-2">
            <div
              className="h-0.5 w-5 bg-blue-400"
              style={{ borderBottom: "1px dashed #60a5fa" }}
            />
            <span className="text-muted-foreground">Forecast</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
