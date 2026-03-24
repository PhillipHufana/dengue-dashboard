"use client";

import { useEffect } from "react";
import { useMap } from "react-leaflet";

interface MapFocusControllerProps {
  center: [number, number] | null;
  zoom?: number;
  focusToken: number;
}

export function MapFocusController({
  center,
  zoom = 13,
  focusToken,
}: MapFocusControllerProps) {
  const map = useMap();

  useEffect(() => {
    if (!center || focusToken <= 0) return;
    const nextZoom = Math.max(map.getZoom(), zoom);
    map.flyTo(center, nextZoom, {
      animate: true,
      duration: 0.6,
    });
  }, [center, focusToken, map, zoom]);

  return null;
}
