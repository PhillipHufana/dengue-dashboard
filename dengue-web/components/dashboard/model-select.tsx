"use client";

import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { getModels } from "@/lib/api";
import { useDashboardStore } from "@/lib/store/dashboard-store";

const PREFERRED_ORDER = ["preferred", "prophet", "arima"] as const;

export function ModelSelect({ compact = false }: { compact?: boolean }) {
  const runId = useDashboardStore((s) => s.runId);
  const modelName = useDashboardStore((s) => s.modelName);
  const setModelName = useDashboardStore((s) => s.setModelName);

  const { data } = useQuery({
    queryKey: ["models", runId ?? null],
    queryFn: () => getModels(runId ?? undefined),
    staleTime: 60_000,
  });

  const models: string[] = useMemo(() => {
    const raw = Array.isArray(data?.models) ? data.models.map((x: unknown) => String(x)) : [];
    if (!raw.length) return ["preferred"];

    const rank = new Map<string, number>(PREFERRED_ORDER.map((m, idx) => [m, idx]));
    return [...raw].sort((a, b) => {
      const ra = rank.has(a) ? (rank.get(a) as number) : 99;
      const rb = rank.has(b) ? (rank.get(b) as number) : 99;
      return ra - rb || a.localeCompare(b);
    });
  }, [data]);

  const defaultModel = String(data?.default_model || models[0] || "preferred");
  const safeModel = models.includes(modelName) ? modelName : defaultModel;

  useEffect(() => {
    if (safeModel !== modelName) {
      setModelName(safeModel);
    }
  }, [safeModel, modelName, setModelName]);

  return (
    <Select value={safeModel} onValueChange={(v) => setModelName(v)}>
      <SelectTrigger className={compact ? "w-full h-8 text-xs bg-secondary" : "w-[150px] bg-secondary"}>
        <SelectValue placeholder="Model" />
      </SelectTrigger>
      <SelectContent>
        {models.map((m) => (
          <SelectItem key={m} value={m}>
            {m.toUpperCase()}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
