"use client";

import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import { useEffect, useState } from "react";

export default function MapView() {
  const [boundaries, setBoundaries] = useState<any | null>(null);

  useEffect(() => {
    async function load() {
      const res = await fetch("http://127.0.0.1:8000/geo/boundaries");
      const data = await res.json();
      setBoundaries(data);
    }
    load();
  }, []);

  return (
    <MapContainer
      center={[7.0731, 125.6128]}
      zoom={11}
      style={{ height: "100vh", width: "100%" }}
    >
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {boundaries && <GeoJSON data={boundaries} />}
    </MapContainer>
  );
}
