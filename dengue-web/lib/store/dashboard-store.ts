"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Frequency = "weekly" | "monthly" | "yearly";
export type ForecastModel = "preferred" | "final" | "hybrid" | "local";

interface DashboardState {
  // UI state
  selectedBarangay: string | null;
  freq: Frequency;
  model: ForecastModel;

  // time-range controls
  rangeStart: number;
  rangeEnd: number;

  // city unity range (total)
  cityLength: number;

  // Actions
  setSelectedBarangay: (name: string | null) => void;
  setFreq: (f: Frequency) => void;
  setModel: (m: ForecastModel) => void;

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
      model: "preferred",

      rangeStart: 0,
      rangeEnd: 10,
      cityLength: 0,

      setSelectedBarangay: (name) => set(() => ({ selectedBarangay: name })),
      setFreq: (f) => set(() => ({ freq: f })),
      setModel: (m) => set(() => ({ model: m })),

      setRange: (start, end) => set(() => ({ rangeStart: start, rangeEnd: end })),
      setRangeStart: (start) => set(() => ({ rangeStart: start })),
      setRangeEnd: (end) => set(() => ({ rangeEnd: end })),

      setCityLength: (n) => set(() => ({ cityLength: n })),
    }),
    {
      name: "dashboard-store",
    }
  )
);
