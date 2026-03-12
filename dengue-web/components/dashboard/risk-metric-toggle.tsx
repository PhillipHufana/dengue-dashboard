"use client";

import { Button } from "@/components/ui/button";
import { ButtonGroup } from "@/components/ui/button-group";
import { useDashboardStore } from "@/lib/store/dashboard-store";

export function RiskMetricToggle({ compact = false }: { compact?: boolean }) {
  const riskMetric = useDashboardStore((s) => s.riskMetric);
  const setRiskMetric = useDashboardStore((s) => s.setRiskMetric);
  const dataMode = useDashboardStore((s) => s.dataMode);
  const showSurge = dataMode === "forecast";

  return (
    <ButtonGroup className={compact ? "w-full" : ""}>
      <Button
        size={compact ? "sm" : "default"}
        variant={riskMetric === "action_priority" ? "default" : "outline"}
        onClick={() => setRiskMetric("action_priority")}
        className={
          compact
            ? "h-8 px-2 text-xs font-medium flex-1 min-w-0 rounded-r-none"
            : "h-9 px-4 text-sm font-medium rounded-r-none"
        }
        title={dataMode === "observed" ? "Recommended queue for Respond Now." : "Recommended queue for Prepare Next."}
      >
        {compact ? "Recommended" : "Recommended"}
      </Button>
      <Button
        size={compact ? "sm" : "default"}
        variant={riskMetric === "cases" ? "default" : "outline"}
        onClick={() => setRiskMetric("cases")}
        className={
          compact
            ? "h-8 px-2 text-xs font-medium flex-1 min-w-0 rounded-l-none border-l-0"
            : "h-9 px-4 text-sm font-medium rounded-l-none border-l-0"
        }
        title={dataMode === "observed" ? "Observed cases (Past W)." : "Forecast cases (Next W)."}
      >
        {compact ? "Cases" : "Cases"}
      </Button>
      <Button
        size={compact ? "sm" : "default"}
        variant={riskMetric === "incidence" ? "default" : "outline"}
        onClick={() => setRiskMetric("incidence")}
        className={
          compact
            ? "h-8 px-2 text-xs font-medium flex-1 min-w-0 rounded-l-none border-l-0"
            : "h-9 px-4 text-sm font-medium rounded-l-none border-l-0"
        }
        title={dataMode === "observed" ? "Risk rate based on recent reported cases." : "Risk rate based on forecasted cases."}
      >
        {compact ? "Rate" : "Risk Rate"}
      </Button>
      {showSurge ? (
        <Button
          size={compact ? "sm" : "default"}
          variant={riskMetric === "surge" ? "default" : "outline"}
          onClick={() => setRiskMetric("surge")}
          className={
            compact
              ? "h-8 px-2 text-xs font-medium flex-1 min-w-0 rounded-l-none border-l-0"
              : "h-9 px-4 text-sm font-medium rounded-l-none border-l-0"
          }
          title="How fast risk may rise compared with recent weeks."
        >
          {compact ? "Change" : "Risk Change"}
        </Button>
      ) : null}
    </ButtonGroup>
  );
}
