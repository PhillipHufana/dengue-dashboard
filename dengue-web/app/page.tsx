// app/page.tsx
"use client";

import { useState, useEffect } from "react";
import SummaryCards from "@/components/SummaryCards";
import MapView from "@/components/MapView";
import BarangayChart from "@/components/BarangayChart";
import CityChart from "@/components/CityChart";
import { getTimeseries } from "@/lib/api";

export default function Dashboard() {
  const [selectedBarangay, setSelectedBarangay] = useState<string>("");
  const [barangayLength, setBarangayLength] = useState(0);

  // global controls
  const [freq, setFreq] = useState<"weekly" | "monthly" | "yearly">("weekly");
  const [model, setModel] = useState<"preferred" | "final" | "hybrid" | "local">(
    "preferred"
  );

  const [citySeries, setCitySeries] = useState<any[]>([]);

  // range = [startIndex, endIndex]
  const [rangeStart, setRangeStart] = useState(0);
  const [rangeEnd, setRangeEnd] = useState(0);

  // load city time series whenever freq/model changes
  useEffect(() => {
    getTimeseries("city", { freq, model })
      .then((data) => {
        const series = data.series || [];
        setCitySeries(series);

        if (series.length === 0) {
          setRangeStart(0);
          setRangeEnd(0);
        } else {
          setRangeStart(0);
          setRangeEnd(series.length - 1);
        }
      })
      .catch(console.error);
  }, [freq, model]);

  const safeStart =
    citySeries.length === 0 ? 0 : Math.max(0, Math.min(rangeStart, citySeries.length - 1));
  const safeEnd =
    citySeries.length === 0
      ? 0
      : Math.max(safeStart, Math.min(rangeEnd, citySeries.length - 1));

  const startDate =
    citySeries.length > 0 ? citySeries[safeStart]?.date : null;
  const endDate =
    citySeries.length > 0 ? citySeries[safeEnd]?.date : null;

  return (
    <div className="h-screen w-screen flex flex-col">
      {/* TOP SUMMARY */}
      <SummaryCards />

      {/* CONTROLS */}
      <div className="flex flex-wrap items-center gap-4 p-3 border-b bg-white">
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

        {/* Model */}
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

        {/* RANGE SLIDER (two thumbs) */}
        {citySeries.length > 0 && (
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              <input
                type="range"
                min={0}
                max={selectedBarangay
                  ? barangayLength - 1
                  : citySeries.length - 1}

                value={safeStart}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  // start cannot go beyond end
                  setRangeStart(Math.min(v, safeEnd));
                }}
                className="w-64"
              />
              <span className="text-xs text-zinc-600">
                From: {startDate ?? "N/A"}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="range"
                min={0}
                max={selectedBarangay
                  ? barangayLength - 1
                  : citySeries.length - 1}

                value={safeEnd}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  // end cannot go before start
                  setRangeEnd(Math.max(v, safeStart));
                }}
                className="w-64"
              />
              <span className="text-xs text-zinc-600">
                To: {endDate ?? "N/A"}
              </span>
            </div>
          </div>
        )}

        <div className="text-sm text-zinc-600">
          {startDate && endDate
            ? `Selected range: ${startDate} → ${endDate}`
            : ""}
        </div>
      </div>

      {/* MAIN LAYOUT */}
      <div className="flex flex-1 overflow-hidden">
        {/* LEFT MAP */}
        <div className="w-1/2 border-r overflow-hidden">
          <MapView
            onSelect={setSelectedBarangay}
            freq={freq}
            model={model}
            rangeStart={safeStart}
            rangeEnd={safeEnd}
            citySeries={citySeries}
          />
        </div>

        {/* RIGHT CHARTS */}
        <div className="w-1/2 overflow-y-auto bg-zinc-50">
          <BarangayChart
              name={selectedBarangay}
              freq={freq}
              model={model}
              rangeStart={safeStart}
              rangeEnd={safeEnd}
              onSeriesLength={setBarangayLength}
          />


          <CityChart
            series={citySeries}
            rangeStart={safeStart}
            rangeEnd={safeEnd}
            freq={freq}          // ← ADD THIS
          />
        </div>
      </div>
    </div>
  );
}
