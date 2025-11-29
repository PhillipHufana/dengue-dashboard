"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { getTimeseries } from "@/lib/api";
import type { FeatureCollection } from "geojson";

// Dynamic imports (Leaflet)
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

export default function MapView({
  onSelect,
  freq,
  model,
  timeIndex,
  citySeries,
}: {
  onSelect: (name: string) => void;
  freq: "weekly" | "monthly" | "yearly";
  model: "preferred" | "final" | "hybrid" | "local";
  timeIndex: number;
  citySeries: any[];
}) {
  const [polygons, setPolygons] = useState<FeatureCollection | null>(null);
  const [barangayForecasts, setBarangayForecasts] = useState<
    Record<string, any[]>
  >({});

  // Safe date
  const safeIndex = Math.min(timeIndex, citySeries.length - 1);
  const selectedDate = citySeries?.[safeIndex]?.date ?? null;

  // -------------------------------
  // LOAD CHOROPLETH GEOJSON
  // -------------------------------
  useEffect(() => {
    fetch("http://127.0.0.1:8000/geo/choropleth")
      .then((res) => res.json())
      .then((json) => {
        if (json.type === "FeatureCollection") setPolygons(json);
        else console.error("Invalid GeoJSON", json);
      })
      .catch((err) => console.error("Failed to load polygons", err));
  }, []);

  // -------------------------------
  // LOAD BARANGAY FORECAST SERIES
  // -------------------------------
  useEffect(() => {
    if (!polygons) return;

    polygons.features.forEach((f: any) => {
      const nm = f.properties?.name;
      if (!nm) return;
      if (barangayForecasts[nm]) return;

      getTimeseries("barangay", { name: nm, freq, model })
        .then((data) => {
          setBarangayForecasts((prev) => ({
            ...prev,
            [nm]: data.series ?? [],
          }));
        })
        .catch(() => {});
    });
  }, [polygons, freq, model]);

  // -------------------------------
  // HELPERS
  // -------------------------------
  function getForecastForBarangay(nm: string) {
    const series = barangayForecasts[nm];
    if (!series || !selectedDate) return 0;

    const match = series.find((x) => x.date === selectedDate);
    return match?.forecast ?? 0;
  }

  function getRiskColor(risk?: string): string {
    switch (risk) {
      case "high":
        return "#d73027";
      case "medium":
        return "#fc8d59";
      case "low":
        return "#91cf60";
      default:
        return "#cccccc";
    }
  }

  // -------------------------------
  // STYLING
  // -------------------------------
  function style(feature: any) {
    const p = feature.properties;
    const riskColor = getRiskColor(p?.risk_level);

    const nm = p?.name;
    const forecastValue = getForecastForBarangay(nm);

    const isFuture = citySeries?.[safeIndex]?.is_future ?? false;

    // If it's not future → show risk map
    if (!isFuture) {
      return {
        fillColor: riskColor,
        weight: 1,
        opacity: 1,
        color: "#ffffff",
        fillOpacity: 0.7,
      };
    }

    // Future → use forecast overlay
    const overlayColor =
      forecastValue > 15 ? "#ef4444" :
      forecastValue > 5  ? "#f59e0b" :
                          "#22c55e";

    return {
      fillColor: overlayColor,
      weight: 1,
      opacity: 1,
      color: "#ffffff",
      fillOpacity: 0.7,
    };
  }



  // -------------------------------
  // POPUP + TOOLTIP
  // -------------------------------
  function onEachFeature(feature: any, layer: any) {
    const p = feature.properties || {};

    const tooltip = `
      <div style="font-size:12px;">
        <b>${p.name?.toUpperCase() ?? "Unknown"}</b><br/>
        Risk: <b>${p.risk_level ?? "unknown"}</b><br/>
        Latest week: ${p.latest_week ?? "N/A"}<br/>
        Cases: ${p.latest_cases ?? "N/A"}<br/>
        Forecast week: ${p.latest_future_week ?? "N/A"}<br/>
        Forecast: ${p.latest_forecast ?? "N/A"}
      </div>
    `;

    layer.bindTooltip(tooltip, { sticky: true });
    layer.on("click", () => onSelect(p.name));
  }

  if (!polygons) return <div>Loading map…</div>;

  return (
    <MapContainer
      center={[7.07, 125.6]}
      zoom={11}
      style={{ height: "100%", width: "100%" }}
    >
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />

      <GeoJSON data={polygons as any} style={style} onEachFeature={onEachFeature} />
    </MapContainer>
  );
}
