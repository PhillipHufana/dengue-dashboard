// components/BarangayChart.tsx
"use client";

import { useEffect, useState } from "react";
import { Line } from "react-chartjs-2";
import { getTimeseries } from "@/lib/api";
import {
  Chart as ChartJS,
  TimeScale,
  LineElement,
  PointElement,
  LinearScale,
  Tooltip,
  Legend,
} from "chart.js";
import "chartjs-adapter-date-fns";

ChartJS.register(TimeScale, LineElement, PointElement, LinearScale, Tooltip, Legend);

export default function BarangayChart({
  name,
  freq,
  model,
  rangeStart,
  rangeEnd,
  onSeriesLength,
}: {
  name: string;
  freq: "weekly" | "monthly" | "yearly";
  model: "preferred" | "final" | "hybrid" | "local";
  rangeStart: number;
  rangeEnd: number;
  onSeriesLength?: (len: number) => void;
}) {
  const [series, setSeries] = useState<any[]>([]);

  const rangeHighlightPlugin = {
    id: "rangeHighlight",
    beforeDraw(chart: any, _args: any, pluginOptions: any) {
      const { rangeStart, rangeEnd } = pluginOptions || {};
      if (rangeStart == null || rangeEnd == null) return;

      const { ctx, chartArea, scales } = chart;
      const xScale = scales.x;
      if (!chartArea || !xScale) return;

      const labels = chart.data?.labels || [];
      if (!labels.length) return;

      if (
        rangeStart < 0 ||
        rangeEnd < 0 ||
        rangeStart >= labels.length ||
        rangeEnd >= labels.length
      ) {
        return;
      }

      const left = xScale.getPixelForValue(labels[rangeStart]);
      const right = xScale.getPixelForValue(labels[rangeEnd]);

      ctx.save();
      ctx.fillStyle = "rgba(0,0,0,0.08)";
      ctx.fillRect(left, chartArea.top, right - left, chartArea.bottom - chartArea.top);
      ctx.restore();
    },
  };

  useEffect(() => {
    if (!name) return;

    getTimeseries("barangay", { name, freq, model })
      .then((data) => setSeries(data.series || []))
      .catch(console.error);
  }, [name, freq, model]);

  useEffect(() => {
    if (series.length > 0) {
      onSeriesLength?.(series.length);
    }
  }, [series, onSeriesLength]);

  if (!name) return <div className="p-4">Select a barangay on the map</div>;
  if (!series.length) return <div className="p-4">Loading data…</div>;

  const safeStart =
    series.length === 0 ? 0 : Math.max(0, Math.min(rangeStart, series.length - 1));
  const safeEnd =
    series.length === 0
      ? 0
      : Math.max(safeStart, Math.min(rangeEnd, series.length - 1));

  const sliced = series.slice(safeStart, safeEnd + 1);

  const totalCases = sliced.reduce((sum, x) => sum + (x.cases ?? 0), 0);
  const totalForecast = sliced.reduce((sum, x) => sum + (x.forecast ?? 0), 0);

  const labels = series.map((x) => new Date(x.date));
  const cases = series.map((x) => x.cases);
  const forecast = series.map((x) => x.forecast);

  return (
    <div className="p-4">
      <h2 className="font-semibold text-lg mb-2">
        {name.toUpperCase()} — {model} ({freq})
      </h2>

      <div className="text-sm text-gray-600 mb-3">
        Range: {series[safeStart]?.date} → {series[safeEnd]?.date}
        <br />
        <b>Total cases:</b> {totalCases.toFixed(1)} &nbsp; | &nbsp;
        <b>Total forecast:</b> {totalForecast.toFixed(1)}
      </div>

      <Line
        data={{
          labels,
          datasets: [
            {
              label: "Actual Cases",
              data: cases,
              borderColor: "#22c55e",
              backgroundColor: "rgba(34,197,94,0.2)",
              borderWidth: 2,
              pointRadius: 2,
              tension: 0.2,
            },
            {
              label: "Forecast",
              data: forecast,
              borderColor: "#2563eb",
              backgroundColor: "rgba(37,99,235,0.2)",
              borderWidth: 2,
              pointRadius: 2,
              tension: 0.2,
            },
          ],
        }}
        options={{
          responsive: true,
          plugins: {
            legend: { display: true },
            rangeHighlight: {
              rangeStart: safeStart,
              rangeEnd: safeEnd,
            },
          } as any,
          scales: {
            x: {
              type: "time",
              time: {
                unit:
                  freq === "weekly"
                    ? "week"
                    : freq === "monthly"
                    ? "month"
                    : "year",
              },
            },
            y: { beginAtZero: true },
          },
        }}
        plugins={[rangeHighlightPlugin]}
      />
    </div>
  );
}
