"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { getSummary, getChoropleth, getTimeseries, getForecastRankings, getCityCompareSeries, getActionPriority } from "@/lib/api";

import type { DataMode, Frequency, RiskMetric, TimePeriod } from "@/lib/store/dashboard-store";
import type { ChoroplethFC, SummaryResponse, RankingResponse, ActionPriorityResponse } from "@/lib/api";

export function useSummary(
  runId?: string | null,
  modelName?: string | null,
  period?: TimePeriod | null,
  dataMode?: DataMode | null
) {
  return useQuery<SummaryResponse>({
    queryKey: ["summary", runId ?? null, modelName ?? null, period ?? null, dataMode ?? null],
    queryFn: () =>
      getSummary({
        runId: runId ?? undefined,
        modelName: modelName ?? undefined,
        period: period ?? undefined,
        dataMode: dataMode ?? undefined,
      }),
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
    placeholderData: keepPreviousData,
  });
}
export function useChoropleth(
  runId?: string | null,
  modelName?: string | null,
  period?: TimePeriod | null,
  dataMode?: DataMode | null
) {
  return useQuery<ChoroplethFC>({
    queryKey: ["choropleth", runId ?? null, modelName ?? null, period ?? null, dataMode ?? null],
    queryFn: () =>
      getChoropleth({
        runId: runId ?? undefined,
        modelName: modelName ?? undefined,
        period: period ?? undefined,
        dataMode: dataMode ?? undefined,
      }),
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
    placeholderData: keepPreviousData,
  });
}

export function useRankings(
  period: string,
  runId?: string | null,
  modelName?: string | null,
  rankingBasis?: RiskMetric | null,
  dataMode?: DataMode | null
) {
  return useQuery<RankingResponse>({
    queryKey: ["rankings", period, runId ?? null, modelName ?? null, rankingBasis ?? null, dataMode ?? null],
    queryFn: () =>
      getForecastRankings(period, {
        runId: runId ?? undefined,
        modelName: modelName ?? undefined,
        rankingBasis: rankingBasis ?? undefined,
        dataMode: dataMode ?? undefined,
      }),
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
    placeholderData: keepPreviousData,
  });
}

export function useActionPriority(
  period: string,
  runId?: string | null,
  modelName?: string | null,
  viewMode?: DataMode | null,
  enabled = true
) {
  return useQuery<ActionPriorityResponse>({
    queryKey: ["action-priority", period, runId ?? null, modelName ?? null, viewMode ?? null],
    enabled,
    queryFn: () =>
      getActionPriority(period, {
        runId: runId ?? undefined,
        modelName: modelName ?? undefined,
        viewMode: viewMode ?? undefined,
      }),
    staleTime: 60_000,
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
    placeholderData: keepPreviousData,
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
        name: name!,
        freq,
        runId: runId ?? undefined,
        modelName,
        horizonType,
      }),
    staleTime: 2 * 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    placeholderData: keepPreviousData,
  });
}

export function useCitySeries(freq: Frequency, runId: string | null, modelName: string, horizonType: "test" | "future") {
  return useQuery({
    queryKey: ["timeseries", "city", freq, runId, modelName, horizonType],
    queryFn: () =>
      getTimeseries("city", {
        freq,
        runId: runId ?? undefined,
        modelName,
        horizonType,
      }),
    staleTime: 2 * 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    placeholderData: keepPreviousData,
  });
}

export function useCityCompareSeries(runId: string | null, enabled = true) {
  return useQuery({
    queryKey: ["timeseries", "city", "compare", runId ?? null],
    enabled,
    queryFn: () =>
      getCityCompareSeries({
        runId: runId ?? undefined,
      }),
    staleTime: 2 * 60_000,
    gcTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    placeholderData: keepPreviousData,
  });
}
