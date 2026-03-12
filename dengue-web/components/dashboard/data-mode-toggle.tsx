"use client";

import { Button } from "@/components/ui/button";
import { ButtonGroup } from "@/components/ui/button-group";
import { useDashboardStore } from "@/lib/store/dashboard-store";

export function DataModeToggle({ compact = false }: { compact?: boolean }) {
  const dataMode = useDashboardStore((s) => s.dataMode);
  const setDataMode = useDashboardStore((s) => s.setDataMode);

  return (
    <ButtonGroup className={compact ? "w-full" : ""}>
      <Button
        size={compact ? "sm" : "default"}
        variant={dataMode === "observed" ? "default" : "outline"}
        onClick={() => setDataMode("observed")}
        className={compact ? "h-8 px-2 text-xs font-medium flex-1 min-w-0 rounded-r-none" : "h-9 px-4 text-sm font-medium rounded-r-none"}
        title="Use observed historical cases for map, KPI, and ranking."
      >
        {compact ? "Observed" : "Observed (Existing)"}
      </Button>
      <Button
        size={compact ? "sm" : "default"}
        variant={dataMode === "forecast" ? "default" : "outline"}
        onClick={() => setDataMode("forecast")}
        className={compact ? "h-8 px-2 text-xs font-medium flex-1 min-w-0 rounded-l-none border-l-0" : "h-9 px-4 text-sm font-medium rounded-l-none border-l-0"}
        title="Use forecasted values for map, KPI, and ranking."
      >
        {compact ? "Forecast" : "Forecast (Predicted)"}
      </Button>
    </ButtonGroup>
  );
}

