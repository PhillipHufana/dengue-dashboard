"use client";

import { useState, useEffect } from "react";
import SummaryCards from "@/components/SummaryCards";
import MapView from "@/components/MapView";
import BarangayChart from "@/components/BarangayChart";
import CityChart from "@/components/CityChart";
import { getTimeseries } from "@/lib/api";

export default function Dashboard() {
  const [selectedBarangay, setSelectedBarangay] = useState<string>("");

  // Global control state
  const [freq, setFreq] = useState<"weekly" | "monthly" | "yearly">("weekly");
  const [model, setModel] = useState<"preferred" | "final" | "hybrid" | "local">(
    "preferred"
  );

  // Global city-level timeseries (for both map coloring & city chart)
  const [citySeries, setCitySeries] = useState<any[]>([]);
  const [timeIndex, setTimeIndex] = useState(0);

  // Load city timeseries whenever freq/model changes
  useEffect(() => {
    getTimeseries("city", { freq, model })
      .then((data) => {
        setCitySeries(data.series || []);
        setTimeIndex((i) =>
          i < data.series.length ? i : data.series.length - 1
        );
      })
      .catch(console.error);
  }, [freq, model]);

  const currentDate =
    citySeries.length > 0 ? citySeries[timeIndex]?.date : null;

  return (
    <div className="h-screen w-screen flex flex-col">

      {/* TOP SUMMARY */}
      <SummaryCards />

      {/* Controls */}
      <div className="flex items-center gap-4 p-3 border-b bg-white">
        {/* Frequency */}
        <select
          className="border p-2 rounded"
          value={freq}
          onChange={(e) => setFreq(e.target.value as any)}
        >
          <option value="weekly">Weekly</option>
          <option value="monthly">Monthly</option>
          <option value="yearly">Yearly</option>
        </select>

        {/* Forecast Model */}
        <select
          className="border p-2 rounded"
          value={model}
          onChange={(e) => setModel(e.target.value as any)}
        >
          <option value="preferred">Preferred</option>
          <option value="final">Final Only</option>
          <option value="hybrid">Hybrid</option>
          <option value="local">Local</option>
        </select>

        {/* Time slider */}
        {citySeries.length > 0 && (
          <input
            type="range"
            min={0}
            max={citySeries.length - 1}
            value={timeIndex}
            onChange={(e) => setTimeIndex(Number(e.target.value))}
            className="w-64"
          />
        )}

        <div className="text-sm text-zinc-600">
          {currentDate ? `Selected: ${currentDate}` : ""}
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* LEFT MAP */}
        <div className="w-1/2 border-r overflow-hidden">
          <MapView
            onSelect={setSelectedBarangay}
            freq={freq}
            model={model}
            timeIndex={timeIndex}
            citySeries={citySeries}
          />

        </div>

        {/* RIGHT CHART PANEL */}
        <div className="w-1/2 overflow-y-auto bg-zinc-50">
          <BarangayChart
            name={selectedBarangay}
            freq={freq}
            model={model}
          />
          <CityChart
            series={citySeries}
            timeIndex={timeIndex}
          />
        </div>
      </div>
    </div>
  );
}
