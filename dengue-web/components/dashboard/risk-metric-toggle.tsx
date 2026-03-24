"use client";

import { Button } from "@/components/ui/button";
import { ButtonGroup } from "@/components/ui/button-group";
import { useDashboardStore } from "@/lib/store/dashboard-store";

export function RiskMetricToggle({ compact = false }: { compact?: boolean }) {
  const riskMetric = useDashboardStore((s) => s.riskMetric);
  const setRiskMetric = useDashboardStore((s) => s.setRiskMetric);
  const dataMode = useDashboardStore((s) => s.dataMode);
  const showForecastSurge = dataMode === "forecast";

  return (
    <ButtonGroup className={compact ? "w-full" : ""}>
      {showForecastSurge ? (
        <Button
          size={compact ? "sm" : "default"}
          variant={riskMetric === "action_priority" ? "default" : "outline"}
          onClick={() => setRiskMetric("action_priority")}
          className={
            compact
              ? "h-8 px-2 text-xs font-medium flex-1 min-w-0 rounded-r-none"
              : "h-9 px-4 text-sm font-medium rounded-r-none"
          }
          title="Forecasted surge compared with recent baseline, with minimum-burden eligibility."
        >
          {compact ? "Surge" : "Surge"}
        </Button>
      ) : null}
      <Button
        size={compact ? "sm" : "default"}
        variant={riskMetric === "cases" ? "default" : "outline"}
        onClick={() => setRiskMetric("cases")}
        className={
          compact
            ? `h-8 px-2 text-xs font-medium flex-1 min-w-0 ${showForecastSurge ? "rounded-l-none border-l-0" : ""}`
            : `h-9 px-4 text-sm font-medium ${showForecastSurge ? "rounded-l-none border-l-0" : ""}`
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
        title={dataMode === "observed" ? "Observed incidence based on reported cases." : "Forecasted incidence based on projected cases."}
      >
        {compact ? "Incid." : "Incidence"}
      </Button>
    </ButtonGroup>
  );
}
