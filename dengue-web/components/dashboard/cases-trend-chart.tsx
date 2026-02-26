"use client";

import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Area, AreaChart, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { useCitySeries } from "@/lib/query/hooks";
import { useDashboardStore } from "@/lib/store/dashboard-store";

function CustomTooltip({ active, payload, label }: any) {
  if (active && payload && payload.length) {
    return (
      <div className="rounded-lg border border-border bg-background p-3 shadow-md">
        <p className="mb-2 text-sm font-medium">{label}</p>
        {payload.map((entry: any, index: number) => (
          <p key={index} className="text-sm" style={{ color: entry.color }}>
            {entry.dataKey === "cases" ? "Actual" : "Forecast"}: {Number(entry.value ?? 0).toLocaleString()}
          </p>
        ))}
      </div>
    );
  }
  return null;
}

export function CasesTrendChart() {
  const runId = useDashboardStore((s) => s.runId);
  const modelName = useDashboardStore((s) => s.modelName);
  const horizonType = useDashboardStore((s) => s.horizonType);
  const freq = useDashboardStore((s) => s.freq);

  const { data, isLoading } = useCitySeries(freq, runId, modelName, horizonType);

  const chartData = useMemo(() => {
    const series = data?.series ?? [];
    return series.map((d: any) => ({
      date: d.date,
      cases: d.cases ?? null,
      forecast: d.forecast ?? null,
    }));
  }, [data]);

  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold">Cases Trend</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-[320px] w-full">
          {isLoading ? (
            <div className="h-full w-full flex items-center justify-center text-sm text-muted-foreground">
              Loading…
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: "#888", fontSize: 12 }} axisLine={{ stroke: "#333" }} tickLine={false} />
                <YAxis tick={{ fill: "#888", fontSize: 12 }} axisLine={{ stroke: "#333" }} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="cases" strokeWidth={2} />
                <Area type="monotone" dataKey="forecast" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </CardContent>
    </Card>
  );
}