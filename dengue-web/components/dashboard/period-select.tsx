"use client";

import { useEffect } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useDashboardStore, type TimePeriod } from "@/lib/store/dashboard-store";

const periodLabel: Record<TimePeriod, string> = {
  "1w": "1 Week",
  "2w": "2 Weeks",
  "1m": "1 Month",
  "3m": "3 Months",
  "6m": "6 Months",
  "1y": "1 Year",
};

const ALLOWED_PERIODS: TimePeriod[] = ["1w", "2w", "1m", "3m"]; // ✅ temporary limit

export function PeriodSelect({ compact = false }: { compact?: boolean }) {
  const period = useDashboardStore((s) => s.period);
  const setPeriod = useDashboardStore((s) => s.setPeriod);

  // Optional safety: if someone has 6m/1y persisted, auto-fallback
  const safePeriod: TimePeriod = ALLOWED_PERIODS.includes(period) ? period : "1m";

  useEffect(() => {
    if (period !== safePeriod) {
      setPeriod(safePeriod);
    }
  }, [period, safePeriod, setPeriod]);

  return (
    <Select value={safePeriod} onValueChange={(v) => setPeriod(v as TimePeriod)}>
      <SelectTrigger
        className={
          compact
            ? "w-full h-8 text-[11px] border-secondary bg-secondary text-secondary-foreground! hover:bg-secondary/90 hover:border-secondary/90 data-[state=open]:bg-secondary/90 [&_svg]:text-secondary-foreground!"
            : "w-[150px] h-9 border-secondary bg-secondary text-secondary-foreground! hover:bg-secondary/90 hover:border-secondary/90 data-[state=open]:bg-secondary/90 [&_svg]:text-secondary-foreground!"
        }
      >
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {ALLOWED_PERIODS.map((p) => (
          <SelectItem key={p} value={p}>
            {periodLabel[p]}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
