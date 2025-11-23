"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import type { FeatureCollection } from "geojson";

// Dynamic imports (no SSR)
const MapContainer = dynamic(
  () => import("react-leaflet").then((m) => m.MapContainer),
  { ssr: false }
);

const TileLayer = dynamic(
  () => import("react-leaflet").then((m) => m.TileLayer),
  { ssr: false }
);

const GeoJSON = dynamic(
  () => import("react-leaflet").then((m) => m.GeoJSON),
  { ssr: false }
);

const API = "http://127.0.0.1:8000";

// Colors based on dengue risk
function getRiskColor(risk?: string): string {
  switch (risk) {
    case "high":
      return "#d73027";
    case "medium":
      return "#fc8d59";
    case "low":
      return "#91cf60";
    default:
      return "#cccccc"; // no data
  }
}

export default function MapView({ onSelect }: { onSelect: (name: string) => void }) {
  const [polygons, setPolygons] = useState<FeatureCollection | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API}/geo/choropleth`);
        const json = await res.json();
        setPolygons(json);
      } catch (err) {
        console.error("Failed to load polygons", err);
      }
    }
    load();
  }, []);

  // Styling per polygon
  const style = (feature: any) => {
    const risk = feature.properties?.risk_level;
    return {
      fillColor: getRiskColor(risk),
      weight: 1,
      opacity: 1,
      color: "#ffffff",
      fillOpacity: 0.7,
    };
  };

  // Tooltip + click handler
  const onEachFeature = (feature: any, layer: any) => {
    const p = feature.properties || {};

    const name = p.name || "Unknown";
    const cases = p.latest_cases ?? "N/A";
    const week = p.latest_week ?? "N/A";
    const fcast = p.latest_forecast ?? "N/A";
    const fweek = p.latest_future_week ?? "N/A";
    const risk = p.risk_level ?? "unknown";

    const tooltip = `
      <div style="font-size:12px;">
        <b>${name.toUpperCase()}</b><br/>
        Risk: <b>${risk}</b><br/>
        Latest week: ${week}<br/>
        Cases: ${cases}<br/>
        Forecast week: ${fweek}<br/>
        Forecast: ${fcast}
      </div>
    `;

    layer.bindTooltip(tooltip, { sticky: true });

    layer.on("click", () => onSelect(name));
  };

  return (
    <MapContainer
      center={[7.0731, 125.6128]}
      zoom={11}
      style={{ height: "100vh", width: "100%" }}
    >
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />

      {polygons && (
        <GeoJSON
          data={polygons as any}
          style={style as any}
          onEachFeature={onEachFeature as any}
        />
      )}
    </MapContainer>
  );
}
