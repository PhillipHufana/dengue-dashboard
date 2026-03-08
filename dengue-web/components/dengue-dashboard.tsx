"use client"

import { useState } from "react"
import { KpiCards } from "./dashboard/kpi-cards"
import { ForecastChart } from "./dashboard/forecast-chart"
import { ForecastRankings } from "./dashboard/forecast-rankings"
import dynamic from "next/dynamic";
// import { DataUploadLogs } from "./dashboard/upload-logs"
import { useDashboardStore } from "@/lib/store/dashboard-store"
import { useEffect } from "react"
import { getDataInfo } from "@/lib/api"
import { AppHeader } from "./dashboard/AppHeader"
import { RiskMetricToggle } from "./dashboard/risk-metric-toggle";
import { PeriodSelect } from "./dashboard/period-select";


const ChoroplethMap = dynamic(
  () =>
    import("./dashboard/choropleth-map").then((mod) => mod.ChoroplethMap),
  {
    ssr: false,
    loading: () => (
      <div className="h-[300px] flex items-center justify-center">
        Loading map…
      </div>
    ),
  }
);

export function DengueDashboard() {
  const [selectedBarangay, setSelectedBarangay] = useState<{
    pretty: string;
    clean: string;
  } | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)
  const setRunId = useDashboardStore((s) => s.setRunId)

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const info = await getDataInfo();
        if (alive) {
          setLastUpdated(info.last_historical_date);
          setRunId(info.run_id ?? null);
        }
      } catch {
        if (alive) setLastUpdated(null);
      }
    })();
    return () => { alive = false; };
  }, [setRunId]);


  return (
    <div className="min-h-screen bg-background">
      <AppHeader
        mode="public"
        lastUpdated={lastUpdated}
        rightSlot={
          <div className="flex items-center gap-2">
            <RiskMetricToggle />
            <PeriodSelect />
          </div>
        }
      />

      <main className="p-3 md:p-6">
        <div className="space-y-4 md:space-y-6">
          <ChoroplethMap
            selectedBarangay={selectedBarangay}
            onBarangaySelect={setSelectedBarangay}
          />

          <ForecastChart selectedBarangay={selectedBarangay} />

          <KpiCards />

          <ForecastRankings
            selectedBarangay={selectedBarangay}
            onBarangaySelect={setSelectedBarangay}
          />

          {/* <DataUploadLogs /> */}


        </div>
      </main>
    </div>
  )
}
