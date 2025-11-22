"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
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

const API_BASE = "http://127.0.0.1:8000";

function normalizeName(name: string | undefined | null): string {
  if (!name) return "";
  return name.trim().toLowerCase().replace(/[-_]+/g, " ");
}

function getColor(value: number | undefined): string {
  if (value === undefined || Number.isNaN(value)) return "#eeeeee";
  if (value < 5) return "#a1dab4";
  if (value < 15) return "#41b6c4";
  if (value < 30) return "#2c7fb8";
  return "#253494";
}

export default function MapView({ onSelect }: { onSelect: (name: string) => void }) {
  const [polygons, setPolygons] = useState<FeatureCollection | null>(null);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [L, setL] = useState<any>(null); // dynamically loaded Leaflet

  // Load Leaflet only on the client
  useEffect(() => {
    (async () => {
      const leaflet = await import("leaflet");
      setL(leaflet);
    })();
  }, []);

  // Load data
  useEffect(() => {
    async function load() {
      const [polyRes, foreRes] = await Promise.all([
        fetch(`${API_BASE}/geo/choropleth`),
        fetch(`${API_BASE}/forecast/weeks/1`)
      ]);

      const polyData = (await polyRes.json()) as FeatureCollection;
      const foreJson = await foreRes.json();
      const barangayRows: any[] = foreJson.barangays ?? [];

      const agg: Record<string, number> = {};
      for (const row of barangayRows) {
        const nameNorm = normalizeName(row.name);
        const val = Number(row.final_forecast);
        if (!Number.isFinite(val)) continue;
        agg[nameNorm] = val;
      }

      setPolygons(polyData);
      setStats(agg);
    }
    load();
  }, []);

  if (!L) return <div className="p-4">Loading map…</div>;

  const geoJsonStyle = (feature: any) => {
    const props = feature?.properties ?? {};
    const rawName =
      props.BARANGAY ||
      props.barangay ||
      props.NAME ||
      props.name ||
      props.brgy ||
      "";

    const value = stats[normalizeName(rawName)];

    return {
      fillColor: getColor(value),
      weight: 1,
      opacity: 1,
      color: "#555",
      fillOpacity: 0.7,
    };
  };

  const onEachFeature = (feature: any, layer: any) => {
    const props = feature?.properties ?? {};
    const rawName =
      props.BARANGAY ||
      props.barangay ||
      props.NAME ||
      props.name ||
      props.brgy ||
      "";

    const value = stats[normalizeName(rawName)];
    const label = `${rawName} — ${value ?? "no data"}`;

    layer.on("click", () => onSelect(rawName));

    layer.bindTooltip(label, { sticky: true });
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
          style={geoJsonStyle as any}
          onEachFeature={onEachFeature as any}
        />
      )}
    </MapContainer>
  );
}
