"use client";

import { useEffect, useState, useMemo } from "react";
import { Line } from "react-chartjs-2";
import { getTimeseries } from "@/lib/api";

export default function BarangayChart({
  name,
  freq,
  model,
  rangeStart,
  rangeEnd,
}: {
  name: string;
  freq: "weekly" | "monthly" | "yearly";
  model: "preferred" | "final" | "hybrid" | "local";
  rangeStart: number;
  rangeEnd: number;
}) {
  const [series, setSeries] = useState<any[]>([]);

  const rangeHighlightPlugin = {
    id: "rangeHighlight",
    beforeDraw(chart: any, args: any, pluginOptions: any) {
      const { rangeStart, rangeEnd } = pluginOptions || {};
      if (rangeStart == null || rangeEnd == null) return;

      const { ctx, chartArea, scales } = chart;
      const xScale = scales.x;

      if (!chartArea || !xScale) return;

      const left = xScale.getPixelForValue(rangeStart);
      const right = xScale.getPixelForValue(rangeEnd);

      ctx.save();
      ctx.fillStyle = "rgba(0,0,0,0.08)";
      ctx.fillRect(left, chartArea.top, right - left, chartArea.bottom - chartArea.top);
      ctx.restore();
    },
  };





  // -----------------------------------------------------
  // Load FULL barangay series
  // -----------------------------------------------------
  useEffect(() => {
    if (!name) return;

    getTimeseries("barangay", { name, freq, model })
      .then((data) => setSeries(data.series || []))
      .catch(console.error);
  }, [name, freq, model]);

  if (!name)
    return <div className="p-4">Select a barangay on the map</div>;

  if (!series.length)
    return <div className="p-4">Loading data…</div>;

  // -----------------------------------------------------
  // Slice range
  // -----------------------------------------------------
  const sliced = series.slice(rangeStart, rangeEnd + 1);

  const totalCases = sliced.reduce(
    (sum, x) => sum + (x.cases ?? 0), 
    0
  );
  const totalForecast = sliced.reduce(
    (sum, x) => sum + (x.forecast ?? 0), 
    0
  );

  const labels = series.map((x) => x.date);
  const cases = series.map((x) => x.cases);
  const forecast = series.map((x) => x.forecast);

  // -----------------------------------------------------
  // Range shading FIX — use a "baseline difference" line
  // This avoids bar datasets completely
  // -----------------------------------------------------
  const highlightValues = series.map((_, idx) =>
    idx >= rangeStart && idx <= rangeEnd ? 1 : null
  );

  return (
    <div className="p-4">
      <h2 className="font-semibold text-lg mb-2">
        {name.toUpperCase()} — {model} ({freq})
      </h2>

      <div className="text-sm text-gray-600 mb-3">
        Range: {series[rangeStart]?.date} → {series[rangeEnd]?.date}
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
              rangeStart,
              rangeEnd,
            },
          } as any,


          scales: {
            x: { beginAtZero: false },
            y: { beginAtZero: true },
          },
        }}
        plugins={[rangeHighlightPlugin]}
      />



    </div>
  );
}
