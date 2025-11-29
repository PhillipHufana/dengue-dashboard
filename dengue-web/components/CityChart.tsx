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
} from "chart.js";
import { Line } from "react-chartjs-2";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend
);

export default function CityChart({
  series,
  rangeStart,
  rangeEnd,
}: {
  series: any[];
  rangeStart: number;
  rangeEnd: number;
}) {
  if (!series || series.length === 0) {
    return <div className="p-4">No city data</div>;
  }

  const labels = series.map((d) => d.date);
  const values = series.map((d) => d.value ?? d.cases ?? 0);

  const safeStart = Math.max(0, Math.min(rangeStart, series.length - 1));
  const safeEnd = Math.max(safeStart, Math.min(rangeEnd, series.length - 1));

  // build a mask dataset to visually highlight the selected range
  const mask = values.map((v, idx) =>
    idx >= safeStart && idx <= safeEnd ? v : null
  );

  return (
    <div className="p-4">
      <h2 className="font-semibold text-lg mb-2">
        Citywide cases / forecast
      </h2>
      <Line
        data={{
          labels,
          datasets: [
            {
              label: "City value",
              data: values,
              borderColor: "#16a34a",
              backgroundColor: "rgba(22,163,74,0.2)",
              pointRadius: 0,
            },
            {
              label: "Selected range",
              data: mask,
              borderColor: "#2563eb",
              backgroundColor: "rgba(37,99,235,0.25)",
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
            x: { display: true },
            y: { display: true },
          },
        }}
      />
    </div>
  );
}
