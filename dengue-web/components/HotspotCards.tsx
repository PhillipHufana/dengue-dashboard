// "use client";

// import { useEffect, useState } from "react";

// const API = "http://127.0.0.1:8000";

// interface Hotspot {
//   name: string;
//   latest_cases: number;
//   latest_forecast: number;
//   risk_level: string;
//   growth: number;
// }

// export default function HotspotCards() {
//   const [items, setItems] = useState<Hotspot[]>([]);

//   useEffect(() => {
//     async function load() {
//       const res = await fetch(`${API}/hotspots/top?n=5`);
//       const json = await res.json();
//       setItems(json);
//     }
//     load();
//   }, []);

//   return (
//     <div className="p-4">
//       <h2 className="font-semibold text-lg mb-2">Emerging Hotspots</h2>

//       <div className="grid grid-cols-1 gap-3">
//         {items.map((h) => (
//           <div
//             key={h.name}
//             className="border rounded-lg p-3 bg-white shadow-sm"
//           >
//             <div className="font-semibold text-md capitalize">{h.name}</div>
//             <div className="text-sm text-gray-600">
//               Current cases: {h.latest_cases}
//             </div>
//             <div className="text-sm text-gray-600">
//               Forecast: {h.latest_forecast}
//             </div>

//             <div className="text-sm mt-2">
//               Risk level:{" "}
//               <span
//                 className={`px-2 py-1 rounded text-white ${
//                   h.risk_level === "high"
//                     ? "bg-red-600"
//                     : h.risk_level === "medium"
//                     ? "bg-orange-500"
//                     : "bg-green-600"
//                 }`}
//               >
//                 {h.risk_level}
//               </span>
//             </div>

//             <div className="text-sm mt-1">
//               Growth: <b>+{h.growth.toFixed(1)}</b>
//             </div>
//           </div>
//         ))}
//       </div>
//     </div>
//   );
// }
