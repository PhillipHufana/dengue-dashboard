// lib/api.ts
const API_BASE = "http://127.0.0.1:8000";
import type { FeatureCollection, Geometry } from "geojson";
import type { TimePeriod } from "@/lib/store/dashboard-store";
export function cleanName(name: string): string {
  if (!name) return "";

  let x = name.toLowerCase().trim();

  // remove accents
  x = x.normalize("NFD").replace(/[\u0300-\u036f]/g, "");

  // remove (pob.) or any parentheses
  x = x.replace(/\(.*?\)/g, "");

  // convert hyphens to spaces
  x = x.replace(/-/g, " ");

  // remove punctuation
  x = x.replace(/[^a-z0-9 ]/g, "");

  // collapse multiple spaces
  x = x.replace(/\s+/g, " ").trim();

  return x;
}

export type RiskLevel = "low" | "medium" | "high" | "critical" | "unknown";
export type JenksClass = "very_low" | "low" | "medium" | "high" | "very_high" | "unknown";

export interface SummaryBarangayRow {
  name: string;           // canonical key
  forecast: number;
  week_start: string;
  risk_level: RiskLevel;

    // optional richer fields from backend (safe to keep optional)
  forecast_cases?: number | null;
  forecast_incidence_per_100k?: number | null;
  risk_level_cases?: RiskLevel;
  risk_level_incidence?: RiskLevel | null;

  // new sync fields
  period?: TimePeriod;
  weeks_to_sum?: number;
}

export type ChoroplethFeatureProps = {
  name: string;
  display_name: string;

  // legacy key (keep)
  risk_level: RiskLevel;
  latest_cases: number;
  latest_week: string | null;
  latest_forecast: number;
  latest_future_week: string | null;

  // new richer keys (safe optional)
  forecast_cases?: number | null;
  forecast_incidence_per_100k?: number | null;
  risk_level_cases?: RiskLevel;
  risk_level_incidence?: RiskLevel | null;

  // new sync fields
  period?: TimePeriod;
  weeks_to_sum?: number;
  period_start_week?: string | null;

  run_id: string;
  model_name: string;
  horizon_type: "future";
};

export type ChoroplethFC = FeatureCollection<Geometry, ChoroplethFeatureProps>;

export interface SummaryResponse {
  run_id: string;
  model_name: string;
  horizon_type: "future";
  data_last_updated: string | null;
  city_latest: any | null;
  total_forecasted_cases: number;
  barangay_latest: SummaryBarangayRow[];

  // new
  period?: TimePeriod;
  weeks_to_sum?: number;
}

export async function getSummary(options?: {
  runId?: string;
  modelName?: string;
  period?: TimePeriod;
}): Promise<SummaryResponse> {
  const params = new URLSearchParams();
  if (options?.runId) params.set("run_id", options.runId);
  if (options?.modelName) params.set("model_name", options.modelName);
  if (options?.period) params.set("period", options.period);

  const url = params.toString()
    ? `${API_BASE}/forecast/summary?${params.toString()}`
    : `${API_BASE}/forecast/summary`;

  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to load summary");
  return res.json();
}

export async function getDataInfo(): Promise<{
  last_historical_date: string | null;
  server_date: string;
  run_id?: string;
}> {
  const res = await fetch(`${API_BASE}/data/info`);
  if (!res.ok) throw new Error("Failed to load data info");
  return res.json();
}

export async function getChoropleth(options?: {
  runId?: string;
  modelName?: string;
  period?: TimePeriod;
}): Promise<ChoroplethFC> {
  const params = new URLSearchParams();
  if (options?.runId) params.set("run_id", options.runId);
  if (options?.modelName) params.set("model_name", options.modelName);
  if (options?.period) params.set("period", options.period);

  const url = params.toString()
    ? `${API_BASE}/geo/choropleth?${params.toString()}`
    : `${API_BASE}/geo/choropleth`;

  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to load choropleth");
  return res.json();
}

export async function getBarangaySeries(
  name: string,
  options?: { runId?: string; modelName?: string; horizonType?: "test" | "future" }
) {
  const safe = encodeURIComponent(cleanName(name));
  const params = new URLSearchParams();
  if (options?.runId) params.set("run_id", options.runId);
  if (options?.modelName) params.set("model_name", options.modelName);
  if (options?.horizonType) params.set("horizon_type", options.horizonType);

  const url = params.toString()
    ? `${API_BASE}/forecast/barangay/${safe}?${params.toString()}`
    : `${API_BASE}/forecast/barangay/${safe}`;

  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to load barangay series");
  return res.json();
}


export async function getCitySeries() {
  const res = await fetch(`${API_BASE}/forecast/city`);
  if (!res.ok) throw new Error("Failed to load city series");
  return res.json();
}

export interface RankingRow {
  name: string;
  pretty_name: string;

  total_forecast: number;
  risk_level: string;

  total_forecast_cases: number;
  total_forecast_incidence_per_100k: number | null;
  risk_level_cases: string;
  risk_level_incidence: string | null;

  cases_class?: string;
  burden_class?: string;

  trend: number;
  this_week: number | null;
  last_week: number | null;
  trend_source: string;
  trend_message: string;
}

export interface RankingResponse {
  period: string;
  model_current_date: string | null;
  user_current_date: string;
  data_last_updated: string | null;
  rankings: RankingRow[];
  run_id: string;
  model_name: string;
  horizon_type: "future";
}

export async function getForecastRankings(
  period: string,
  options?: { runId?: string; modelName?: string }
): Promise<RankingResponse> {
  const params = new URLSearchParams();
  params.set("period", period);
  if (options?.runId) params.set("run_id", options.runId);
  if (options?.modelName) params.set("model_name", options.modelName);

  const res = await fetch(`${API_BASE}/forecast/rankings?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to load rankings");
  return res.json();
}


export async function getRuns() {
  const res = await fetch(`${API_BASE}/forecast/runs`);
  if (!res.ok) throw new Error("Failed to load runs");
  return res.json();
}

export async function getModels(runId?: string) {
  const url = runId
    ? `${API_BASE}/forecast/models?run_id=${encodeURIComponent(runId)}`
    : `${API_BASE}/forecast/models`;
  const res = await fetch(url);
  if (!res.ok) throw new Error("Failed to load models");
  return res.json();
}


export async function getTimeseries(
  level: "barangay" | "city",
  options: {
    name?: string;
    freq?: "weekly" | "monthly" | "yearly";
    runId?: string;
    modelName?: string;
    horizonType?: "test" | "future";
  }
) {
  const params = new URLSearchParams();
  params.set("level", level);
  if (options.name) params.set("name", cleanName(options.name));
  params.set("freq", options.freq ?? "weekly");
  params.set("model_name", options.modelName ?? "preferred");
  params.set("horizon_type", options.horizonType ?? "future");
  if (options.runId) params.set("run_id", options.runId);


  const url = `${API_BASE}/timeseries?${params.toString()}`;

  try {
    console.log("[getTimeseries] Fetching:", url);
    const res = await fetch(url);

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      console.error(
        "[getTimeseries] HTTP error",
        res.status,
        res.statusText,
        text
      );
      throw new Error(`Failed to load timeseries: ${res.status}`);
    }

    const json = await res.json();
    return json;
  } catch (err) {
    console.error("[getTimeseries] Network/Fetch error for URL:", url, err);
    throw err;
  }
}

