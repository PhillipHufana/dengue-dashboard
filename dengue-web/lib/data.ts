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
type Model = "preferred" | "final" | "hybrid" | "local";

// --------------------------------------
// 1. City timeseries
// --------------------------------------
export async function fetchCityTimeseries(
  freq: Freq = "weekly",
  model: Model = "preferred"
) {
  const res = await getTimeseries("city", { freq, model });

  return res.series.map((d: any) => ({
    date: d.date,
    cases: d.cases ?? 0,
    forecast: d.forecast ?? 0,
    isFuture: !!d.is_future,
  }));
}

// --------------------------------------
// 2. Barangay timeseries
// --------------------------------------
export async function fetchBarangayTimeseries(
  name: string,
  freq: Freq = "weekly",
  model: Model = "preferred"
) {
  const res = await getTimeseries("barangay", { name, freq, model });

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

  return {
    cityCases: raw.city_latest.city_cases,
    cityWeek: raw.city_latest.week_start,
    totalForecast: raw.total_forecasted_cases,
    topBarangays: raw.barangay_latest
      .sort((a: any, b: any) => (b.forecast ?? 0) - (a.forecast ?? 0))
      .slice(0, 3)
      .map((b: any) => ({
        name: b.name,
        forecast: b.forecast,
        cases: b.cases,
      })),
  };
}
