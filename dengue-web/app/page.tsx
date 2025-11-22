// app/page.tsx
"use client";

import { useState } from "react";
import SummaryCards from "@/components/SummaryCards";
import MapView from "@/components/MapView";
import BarangayChart from "@/components/BarangayChart";
import CityChart from "@/components/CityChart";

export default function Dashboard() {
  const [selectedBarangay, setSelectedBarangay] = useState<string>("");

  return (
    <div className="h-screen w-screen flex flex-col">
      {/* TOP SUMMARY */}
      <SummaryCards />

      <div className="flex flex-1 overflow-hidden">
        {/* LEFT MAP */}
        <div className="w-1/2 border-r overflow-hidden">
          <MapView onSelect={(name) => setSelectedBarangay(name)} />
        </div>

        {/* RIGHT CHART PANEL */}
        <div className="w-1/2 overflow-y-auto bg-zinc-50">
          <BarangayChart name={selectedBarangay} />
          <CityChart />
        </div>
      </div>
    </div>
  );
}
