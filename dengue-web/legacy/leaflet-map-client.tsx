"use client"

import { useEffect, useState } from "react"
import type { LatLngExpression } from "leaflet"

// Generate 182 barangays with polygon coordinates
const generateBarangayPolygons = () => {
  const barangayNames = [
    "Poblacion",
    "San Jose",
    "San Antonio",
    "San Isidro",
    "Santo Niño",
    "Sta. Cruz",
    "Sta. Maria",
    "San Miguel",
    "San Rafael",
    "San Vicente",
    "Bagumbayan",
    "Maligaya",
    "Mabuhay",
    "Kamuning",
    "Barangka",
    "Plainview",
    "Addition Hills",
    "Highway Hills",
    "Burol",
    "Paliparan",
    "Langkaan",
    "Salawag",
    "Sampaloc",
    "Sabang",
    "Salitran",
    "Datu",
    "Fatima",
    "San Agustin",
    "San Dionisio",
    "San Francisco",
    "San Juan",
    "San Nicolas",
    "San Pedro",
    "San Roque",
    "Santa Ana",
    "Santa Barbara",
    "Santa Elena",
    "Santa Lucia",
    "Santa Monica",
    "Santa Rosa",
    "Santiago",
    "Santo Cristo",
    "Santo Domingo",
    "Assumption",
    "Bel-Air",
    "Cembo",
    "Comembo",
    "Dasmariñas",
    "East Rembo",
    "Forbes Park",
    "Guadalupe Nuevo",
    "Guadalupe Viejo",
    "Kasilawan",
    "La Paz",
    "Magallanes",
    "Olympia",
    "Palanan",
    "Pio del Pilar",
    "Pitogo",
    "Post Proper North",
    "Post Proper South",
    "Rizal",
    "San Isidro Labrador",
    "Santa Clara",
    "Singkamas",
    "South Cembo",
    "Tejeros",
    "Valenzuela",
    "West Rembo",
    "Bangkal",
    "Buting",
    "Carmona",
    "Dela Paz",
    "East Kamias",
    "Escopa",
    "Kapasigan",
    "Kapitolyo",
    "Manggahan",
    "Maybunga",
    "Oranbo",
    "Pasig",
    "Pinagbuhatan",
    "Pineda",
    "Rosario",
    "Sagad",
    "San Joaquin",
    "Santa Lucia Old",
    "Santolan",
    "Sumilang",
    "Ugong",
    "Bambang",
    "Bignay",
    "Caniogan",
    "Concepcion",
    "Dulong Bayan",
    "Gulod",
    "Malanday",
    "Malis",
    "Panghulo",
    "Potrero",
    "Sta. Clara Del Monte",
    "Sto. Cristo",
    "Sto. Rosario",
    "Tugatog",
    "Ubihan",
    "Baesa",
    "Bagong Barrio",
    "Balintawak",
    "Capri",
    "Coloong",
    "Deparo",
    "Gen. T. de Leon",
    "Isla",
    "Karuhatan",
    "Lawang Bato",
    "Lingunan",
    "Mabolo",
    "Malanday Norte",
    "Malinta",
    "Mapulang Lupa",
    "Marulas",
    "Maysan",
    "Parada",
    "Pariancillo Villa",
    "Paso de Blas",
    "Pasolo",
    "Poblacion Norte",
    "Poblacion Sur",
    "Polo",
    "Punturin",
    "Rincon",
    "Tagalag",
    "Ugong Norte",
    "Viente Reales",
    "Wawang Pulo",
    "Arkong Bato",
    "Balangkas",
    "Bignay Sur",
    "Bisig",
    "Canumay",
    "Coloong Sur",
    "Dalandanan",
    "Hen. de Leon",
    "Isla Norte",
    "Isla Sur",
    "Karuhatan Sur",
    "Lawang Bato Sur",
    "Lingunan Sur",
    "Mabolo Sur",
    "Malanday Sur",
    "Malinta Sur",
    "Mapulang Lupa Sur",
    "Marulas Sur",
    "Maysan Sur",
    "Parada Sur",
    "Pasolo Sur",
    "Polo Sur",
    "Punturin Sur",
    "Rincon Sur",
    "Tagalag Sur",
    "Ugong Sur",
    "Veinte Reales Sur",
    "Bagong Silang",
    "Batasan Hills",
    "Commonwealth",
    "Holy Spirit",
    "Payatas",
    "Bagong Pag-asa",
    "Bahay Toro",
    "Balingasa",
    "Bungad",
    "Damar",
    "Damayan",
    "Del Monte",
    "Katipunan",
    "Lourdes",
    "Maharlika",
    "Manresa",
    "Masambong",
    "N.S. Amoranto",
    "Nayong Kanluran",
    "Paang Bundok",
    "Pag-ibig sa Nayon",
    "Paltok",
    "Paraiso",
    "Phil-Am",
    "Project 6",
    "Ramon Magsaysay",
    "Saint Peter",
  ]

  const cols = 14
  const baseLat = 14.55
  const baseLng = 120.98
  const cellSize = 0.012

  return barangayNames.slice(0, 182).map((name, i) => {
    const row = Math.floor(i / cols)
    const col = i % cols
    const offsetLat = (Math.random() - 0.5) * 0.002
    const offsetLng = (Math.random() - 0.5) * 0.002
    const centerLat = baseLat + row * cellSize + offsetLat
    const centerLng = baseLng + col * cellSize + offsetLng
    const polySize = cellSize * 0.45

    const polygon: [number, number][] = [
      [centerLat + polySize, centerLng],
      [centerLat + polySize * 0.5, centerLng + polySize * 0.866],
      [centerLat - polySize * 0.5, centerLng + polySize * 0.866],
      [centerLat - polySize, centerLng],
      [centerLat - polySize * 0.5, centerLng - polySize * 0.866],
      [centerLat + polySize * 0.5, centerLng - polySize * 0.866],
    ]

    const weeklyData = Array.from({ length: 12 }, (_, weekIdx) => {
      const baseCases = Math.floor(Math.random() * 300) + 20
      const seasonalFactor = 1 + Math.sin((weekIdx / 12) * Math.PI) * 0.5
      return Math.floor(baseCases * seasonalFactor)
    })

    const seed = i + 1
    const forecastData = generateBarangayForecastData(seed, name)

    return {
      id: i + 1,
      name,
      center: [centerLat, centerLng] as [number, number],
      polygon,
      weeklyData,
      forecastData,
    }
  })
}

function generateBarangayForecastData(seed: number, name: string) {
  const data = []
  const startDate = new Date("2025-09-01")

  // Use seed to create unique but consistent data per barangay
  const baseCases = 10 + (seed % 50)
  const volatility = 0.3 + (seed % 10) / 20
  const trend = (seed % 3) - 1 // -1, 0, or 1

  for (let i = 0; i < 120; i++) {
    const date = new Date(startDate)
    date.setDate(date.getDate() + i)

    const isHistorical = i < 90
    const seasonalFactor = Math.sin((i / 30) * Math.PI) * (baseCases * 0.5)
    const trendValue = trend * i * 0.1
    const baseValue = baseCases + trendValue + seasonalFactor

    // Seeded random function
    const seededRandom = (offset: number) => {
      const x = Math.sin(seed * 9999 + i * 100 + offset) * 10000
      return x - Math.floor(x)
    }

    const actual = isHistorical
      ? Math.max(0, Math.floor(baseValue + (seededRandom(1) - 0.5) * baseCases * volatility))
      : null
    const arima = Math.max(
      0,
      Math.floor(
        baseValue + (seededRandom(2) - 0.5) * baseCases * volatility * 0.5 + (isHistorical ? 0 : baseCases * 0.1),
      ),
    )
    const prophet = Math.max(
      0,
      Math.floor(
        baseValue + (seededRandom(3) - 0.5) * baseCases * volatility * 0.6 + (isHistorical ? 0 : baseCases * 0.05),
      ),
    )

    data.push({
      date: date.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      fullDate: date.toISOString(),
      actual,
      arima,
      prophet,
      isHistorical,
      arimaLower: Math.max(0, arima - Math.floor(baseCases * 0.3)),
      arimaUpper: arima + Math.floor(baseCases * 0.3),
      prophetLower: Math.max(0, prophet - Math.floor(baseCases * 0.35)),
      prophetUpper: prophet + Math.floor(baseCases * 0.35),
    })
  }

  return data
}

const barangays = generateBarangayPolygons()

const getSeverity = (cases: number) => {
  if (cases > 250) return { level: "critical", color: "#dc2626", fillColor: "#dc2626" }
  if (cases > 150) return { level: "high", color: "#ea580c", fillColor: "#ea580c" }
  if (cases > 75) return { level: "medium", color: "#ca8a04", fillColor: "#ca8a04" }
  return { level: "low", color: "#16a34a", fillColor: "#16a34a" }
}

interface LeafletMapClientProps {
  selectedWeek: number
  mapView: "choropleth" | "hotspots"
  selectedBarangayId: number | null
  onBarangaySelect: (barangayId: number | null) => void
}

export function LeafletMapClient({
  selectedWeek,
  mapView,
  selectedBarangayId,
  onBarangaySelect,
}: LeafletMapClientProps) {
  const [mapComponents, setMapComponents] = useState<{
    MapContainer: any
    TileLayer: any
    Polygon: any
    CircleMarker: any
    Tooltip: any
  } | null>(null)

  useEffect(() => {
    const loadLeaflet = async () => {
      const L = await import("leaflet")
      const { MapContainer, TileLayer, Polygon, CircleMarker, Tooltip } = await import("react-leaflet")

      delete (L.Icon.Default.prototype as any)._getIconUrl
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
        iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
        shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
      })

      setMapComponents({ MapContainer, TileLayer, Polygon, CircleMarker, Tooltip })
    }

    loadLeaflet()
  }, [])

  const currentData = barangays.map((b) => ({
    ...b,
    cases: b.weeklyData[selectedWeek],
    severity: getSeverity(b.weeklyData[selectedWeek]),
  }))

  if (!mapComponents) {
    return (
      <div className="flex items-center justify-center h-full bg-secondary/30 rounded-lg">
        <div className="text-muted-foreground">Loading map...</div>
      </div>
    )
  }

  const { MapContainer, TileLayer, Polygon, CircleMarker, Tooltip } = mapComponents
  const mapCenter: LatLngExpression = [14.62, 121.05]

  return (
    <MapContainer center={mapCenter} zoom={12} style={{ height: "100%", width: "100%" }} className="z-0">
      <TileLayer
        attribution='&copy; <a href="https://carto.com/">CARTO</a>'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      />
      {currentData.map((barangay) => {
        const isSelected = selectedBarangayId === barangay.id

        if (mapView === "choropleth") {
          return (
            <Polygon
              key={barangay.id}
              positions={barangay.polygon}
              pathOptions={{
                fillColor: barangay.severity.fillColor,
                fillOpacity: isSelected ? 0.95 : 0.7,
                color: isSelected ? "#ffffff" : "#ffffff",
                weight: isSelected ? 3 : 1,
                opacity: isSelected ? 1 : 0.5,
              }}
              eventHandlers={{
                click: () => {
                  // Toggle selection: if already selected, deselect (show city-wide)
                  onBarangaySelect(isSelected ? null : barangay.id)
                },
              }}
            >
              <Tooltip sticky>
                <div className="text-sm">
                  <div className="font-semibold">{barangay.name}</div>
                  <div className="flex items-center gap-1 mt-1">
                    <span
                      className="inline-block w-2 h-2 rounded-full"
                      style={{ backgroundColor: barangay.severity.color }}
                    />
                    <span className="capitalize">{barangay.severity.level}</span>
                  </div>
                  <div className="font-bold mt-1">{barangay.cases} cases</div>
                  <div className="text-xs text-muted-foreground mt-1">Click to view forecast</div>
                </div>
              </Tooltip>
            </Polygon>
          )
        }

        const radius = Math.max(5, Math.min(20, barangay.cases / 15))
        return (
          <CircleMarker
            key={barangay.id}
            center={barangay.center}
            radius={isSelected ? radius * 1.3 : radius}
            pathOptions={{
              fillColor: barangay.severity.fillColor,
              fillOpacity: isSelected ? 1 : 0.8,
              color: isSelected ? "#ffffff" : barangay.severity.color,
              weight: isSelected ? 3 : 2,
              opacity: 1,
            }}
            eventHandlers={{
              click: () => {
                onBarangaySelect(isSelected ? null : barangay.id)
              },
            }}
          >
            <Tooltip sticky>
              <div className="text-sm">
                <div className="font-semibold">{barangay.name}</div>
                <div className="flex items-center gap-1 mt-1">
                  <span
                    className="inline-block w-2 h-2 rounded-full"
                    style={{ backgroundColor: barangay.severity.color }}
                  />
                  <span className="capitalize">{barangay.severity.level}</span>
                </div>
                <div className="font-bold mt-1">{barangay.cases} cases</div>
                <div className="text-xs text-muted-foreground mt-1">Click to view forecast</div>
              </div>
            </Tooltip>
          </CircleMarker>
        )
      })}
    </MapContainer>
  )
}

// Export barangays data and utility functions for parent component
export { barangays, getSeverity }
