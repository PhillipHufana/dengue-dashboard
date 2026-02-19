"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Frequency = "weekly" | "monthly" | "yearly";
export type ModelName = string;
export type RiskMetric = "cases" | "incidence";
interface DashboardState {
  // UI state
  selectedBarangay: string | null;
  freq: Frequency;
  modelName: ModelName;

  // run/model/horizon controls
  runId: string | null;
  horizonType: "test" | "future";

  // time-range controls
  rangeStart: number;
  rangeEnd: number;

  // city unity range (total)
  cityLength: number;

  riskMetric: RiskMetric;
  setRiskMetric: (v: RiskMetric) => void;

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

      riskMetric: "cases",
      setRiskMetric: (v) => set({ riskMetric: v }),


      runId: null,
      horizonType: "future",

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
