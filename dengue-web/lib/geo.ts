import { fetchBarangayPolygons } from "@/lib/data";

export interface BarangayGeo {
  id: string;
  name: string;
  polygon: [number, number][];
  cases: number;
  forecast: number;
  severity: {
    level: "low" | "medium" | "high" | "critical";
    fillColor: string;
  };
}

type SeverityLevel = "low" | "medium" | "high" | "critical";
type Severity = {
  level: SeverityLevel;
  fillColor: string;
};

export async function loadBarangayGeo(): Promise<BarangayGeo[]> {
  const geo = await fetchBarangayPolygons();

  return geo.features.map((feature: unknown, index: number) => {
    const f = feature as {
      geometry: { coordinates: number[][][] };
      properties: {
        id?: string;
        name?: string;
        latestCases?: number;
        latestForecast?: number;
      };
    };
    const coords = f.geometry.coordinates[0]; // polygon outer ring

    return {
      id: String(f.properties.id ?? index),
      name: f.properties.name ?? "",
      polygon: coords.map((pt: number[]) => [pt[1], pt[0]]), // Leaflet uses [lat,lng]
      cases: f.properties.latestCases ?? 0,
      forecast: f.properties.latestForecast ?? 0,
      severity: getSeverity(f.properties.latestCases ?? 0),
    };
  });
}

// same old severity
export function getSeverity(cases: number): Severity {
  if (cases > 250) return { level: "critical", fillColor: "#dc2626" };
  if (cases > 150) return { level: "high", fillColor: "#ea580c" };
  if (cases > 75) return { level: "medium", fillColor: "#ca8a04" };
  return { level: "low", fillColor: "#16a34a" };
}
