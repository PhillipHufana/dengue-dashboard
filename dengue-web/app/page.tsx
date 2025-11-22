// app/page.tsx
import dynamic from "next/dynamic";

// Prevent SSR (Leaflet requires browser)
const MapView = dynamic(() => import("../components/MapView"), {
  ssr: false,
});

export default function Page() {
  return (
    <div style={{ height: "100vh", width: "100vw" }}>
      <MapView />
    </div>
  );
}
