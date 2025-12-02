// components/CityChart.tsx
"use client";

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  TimeScale,
} from "chart.js";
import { Line } from "react-chartjs-2";
import "chartjs-adapter-date-fns";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  TimeScale
);

export default function CityChart({
  series,
  rangeStart,
  rangeEnd,
  freq,
}: {
  series: any[];
  rangeStart: number;
  rangeEnd: number;
  freq: "weekly" | "monthly" | "yearly";
}) {
  if (!series || series.length === 0) {
    return <div className="p-4">No city data</div>;
  }

  const labels = series.map((d) => new Date(d.date));

  const safeStart = Math.max(0, Math.min(rangeStart, series.length - 1));
  const safeEnd = Math.max(safeStart, Math.min(rangeEnd, series.length - 1));

  const cases = series.map((d) => d.cases ?? null);
  const forecast = series.map((d) => d.forecast ?? null);

  const values = series.map((d) => d.cases ?? d.forecast ?? 0);

  const mask = values.map((v: number, idx: number) =>
    idx >= safeStart && idx <= safeEnd ? v : null
  );

  return (
    <div className="p-4">
      <h2 className="font-semibold text-lg mb-2">Citywide cases / forecast</h2>
      <Line
        data={{
          labels,
          datasets: [
            {
              label: "Actual Cases",
              data: cases,
              borderColor: "#16a34a",
              backgroundColor: "rgba(22,163,74,0.2)",
              pointRadius: 0,
            },
            {
              label: "Forecast",
              data: forecast,
              borderColor: "#2563eb",
              backgroundColor: "rgba(37,99,235,0.25)",
              pointRadius: 0,
            },
            {
              label: "Selected Range",
              data: mask,
              borderColor: "#f97316",
              backgroundColor: "rgba(249,115,22,0.3)",
              pointRadius: 0,
            },
          ],
        }}
        options={{
          responsive: true,
          plugins: {
            legend: {
              display: true,
            },
          },
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
      />
    </div>
  );
}
