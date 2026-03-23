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
import { formatDateRange, formatReadableDate } from "@/lib/display-text"


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
  const [disaggScheme, setDisaggScheme] = useState<string | null>(null)
  const setRunId = useDashboardStore((s) => s.setRunId)
  const dataMode = useDashboardStore((s) => s.dataMode)
  const riskMetric = useDashboardStore((s) => s.riskMetric)
  const period = useDashboardStore((s) => s.period)
  const setRiskMetric = useDashboardStore((s) => s.setRiskMetric)

  const periodWeeks: Record<string, number> = {
    "1w": 1,
    "2w": 2,
    "1m": 4,
    "3m": 12,
    "6m": 26,
    "1y": 52,
  };

  const rangeLabel = (() => {
    if (!lastUpdated) return null;
    const end = new Date(lastUpdated);
    if (Number.isNaN(end.getTime())) return null;
    const weeks = periodWeeks[period] ?? 4;
    const start = new Date(end);
    if (dataMode === "observed") {
      start.setDate(end.getDate() - ((weeks - 1) * 7));
    } else {
      start.setDate(end.getDate() + 7);
      end.setDate(start.getDate() + ((weeks - 1) * 7));
    }
    return formatDateRange(start.toISOString(), end.toISOString());
  })();

  const banner = (() => {
    if (dataMode === "observed") {
      if (riskMetric === "incidence") {
        return {
          title: "Observed Incidence",
          body: "This view compares reported cases to population over the selected observed date range.",
        };
      }
      if (riskMetric === "action_priority") {
        return {
          title: "Observed Action Priority",
          body: "This view prioritizes barangays using recent reported burden in the selected observed date range.",
        };
      }
      return {
        title: "Observed Cases",
        body: "This view shows where the most reported cases were recorded in the selected observed date range.",
      };
    }

    if (riskMetric === "incidence") {
      return {
        title: "Forecasted Incidence",
        body: "This view shows forecasted incidence for the selected future date range using projected cases and population.",
      };
    }
    if (riskMetric === "surge") {
      return {
        title: "Forecasted Surge",
        body: "This view compares the selected forecast window against recent baseline activity to highlight the strongest expected increase.",
      };
    }
    if (riskMetric === "action_priority") {
      return {
        title: "Forecasted Action Priority",
        body: "This view prioritizes barangays with meaningful expected rise and projected burden in the selected forecast date range.",
      };
    }
    return {
      title: "Forecasted Cases",
      body: "This view shows projected cases for the selected future date range.",
    };
  })();

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
          <section className={`rounded-lg border p-3 md:p-4 ${
            dataMode === "observed"
              ? "border-[#67B99A] bg-[#CFF3DC]/55 dark:border-[#67B99A] dark:bg-[#88D4AB]/12"
              : "border-blue-200 bg-blue-50/70 dark:border-blue-900 dark:bg-blue-950/30"
          }`}>
            <p className="text-sm md:text-base font-semibold">{banner.title}</p>
            <p className="mt-1 text-xs md:text-sm text-muted-foreground">
              {banner.body}
            </p>
            {rangeLabel ? (
              <p className="mt-1 text-[11px] md:text-xs font-medium text-muted-foreground">
                Date range: {rangeLabel}
              </p>
            ) : null}
            {dataMode === "forecast" ? (
              <p className="mt-1 text-[11px] md:text-xs text-muted-foreground italic">
                Forecasted values are estimates, not confirmed case counts.
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
