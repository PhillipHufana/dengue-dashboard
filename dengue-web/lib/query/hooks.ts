"use client";

import { useQuery } from "@tanstack/react-query";
import {
  getSummary,
  getChoropleth,
  getTimeseries,
  getForecastRankings,
} from "@/lib/api";

import type { Frequency } from "@/lib/store/dashboard-store";
import type { ChoroplethFC, SummaryResponse, RankingResponse } from "@/lib/api";


export function useSummary(runId?: string | null, modelName?: string | null) {
  return useQuery<SummaryResponse>({
    queryKey: ["summary", runId ?? null, modelName ?? null],
    queryFn: () =>
      getSummary({
        runId: runId ?? undefined,
        modelName: modelName ?? undefined,
      }),
  });
}

export function useChoropleth(runId?: string | null, modelName?: string | null) {
  return useQuery<ChoroplethFC>({
    queryKey: ["choropleth", runId ?? null, modelName ?? null],
    queryFn: () =>
      getChoropleth({
        runId: runId ?? undefined,
        modelName: modelName ?? undefined,
      }),
  });
}

export function useRankings(
  period: string,
  runId?: string | null,
  modelName?: string | null
) {
  return useQuery<RankingResponse>({
    queryKey: ["rankings", period, runId ?? null, modelName ?? null],
    queryFn: () =>
      getForecastRankings(period, {
        runId: runId ?? undefined,
        modelName: modelName ?? undefined,
      }),
  });
}

export function useBarangaySeries(
  name: string | null,
  freq: Frequency,
  runId: string | null,
  modelName: string,
  horizonType: "test" | "future"
) {
  return useQuery({
    queryKey: ["timeseries", "barangay", name, freq, runId, modelName, horizonType],
    enabled: !!name,
    queryFn: () =>
      getTimeseries("barangay", {
        name: name!, // should be canonical
        freq,
        runId: runId ?? undefined,
        modelName,
        horizonType,
      }),
  });
}

export function useCitySeries(
  freq: Frequency,
  runId: string | null,
  modelName: string,
  horizonType: "test" | "future"
) {
  return useQuery({
    queryKey: ["timeseries", "city", freq, runId, modelName, horizonType],
    queryFn: () =>
      getTimeseries("city", {
        freq,
        runId: runId ?? undefined,
        modelName,
        horizonType,
      }),
  });
}
