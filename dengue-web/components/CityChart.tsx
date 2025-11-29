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

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend
);

import { Line } from "react-chartjs-2";

export default function CityChart({
  series,
  timeIndex,
}: {
  series: any[];
  timeIndex: number;
}) {
  if (!series || series.length === 0)
    return <div className="p-4">Loading city trends…</div>;

  const labels = series.map((x) => x.date);
  const cases = series.map((x) => x.cases);
  const forecast = series.map((x) => x.forecast);

  return (
    <div className="p-4">
      <h2 className="font-semibold text-lg mb-2">Citywide Cases + Forecast</h2>

      <Line
        data={{
          labels,
          datasets: [
            {
              label: "Actual Cases",
              data: cases,
              borderColor: "#16a34a",
            },
            {
              label: "Forecast",
              data: forecast,
              borderColor: "#ef4444",
            },
          ],
        }}
      />
    </div>
  );
}
