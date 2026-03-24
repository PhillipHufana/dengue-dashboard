"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Frequency = "weekly" | "monthly" | "yearly";
export type ModelName = string;
export type RiskMetric = "cases" | "incidence" | "surge" | "action_priority";
export type DataMode = "observed" | "forecast";
export type TimePeriod = "1w" | "2w" | "1m" | "3m" | "6m" | "1y";

interface DashboardState {
  // UI state
  selectedBarangay: string | null;
  freq: Frequency;
  modelName: ModelName;

  // run/model/horizon controls
  runId: string | null;
  horizonType: "test" | "future";

  // global period for syncing map/summary/rankings
  period: TimePeriod;
  setPeriod: (p: TimePeriod) => void;

  // time-range controls (unused for API now, keep)
  rangeStart: number;
  rangeEnd: number;

  // city unity range (total)
  cityLength: number;

  riskMetric: RiskMetric;
  setRiskMetric: (v: RiskMetric) => void;
  dataMode: DataMode;
  setDataMode: (v: DataMode) => void;

  // Actions
  setSelectedBarangay: (name: string | null) => void;
  setFreq: (f: Frequency) => void;
  setModelName: (m: ModelName) => void;

  setRunId: (id: string | null) => void;
  setHorizonType: (h: "test" | "future") => void;

  setRange: (start: number, end: number) => void;
  setRangeStart: (start: number) => void;
  setRangeEnd: (end: number) => void;

  setCityLength: (n: number) => void;
}

export const useDashboardStore = create<DashboardState>()(
  persist(
    (set) => ({
      selectedBarangay: null,
      freq: "weekly",
      modelName: "preferred",

      runId: null,
      horizonType: "future",

      //  default period
      period: "1m",
      setPeriod: (p) => set({ period: p }),

      riskMetric: "cases",
      setRiskMetric: (v) => set({ riskMetric: v }),
      dataMode: "observed",
      setDataMode: (v) => set({ dataMode: v }),

      rangeStart: 0,
      rangeEnd: 10,
      cityLength: 0,

      setSelectedBarangay: (name) => set({ selectedBarangay: name }),
      setFreq: (f) => set({ freq: f }),
      setModelName: (m) => set({ modelName: m }),

      setRunId: (id) => set({ runId: id }),
      setHorizonType: (h) => set({ horizonType: h }),

      setRange: (start, end) => set({ rangeStart: start, rangeEnd: end }),
      setRangeStart: (start) => set({ rangeStart: start }),
      setRangeEnd: (end) => set({ rangeEnd: end }),

      setCityLength: (n) => set({ cityLength: n }),
    }),
    { name: "dashboard-store" }
  )
);
