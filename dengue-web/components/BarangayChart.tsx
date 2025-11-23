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

import { useEffect, useState } from "react";
import { getBarangaySeries } from "@/lib/api";
import { Line } from "react-chartjs-2";

export default function BarangayChart({ name }: { name: string }) {
  const [series, setSeries] = useState<any[]>([]);

  useEffect(() => {
    if (name) {
      getBarangaySeries(name).then((res) => setSeries(res.series || []));
    }
  }, [name]);

  if (!name) return <div className="p-4">Click a barangay on the map</div>;

  const labels = series.map((d) => d.week_start);
  const values = series.map((d) => d.final_forecast);

  return (
    <div className="p-4">
      <h2 className="text-lg font-semibold mb-2">{name.toUpperCase()}</h2>
      <Line
        data={{
          labels,
          datasets: [
            {
              label: "Forecast",
              data: values,
              borderColor: "#2563eb",
              backgroundColor: "rgba(37,99,235,0.3)",
            },
          ],
        }}
      />
    </div>
  );
}
