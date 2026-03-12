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

function formatReadableDate(value?: string | null): string | null {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString([], {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
}

export function DengueDashboard() {
  const [selectedBarangay, setSelectedBarangay] = useState<{
    pretty: string;
    clean: string;
  } | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)
  const [disaggScheme, setDisaggScheme] = useState<string | null>(null)
  const setRunId = useDashboardStore((s) => s.setRunId)
  const dataMode = useDashboardStore((s) => s.dataMode)
  const riskMetric = useDashboardStore((s) => s.riskMetric)
  const setRiskMetric = useDashboardStore((s) => s.setRiskMetric)
  const effectiveMetric =
    riskMetric === "action_priority" ? (dataMode === "observed" ? "cases" : "surge") : riskMetric;

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const info = await getDataInfo();
        if (alive) {
          setLastUpdated(info.last_historical_date);
          setRunId(info.run_id ?? null);
          setDisaggScheme(info.disagg_scheme ?? null);
        }
      } catch {
        if (alive) {
          setLastUpdated(null);
          setDisaggScheme(null);
        }
      }
    })();
    return () => { alive = false; };
  }, [setRunId]);

  useEffect(() => {
    if (dataMode === "observed" && riskMetric === "surge") {
      setRiskMetric("cases");
    }
  }, [dataMode, riskMetric, setRiskMetric]);


  return (
    <div className="min-h-screen bg-background">
      <AppHeader
        mode="public"
        lastUpdated={formatReadableDate(lastUpdated)}
        disaggScheme={disaggScheme}
      />

      <main className="p-3 md:p-6">
        <div className="space-y-4 md:space-y-6">
          <section className="rounded-lg border border-border bg-card p-3 md:p-4">
            <p className="text-sm md:text-base font-semibold">
              {dataMode === "observed"
                ? "Where are reported cases highest right now?"
                : effectiveMetric === "surge"
                ? "Where is risk rising fastest versus recent baseline?"
                : "Where are the most cases expected soon?"}
            </p>
            <p className="mt-1 text-xs md:text-sm text-muted-foreground">
              {dataMode === "observed"
                ? "Respond Now uses observed data from the past selected period (W weeks)."
                : effectiveMetric === "surge"
                ? "Prepare Next uses forecasts. Surge compares next W weeks against recent baseline."
                : "Prepare Next uses forecast estimates for the next selected period (W weeks)."}
            </p>
            {dataMode === "forecast" ? (
              <p className="mt-1 text-[11px] md:text-xs text-muted-foreground italic">
                Forecast views are estimates, not confirmed case counts.
              </p>
            ) : null}
          </section>

          <KpiCards />

          <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 md:gap-6 items-stretch">
            <div className="xl:col-span-8 h-full">
              <ChoroplethMap
                selectedBarangay={selectedBarangay}
                onBarangaySelect={setSelectedBarangay}
              />
            </div>
            <div className="xl:col-span-4 h-full">
              <ForecastRankings
                selectedBarangay={selectedBarangay}
                onBarangaySelect={setSelectedBarangay}
              />
            </div>
          </div>

          <ForecastChart selectedBarangay={selectedBarangay} />

          {/* <DataUploadLogs /> */}


        </div>
      </main>
    </div>
  )
}
