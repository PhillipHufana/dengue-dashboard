"use client";

import { Button } from "@/components/ui/button";
import { ButtonGroup } from "@/components/ui/button-group";
import { useDashboardStore } from "@/lib/store/dashboard-store";

export function RiskMetricToggle({ compact = false }: { compact?: boolean }) {
  const riskMetric = useDashboardStore((s) => s.riskMetric);
  const setRiskMetric = useDashboardStore((s) => s.setRiskMetric);

  return (
    <ButtonGroup className={compact ? "w-full" : ""}>
      <Button
        size={compact ? "sm" : "default"}
        variant={riskMetric === "cases" ? "default" : "outline"}
        onClick={() => setRiskMetric("cases")}
        className={
          compact
            ? "h-9 px-3 text-sm font-medium flex-1 min-w-0 rounded-r-none"
            : "h-9 px-4 text-sm font-medium rounded-r-none"
        }
        title="Use absolute forecasted case counts for ranking and map colors."
      >
        Cases
      </Button>
      <Button
        size={compact ? "sm" : "default"}
        variant={riskMetric === "incidence" ? "default" : "outline"}
        onClick={() => setRiskMetric("incidence")}
        className={
          compact
            ? "h-9 px-3 text-sm font-medium flex-1 min-w-0 rounded-l-none border-l-0"
            : "h-9 px-4 text-sm font-medium rounded-l-none border-l-0"
        }
        title="Use forecasted incidence per 100k population. Recommended for fair cross-barangay comparison."
      >
        Incidence (/100k)
      </Button>
    </ButtonGroup>
  );
}
