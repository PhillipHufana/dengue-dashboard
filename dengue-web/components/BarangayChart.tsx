// components/BarangayChart.tsx
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

function normalizeName(x: string): string {
  return x
    .toLowerCase()
    .replace(/\(.+?\)/g, "") // remove "(Pob.)"
    .replace(/-/g, " ")
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "") // remove accents
    .trim()
    .replace(/\s+/g, " ");
}

export default function BarangayChart({ name }: { name: string }) {
  const [series, setSeries] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (name) {
      const nm = normalizeName(name);
      setError(null);

      getBarangaySeries(nm)
        .then((res) => setSeries(res.series || []))
        .catch((err) => {
          console.error(err);
          setError("No data for this barangay");
        });
    }
  }, [name]);

  if (!name) return <div className="p-4 text-gray-600">Click a barangay on the map</div>;
  if (error) return <div className="p-4 text-red-600">{error}</div>;

  const labels = series.map((d) => d.week_start);
  const values = series.map((d) => d.final_forecast);

  return (
    <div className="p-4">
      <h2 className="text-lg font-semibold mb-2 text-gray-600">{name.toUpperCase()}</h2>
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
