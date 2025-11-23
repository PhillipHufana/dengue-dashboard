// lib/api.ts
const API_BASE = "http://127.0.0.1:8000";

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
  const safe = encodeURIComponent(name.trim().toLowerCase());
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
