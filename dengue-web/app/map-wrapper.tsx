import MapView from "@/components/MapView";
import { useState } from "react";

export default function MapWrapper() {
  const [selected, setSelected] = useState("");

  return (
    <MapView onSelect={(name: string) => setSelected(name)} />
  );
}

