"use client";

import { Button } from "@/components/ui/button";
import { useDashboardStore } from "@/lib/store/dashboard-store";

export function RiskMetricToggle({ compact = false }: { compact?: boolean }) {
  const riskMetric = useDashboardStore((s) => s.riskMetric);
  const setRiskMetric = useDashboardStore((s) => s.setRiskMetric);

  return (
    <div className={`flex items-center ${compact ? "gap-1" : "gap-2"}`}>
      <Button
        size={compact ? "sm" : "default"}
        variant={riskMetric === "cases" ? "default" : "outline"}
        onClick={() => setRiskMetric("cases")}
        className={compact ? "h-8 text-xs" : ""}
      >
        Cases
      </Button>
      <Button
        size={compact ? "sm" : "default"}
        variant={riskMetric === "incidence" ? "default" : "outline"}
        onClick={() => setRiskMetric("incidence")}
        className={compact ? "h-8 text-xs" : ""}
      >
        Incidence (/100k)
      </Button>
    </div>
  );
}