// lib/data.ts
import {
  getSummary,
  getChoropleth,
  getTimeseries,
  getBarangaySeries,
  getCitySeries,
} from "./api";

// Literal type unions for safety
type Freq = "weekly" | "monthly" | "yearly";
type ModelName = string; // "preferred" by default

// --------------------------------------
// 1. City timeseries
// --------------------------------------
export async function fetchCityTimeseries(
  freq: Freq = "weekly",
  runId?: string | null,
  modelName: ModelName = "preferred",
  horizonType: "test" | "future" = "future"
) {
  const res = await getTimeseries("city", {
    freq,
    runId: runId ?? undefined,
    modelName,
    horizonType,
  });

  return res.series.map((d: any) => ({
    date: d.date,
    cases: d.cases ?? 0,
    forecast: d.forecast ?? 0,
    isFuture: !!d.is_future,
  }));
}

export async function fetchBarangayTimeseries(
  name: string,
  freq: Freq = "weekly",
  runId?: string | null,
  modelName: ModelName = "preferred",
  horizonType: "test" | "future" = "future"
) {
  const res = await getTimeseries("barangay", {
    name,
    freq,
    runId: runId ?? undefined,
    modelName,
    horizonType,
  });

  return res.series.map((d: any) => ({
    date: d.date,
    cases: d.cases ?? 0,
    forecast: d.forecast ?? 0,
    isFuture: !!d.is_future,
  }));
}

// --------------------------------------
// 3. GeoJSON polygons
// --------------------------------------
export async function fetchBarangayPolygons() {
  const fc = await getChoropleth();

  return {
    ...fc,
    features: fc.features.map((f: any) => ({
      ...f,
      properties: {
        name: f.properties.name,
        risk: f.properties.risk_level,
        latestCases: f.properties.latest_cases ?? 0,
        latestForecast: f.properties.latest_forecast ?? 0,
        latestWeek: f.properties.latest_week ?? null,
      },
    })),
  };
}

// --------------------------------------
// 4. Dashboard summary
// --------------------------------------
export async function fetchDashboardSummary() {
  const raw = await getSummary();
  const cityCases = raw.city_latest?.city_cases ?? 0;
  const cityWeek = raw.city_latest?.week_start ?? null;
  return {
    cityCases,
    cityWeek,
    totalForecast: raw.total_forecasted_cases,
    topBarangays: raw.barangay_latest
      .sort((a: any, b: any) => (b.forecast ?? 0) - (a.forecast ?? 0))
      .slice(0, 3)
      .map((b: any) => ({
        name: b.name,
        forecast: b.forecast,
        cases: 0,
      })),
  };
}
