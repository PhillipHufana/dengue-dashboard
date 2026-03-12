"use client";

import { Button } from "@/components/ui/button";
import { ButtonGroup } from "@/components/ui/button-group";
import { useDashboardStore } from "@/lib/store/dashboard-store";

export function DataModeToggle({ compact = false }: { compact?: boolean }) {
  const dataMode = useDashboardStore((s) => s.dataMode);
  const setDataMode = useDashboardStore((s) => s.setDataMode);
  const setRiskMetric = useDashboardStore((s) => s.setRiskMetric);

  return (
    <ButtonGroup className={compact ? "w-full" : ""}>
      <Button
        size={compact ? "sm" : "default"}
        variant={dataMode === "observed" ? "default" : "outline"}
        onClick={() => {
          setDataMode("observed");
          setRiskMetric("action_priority");
        }}
        className={compact ? "h-8 px-2 text-xs font-medium flex-1 min-w-0 rounded-r-none" : "h-9 px-4 text-sm font-medium rounded-r-none"}
        title="Respond now using observed data from the past W weeks."
      >
        {compact ? "Respond" : "Respond Now"}
      </Button>
      <Button
        size={compact ? "sm" : "default"}
        variant={dataMode === "forecast" ? "default" : "outline"}
        onClick={() => {
          setDataMode("forecast");
          setRiskMetric("action_priority");
        }}
        className={compact ? "h-8 px-2 text-xs font-medium flex-1 min-w-0 rounded-l-none border-l-0" : "h-9 px-4 text-sm font-medium rounded-l-none border-l-0"}
        title="Prepare next using forecast estimates for the next W weeks."
      >
        {compact ? "Prepare" : "Prepare Next"}
      </Button>
    </ButtonGroup>
  );
}
