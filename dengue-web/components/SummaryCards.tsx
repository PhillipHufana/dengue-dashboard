"use client";

import { useEffect, useState } from "react";
import { getSummary } from "@/lib/api";

export default function SummaryCards() {
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    getSummary().then(setData).catch(console.error);
  }, []);

  if (!data) return <div className="p-4">Loading summary…</div>;

  const city = data.city_latest;
  const total = data.total_forecasted_cases;

  const top3 = [...data.barangay_latest]
    .sort((a, b) => (b.forecast ?? 0) - (a.forecast ?? 0))
    .slice(0, 3);

  return (
    <div className="grid grid-cols-3 gap-4 p-4 bg-white shadow">
      <div className="rounded border p-4">
        <div className="text-sm text-zinc-500">City forecast</div>
        <div className="text-2xl font-bold text-zinc-600">{city?.city_cases}</div>
        <div className="text-xs text-zinc-600">{city?.week_start}</div>
      </div>

      <div className="rounded border p-4">
        <div className="text-sm text-zinc-500">
          Total forecasted (all barangays)
        </div>
        <div className="text-2xl font-bold text-zinc-600">{total}</div>
        <div className="text-xs text-zinc-600">Latest forecast week</div>
      </div>

      <div className="rounded border p-4">
        <div className="text-sm text-zinc-500">Top 3 hotspots</div>
        {top3.map((b: any) => (
          <div key={b.name} className="text-sm text-gray-600">
            {b.name} — <span className="font-semibold text-gray-600">{b.forecast}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
