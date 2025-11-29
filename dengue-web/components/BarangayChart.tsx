"use client";

import { useEffect, useState } from "react";
import { Line } from "react-chartjs-2";
import { getTimeseries } from "@/lib/api";

export default function BarangayChart({
  name,
  freq,
  model,
}: {
  name: string;
  freq: string;
  model: string;
}) {
  const [series, setSeries] = useState<any[]>([]);

  useEffect(() => {
    if (!name) return;
    getTimeseries("barangay", { name, freq: freq as any, model: model as any })
      .then((data) => setSeries(data.series || []))
      .catch(console.error);
  }, [name, freq, model]);

  if (!name)
    return <div className="p-4">Select a barangay on the map</div>;

  const labels = series.map((x) => x.date);
  const cases = series.map((x) => x.cases);
  const forecast = series.map((x) => x.forecast);

  return (
    <div className="p-4">
      <h2 className="font-semibold text-lg mb-2">
        {name.toUpperCase()} — {model} ({freq})
      </h2>

      <Line
        data={{
          labels,
          datasets: [
            {
              label: "Actual Cases",
              data: cases,
              borderColor: "#22c55e",
            },
            {
              label: "Forecast",
              data: forecast,
              borderColor: "#2563eb",
            },
          ],
        }}
      />
    </div>
  );
}
