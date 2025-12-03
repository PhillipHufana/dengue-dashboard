"use client";

import { useQuery } from "@tanstack/react-query";
import {
  getSummary,
  getChoropleth,
  getTimeseries,
} from "@/lib/api";
import { Frequency, ForecastModel } from "@/lib/store/dashboard-store";

export function useSummary() {
  return useQuery({
    queryKey: ["summary"],
    queryFn: getSummary,
  });
}

export function useChoropleth() {
  return useQuery({
    queryKey: ["choropleth"],
    queryFn: getChoropleth,
  });
}

export function useBarangaySeries(
  name: string | null,
  freq: Frequency,
  model: ForecastModel
) {
  return useQuery({
    queryKey: ["barangay", name, freq, model],
    enabled: !!name,
    queryFn: () => getTimeseries("barangay", { name: name!, freq, model }),
  });
}

export function useCitySeries(freq: Frequency, model: ForecastModel) {
  return useQuery({
    queryKey: ["city", freq, model],
    queryFn: () => getTimeseries("city", { freq, model }),
  });
}
