"use client"

import { useState, useMemo } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Line, LineChart, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from "recharts"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { TrendingUp, Brain, Activity, MapPin } from "lucide-react"
import { barangays } from "./leaflet-map-client"

const generateCityForecastData = () => {
  const data = []
  const startDate = new Date("2025-09-01")

  for (let i = 0; i < 120; i++) {
    const date = new Date(startDate)
    date.setDate(date.getDate() + i)

    const isHistorical = i < 90
    const seasonalFactor = Math.sin((i / 30) * Math.PI) * 300
    const trend = i * 2
    const baseValue = 1500 + trend + seasonalFactor

    const actual = isHistorical ? Math.floor(baseValue + (Math.random() - 0.5) * 400) : null
    const arima = Math.floor(baseValue + (Math.random() - 0.5) * 200 + (isHistorical ? 0 : 100))
    const prophet = Math.floor(baseValue + (Math.random() - 0.5) * 250 + (isHistorical ? 0 : 50))

    data.push({
      date: date.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      fullDate: date.toISOString(),
      actual,
      arima,
      prophet,
      isHistorical,
      arimaLower: arima - 150,
      arimaUpper: arima + 150,
      prophetLower: prophet - 180,
      prophetUpper: prophet + 180,
    })
  }

  return data
}

const cityData = generateCityForecastData()

function CustomTooltip({ active, payload, label }: any) {
  if (active && payload && payload.length) {
    const dataPoint = payload[0]?.payload
    return (
      <div className="rounded-lg border border-border bg-background p-2 md:p-3 shadow-lg text-xs md:text-sm">
        <p className="mb-1.5 md:mb-2 font-semibold border-b border-border pb-1.5 md:pb-2">{label}</p>
        <div className="space-y-1 md:space-y-1.5">
          {payload.map((entry: any, index: number) => {
            if (entry.value === null) return null
            return (
              <div key={index} className="flex items-center justify-between gap-3 md:gap-4">
                <div className="flex items-center gap-1.5 md:gap-2">
                  <div className="h-2 w-2 md:h-2.5 md:w-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
                  <span className="text-muted-foreground">{entry.name}</span>
                </div>
                <span className="font-medium" style={{ color: entry.color }}>
                  {entry.value?.toLocaleString()}
                </span>
              </div>
            )
          })}
        </div>
        {!dataPoint?.isHistorical && (
          <p className="mt-1.5 md:mt-2 text-[10px] md:text-xs text-muted-foreground italic border-t border-border pt-1.5 md:pt-2">
            Forecast period
          </p>
        )}
      </div>
    )
  }
  return null
}

interface ForecastChartProps {
  selectedBarangayId: number | null
}

export function ForecastChart({ selectedBarangayId }: ForecastChartProps) {
  const [showActual, setShowActual] = useState(true)
  const [showArima, setShowArima] = useState(true)
  const [showProphet, setShowProphet] = useState(true)

  const { data, locationName, isBarangay } = useMemo(() => {
    if (selectedBarangayId) {
      const barangay = barangays.find((b) => b.id === selectedBarangayId)
      if (barangay) {
        return {
          data: barangay.forecastData,
          locationName: barangay.name,
          isBarangay: true,
        }
      }
    }
    return {
      data: cityData,
      locationName: "City-Wide (All 182 Barangays)",
      isBarangay: false,
    }
  }, [selectedBarangayId])

  const forecastStartIndex = data.findIndex((d) => !d.isHistorical)
  const forecastStartDate = data[forecastStartIndex]?.date

  return (
    <Card className="bg-card border-border">
      <CardHeader className="p-3 pb-2 md:p-6 md:pb-2">
        <div className="flex flex-col gap-2 md:gap-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2 flex-wrap">
              <CardTitle className="text-base md:text-lg font-semibold">Predictive Forecast</CardTitle>
              <Badge variant="secondary" className="text-[10px] md:text-xs">
                30-Day
              </Badge>
            </div>
            <div className="flex items-center gap-1.5 md:gap-2 px-2 md:px-3 py-1 md:py-1.5 rounded-full bg-secondary/50 border border-border max-w-full overflow-hidden">
              <MapPin
                className={`h-3 w-3 md:h-3.5 md:w-3.5 flex-shrink-0 ${isBarangay ? "text-primary" : "text-muted-foreground"}`}
              />
              <span
                className={`text-xs md:text-sm font-medium truncate ${isBarangay ? "text-primary" : "text-muted-foreground"}`}
              >
                {isBarangay ? locationName : "City-Wide"}
              </span>
            </div>
          </div>

          {!isBarangay && (
            <p className="text-[10px] md:text-xs text-muted-foreground">
              Tap a barangay on the map to view its forecast
            </p>
          )}

          <div className="flex flex-wrap items-center gap-3 md:gap-4 rounded-lg bg-secondary/50 p-2 md:p-3">
            <div className="flex items-center gap-1.5 md:gap-2">
              <Switch
                id="actual"
                checked={showActual}
                onCheckedChange={setShowActual}
                className="data-[state=checked]:bg-emerald-500 scale-90 md:scale-100"
              />
              <Label htmlFor="actual" className="flex items-center gap-1 md:gap-1.5 text-xs md:text-sm cursor-pointer">
                <Activity className="h-3 w-3 md:h-3.5 md:w-3.5 text-emerald-500" />
                <span className="hidden xs:inline">Actual</span>
              </Label>
            </div>
            <div className="flex items-center gap-1.5 md:gap-2">
              <Switch
                id="arima"
                checked={showArima}
                onCheckedChange={setShowArima}
                className="data-[state=checked]:bg-[#d4a847] scale-90 md:scale-100"
              />
              <Label htmlFor="arima" className="flex items-center gap-1 md:gap-1.5 text-xs md:text-sm cursor-pointer">
                <TrendingUp className="h-3 w-3 md:h-3.5 md:w-3.5 text-[#d4a847]" />
                <span>ARIMA</span>
              </Label>
            </div>
            <div className="flex items-center gap-1.5 md:gap-2">
              <Switch
                id="prophet"
                checked={showProphet}
                onCheckedChange={setShowProphet}
                className="data-[state=checked]:bg-[#8b5cf6] scale-90 md:scale-100"
              />
              <Label htmlFor="prophet" className="flex items-center gap-1 md:gap-1.5 text-xs md:text-sm cursor-pointer">
                <Brain className="h-3 w-3 md:h-3.5 md:w-3.5 text-[#8b5cf6]" />
                <span>Prophet</span>
              </Label>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-3 pt-0 md:p-6 md:pt-0">
        <div className="h-[220px] md:h-[320px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 10, right: 5, left: -15, bottom: 0 }}>
              <defs>
                <linearGradient id="actualGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fill: "#888", fontSize: 9 }}
                axisLine={{ stroke: "#333" }}
                tickLine={false}
                interval={19}
              />
              <YAxis
                tick={{ fill: "#888", fontSize: 9 }}
                axisLine={{ stroke: "#333" }}
                tickLine={false}
                tickFormatter={(value) => (isBarangay ? value.toString() : `${(value / 1000).toFixed(1)}K`)}
                domain={["dataMin - 10", "dataMax + 10"]}
                width={35}
              />
              <Tooltip content={<CustomTooltip />} />

              <ReferenceLine
                x={forecastStartDate}
                stroke="#666"
                strokeDasharray="5 5"
                label={{
                  value: "Forecast",
                  position: "top",
                  fill: "#888",
                  fontSize: 10,
                }}
              />

              {showActual && (
                <Line
                  type="monotone"
                  dataKey="actual"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={false}
                  name="Actual Cases"
                  connectNulls={false}
                />
              )}

              {showArima && (
                <Line
                  type="monotone"
                  dataKey="arima"
                  stroke="#d4a847"
                  strokeWidth={1.5}
                  strokeDasharray="5 5"
                  dot={false}
                  name="ARIMA Forecast"
                />
              )}

              {showProphet && (
                <Line
                  type="monotone"
                  dataKey="prophet"
                  stroke="#8b5cf6"
                  strokeWidth={1.5}
                  strokeDasharray="3 3"
                  dot={false}
                  name="Prophet Forecast"
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="mt-3 md:mt-4 flex flex-wrap items-center justify-center gap-3 md:gap-4 text-[10px] md:text-xs">
          {showActual && (
            <div className="flex items-center gap-1.5 md:gap-2">
              <div className="h-0.5 w-4 md:w-5 bg-emerald-500" />
              <span className="text-muted-foreground">Actual</span>
            </div>
          )}
          {showArima && (
            <div className="flex items-center gap-1.5 md:gap-2">
              <div
                className="h-0.5 w-4 md:w-5 bg-[#d4a847]"
                style={{
                  backgroundImage:
                    "repeating-linear-gradient(90deg, #d4a847 0px, #d4a847 4px, transparent 4px, transparent 8px)",
                }}
              />
              <span className="text-muted-foreground">ARIMA</span>
            </div>
          )}
          {showProphet && (
            <div className="flex items-center gap-1.5 md:gap-2">
              <div
                className="h-0.5 w-4 md:w-5 bg-[#8b5cf6]"
                style={{
                  backgroundImage:
                    "repeating-linear-gradient(90deg, #8b5cf6 0px, #8b5cf6 3px, transparent 3px, transparent 6px)",
                }}
              />
              <span className="text-muted-foreground">Prophet</span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
