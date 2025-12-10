// lib/api.ts
const API_BASE = "http://127.0.0.1:8000";

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


export async function getSummary() {
  const res = await fetch(`${API_BASE}/forecast/summary`);
  if (!res.ok) throw new Error("Failed to load summary");
  return res.json();
}

export async function getChoropleth() {
  const res = await fetch(`${API_BASE}/geo/choropleth`);
  if (!res.ok) throw new Error("Failed to load choropleth");
  return res.json();
}

export async function getBarangaySeries(name: string) {
  const safe = encodeURIComponent(cleanName(name));
  const res = await fetch(`${API_BASE}/forecast/barangay/${safe}`);

  if (!res.ok) {
    console.error("Barangay fetch failed", safe, res.status);
    throw new Error("Failed to load barangay series");
  }

  return res.json();
}

export async function getCitySeries() {
  const res = await fetch(`${API_BASE}/forecast/city`);
  if (!res.ok) throw new Error("Failed to load city series");
  return res.json();
}

export async function getForecastRankings(period: string): Promise<RankingResponse> {
  const res = await fetch(`${API_BASE}/forecast/rankings?period=${period}`);
  if (!res.ok) throw new Error("Failed to load rankings");232
  return res.json();
}

export interface RankingRow {
  name: string;
  pretty_name: string;
  total_forecast: number;
  risk_level: string;
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
}

export async function getTimeseries(
  level: "barangay" | "city",
  options: {
    name?: string;
    freq?: "weekly" | "monthly" | "yearly";
    model?: "preferred" | "final" | "hybrid" | "local";
  }
) {
  const params = new URLSearchParams();
  params.set("level", level);
  if (options.name) params.set("name", cleanName(options.name));
  params.set("freq", options.freq ?? "weekly");
  params.set("model", options.model ?? "preferred");

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
