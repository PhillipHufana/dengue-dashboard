// components/MapView.tsx
"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { getTimeseries } from "@/lib/api";
import type { FeatureCollection } from "geojson";

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
  rangeStart,
  rangeEnd,
  citySeries,
}: {
  onSelect: (name: string) => void;
  freq: "weekly" | "monthly" | "yearly";
  model: "preferred" | "final" | "hybrid" | "local";
  rangeStart: number;
  rangeEnd: number;
  citySeries: any[];
}) {
  const [polygons, setPolygons] = useState<FeatureCollection | null>(null);
  const [barangayForecasts, setBarangayForecasts] = useState<Record<string, any[]>>(
    {}
  );

  const safeStart =
    citySeries.length === 0 ? 0 : Math.max(0, Math.min(rangeStart, citySeries.length - 1));
  const safeEnd =
    citySeries.length === 0
      ? 0
      : Math.max(safeStart, Math.min(rangeEnd, citySeries.length - 1));

  const selectedSlice =
    citySeries.length > 0 && safeEnd >= safeStart
      ? citySeries.slice(safeStart, safeEnd + 1)
      : [];

  const selectedDates = new Set(selectedSlice.map((d) => d.date));
  const anyFuture = selectedSlice.some((d) => d.is_future === true);

  // Load choropleth polygons once
  useEffect(() => {
    fetch("http://127.0.0.1:8000/geo/choropleth")
      .then((res) => res.json())
      .then((json) => {
        if (json.type === "FeatureCollection") setPolygons(json);
        else console.error("Invalid GeoJSON", json);
      })
      .catch((err) => console.error("Failed to load polygons", err));
  }, []);

  // Reset barangay series on freq/model change
  useEffect(() => {
    setBarangayForecasts({});
  }, [freq, model]);

// -------------------------------
// LOAD BARANGAY FORECAST SERIES (throttled)
// -------------------------------
useEffect(() => {
  if (!polygons) return;

  // If the selected range is entirely in the past,
  // we *only* use risk_level from choropleth and don't need per-barangay series.
  if (!anyFuture) return;

  // ✅ TS now knows this is non-null inside the effect body
  const feats = (polygons.features as any[]) || [];

  let cancelled = false;

  async function loadBarangaySeriesSequentially() {
    for (const f of feats) {
      if (cancelled) break;

      const nm = f.properties?.name;
      if (!nm) continue;

      // Skip if we already fetched this barangay
      if (barangayForecasts[nm]) continue;

      try {
        const data = await getTimeseries("barangay", { name: nm, freq, model });

        if (cancelled) break;

        setBarangayForecasts((prev) => {
          // Another iteration might have filled this while we awaited
          if (prev[nm]) return prev;
          return {
            ...prev,
            [nm]: data.series ?? [],
          };
        });
      } catch (err) {
        console.error("Failed to load barangay series", nm, err);
        // swallow error; map still works with risk_level-only fallback
      }
    }
  }

  loadBarangaySeriesSequentially();

  return () => {
    cancelled = true;
  };
  // IMPORTANT: don't depend on barangayForecasts to avoid infinite re-runs
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [polygons, freq, model, anyFuture]);



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

  function getRangeForecastForBarangay(nm: string) {
    const series = barangayForecasts[nm];
    if (!series || selectedSlice.length === 0) return 0;

    let sum = 0;
    for (const pt of series) {
      if (selectedDates.has(pt.date)) {
        const v = pt.forecast ?? pt.value ?? 0;
        sum += typeof v === "number" ? v : Number(v) || 0;
      }
    }
    return sum;
  }

  function style(feature: any) {
    const p = feature.properties;
    const riskColor = getRiskColor(p?.risk_level);

    const nm = p?.name;
    const forecastSum = getRangeForecastForBarangay(nm);

    // Past-only range → classic risk choropleth
    if (!anyFuture) {
      return {
        fillColor: riskColor,
        weight: 1,
        opacity: 1,
        color: "#ffffff",
        fillOpacity: 0.7,
      };
    }

    // Range includes future → overlay by forecast sum
    const overlayColor =
      forecastSum > 60
        ? "#b91c1c"
        : forecastSum > 30
        ? "#ef4444"
        : forecastSum > 10
        ? "#f59e0b"
        : forecastSum > 0
        ? "#84cc16"
        : "#e5e7eb";

    return {
      fillColor: overlayColor,
      weight: 1,
      opacity: 1,
      color: "#ffffff",
      fillOpacity: 0.7,
    };
  }

  function onEachFeature(feature: any, layer: any) {
    const p = feature.properties || {};
    const nm = p.name;
    const forecastSum = getRangeForecastForBarangay(nm);

    const tooltip = `
      <div style="font-size:12px;">
        <b>${p.name?.toUpperCase() ?? "Unknown"}</b><br/>
        Risk: <b>${p.risk_level ?? "unknown"}</b><br/>
        Latest week: ${p.latest_week ?? "N/A"}<br/>
        Cases: ${p.latest_cases ?? "N/A"}<br/>
        Forecast range total: ${forecastSum.toFixed(2)}
      </div>
    `;

    layer.bindTooltip(tooltip, { sticky: true });
    layer.on("click", () => onSelect(p.name));
  }

  if (!polygons) return <div>Loading map…</div>;

  return (
    <MapContainer center={[7.07, 125.6]} zoom={11} style={{ height: "100%", width: "100%" }}>
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <GeoJSON data={polygons as any} style={style as any} onEachFeature={onEachFeature as any} />
    </MapContainer>
  );
}
