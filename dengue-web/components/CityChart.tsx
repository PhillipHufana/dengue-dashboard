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
import { getCitySeries } from "@/lib/api";
import { Line } from "react-chartjs-2";

export default function CityChart() {
  const [rows, setRows] = useState<any[]>([]);

  useEffect(() => {
    getCitySeries().then((data) => setRows(data || []));
  }, []);

  const labels = rows.map((d) => d.week_start);
  const values = rows.map((d) => d.city_cases);

  return (
    <div className="p-4">
      <h2 className="text-lg font-semibold mb-2">City Weekly Cases</h2>
      <Line
        data={{
          labels,
          datasets: [
            {
              label: "City Cases",
              data: values,
              borderColor: "#16a34a",
              backgroundColor: "rgba(22,163,74,0.4)",
            },
          ],
        }}
      />
    </div>
  );
}
