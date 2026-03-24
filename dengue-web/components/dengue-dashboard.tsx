"use client"

import { useCallback, useRef, useState } from "react"
import { KpiCards } from "./dashboard/kpi-cards"
import { ForecastChart } from "./dashboard/forecast-chart"
import { ForecastRankings } from "./dashboard/forecast-rankings"
import { YearOverYearComparison } from "./dashboard/year-over-year-comparison"
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
  const [mapFocusToken, setMapFocusToken] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)
  const [disaggScheme, setDisaggScheme] = useState<string | null>(null)
  const setRunId = useDashboardStore((s) => s.setRunId)
  const currentRunId = useDashboardStore((s) => s.runId)
  const dataMode = useDashboardStore((s) => s.dataMode)
  const riskMetric = useDashboardStore((s) => s.riskMetric)
  const period = useDashboardStore((s) => s.period)
  const setRiskMetric = useDashboardStore((s) => s.setRiskMetric)
  const latestRunIdRef = useRef<string | null>(currentRunId)

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
          body: "Cases adjusted for population. 25 means 25/100,000.",
        };
      }
      return {
        title: "Observed Cases",
        body: "Reported cases in the selected date range.",
      };
    }

    if (riskMetric === "incidence") {
      return {
        title: "Forecasted Incidence",
        body: "Projected cases adjusted for population size.",
      };
    }
    if (riskMetric === "action_priority" || riskMetric === "surge") {
      return {
        title: "Forecasted Surge",
        body: "Projected rise versus recent baseline activity.",
      };
    }
    return {
      title: "Forecasted Cases",
      body: "Projected cases in the selected future window.",
    };
  })();

  useEffect(() => {
    latestRunIdRef.current = currentRunId;
  }, [currentRunId]);

  const syncLatestRun = useCallback(async (alive = true) => {
    try {
      const info = await getDataInfo();
      if (!alive) return;

      const nextRunId = info.run_id ?? null;
      const runChanged = nextRunId !== latestRunIdRef.current;

      setLastUpdated(info.last_historical_date);
      setDisaggScheme(info.disagg_scheme ?? null);

      if (runChanged) {
        latestRunIdRef.current = nextRunId;
        setRunId(nextRunId);
        setSelectedBarangay(null);
        setMapFocusToken(0);
      }
    } catch {
      if (!alive) return;
      setLastUpdated(null);
      setDisaggScheme(null);
    }
  }, [setRunId]);

  useEffect(() => {
    let alive = true;

    const initialTimeoutId = window.setTimeout(() => {
      void syncLatestRun(alive);
    }, 0);
    const intervalId = window.setInterval(() => {
      void syncLatestRun(alive);
    }, 30_000);

    return () => {
      alive = false;
      window.clearTimeout(initialTimeoutId);
      window.clearInterval(intervalId);
    };
  }, [syncLatestRun]);

  useEffect(() => {
    if (dataMode === "observed" && (riskMetric === "surge" || riskMetric === "action_priority")) {
      setRiskMetric("cases");
    }
  }, [dataMode, riskMetric, setRiskMetric]);

  const handleMapBarangaySelect = (value: { pretty: string; clean: string } | null) => {
    setSelectedBarangay(value);
  };

  const handleRankingBarangaySelect = (value: { pretty: string; clean: string } | null) => {
    setSelectedBarangay(value);
    if (dataMode === "forecast" && value) {
      setMapFocusToken((current) => current + 1);
    }
  };


  return (
    <div className="min-h-screen bg-background">
      <AppHeader
        mode="public"
        lastUpdated={formatReadableDate(lastUpdated)}
        disaggScheme={disaggScheme}
        onRefreshLatestRun={() => void syncLatestRun(true)}
      />

      <main className="relative z-0 p-3 md:p-6">
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

          <YearOverYearComparison selectedBarangay={selectedBarangay} />

          <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 md:gap-6 items-stretch">
            <div className="xl:col-span-8 h-full">
              <ChoroplethMap
                selectedBarangay={selectedBarangay}
                onBarangaySelect={handleMapBarangaySelect}
                focusToken={mapFocusToken}
              />
            </div>
            <div className="xl:col-span-4 h-full">
              <ForecastRankings
                selectedBarangay={selectedBarangay}
                onBarangaySelect={handleRankingBarangaySelect}
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
