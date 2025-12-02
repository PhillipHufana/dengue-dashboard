"use client"

import { useState, useMemo } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TrendingUp, Search, MapPin, AlertTriangle, ChevronUp, ChevronDown, Brain, Activity } from "lucide-react"
import { barangays } from "./leaflet-map-client"

type TimePeriod = "1w" | "2w" | "1m" | "3m" | "6m" | "1y"
type ForecastModel = "arima" | "prophet" | "average"

interface ForecastRankingsProps {
  selectedBarangayId: number | null
  onBarangaySelect: (barangayId: number | null) => void
}

const timePeriodDays: Record<TimePeriod, number> = {
  "1w": 7,
  "2w": 14,
  "1m": 30,
  "3m": 90,
  "6m": 180,
  "1y": 365,
}

const timePeriodLabels: Record<TimePeriod, string> = {
  "1w": "1 Week",
  "2w": "2 Weeks",
  "1m": "1 Month",
  "3m": "3 Months",
  "6m": "6 Months",
  "1y": "1 Year",
}

export function ForecastRankings({ selectedBarangayId, onBarangaySelect }: ForecastRankingsProps) {
  const [timePeriod, setTimePeriod] = useState<TimePeriod>("1m")
  const [forecastModel, setForecastModel] = useState<ForecastModel>("average")
  const [searchQuery, setSearchQuery] = useState("")
  const [showAll, setShowAll] = useState(false)

  const rankedBarangays = useMemo(() => {
    const days = timePeriodDays[timePeriod]

    return barangays
      .map((barangay) => {
        // Get forecast data (non-historical entries)
        const forecastEntries = barangay.forecastData.filter((d) => !d.isHistorical)

        // Limit to the time period we're looking at (up to available data)
        const periodEntries = forecastEntries.slice(0, Math.min(days, forecastEntries.length))

        // Calculate totals based on selected model
        let totalCases = 0
        let arimaTotal = 0
        let prophetTotal = 0

        periodEntries.forEach((entry) => {
          arimaTotal += entry.arima || 0
          prophetTotal += entry.prophet || 0
        })

        if (forecastModel === "arima") {
          totalCases = arimaTotal
        } else if (forecastModel === "prophet") {
          totalCases = prophetTotal
        } else {
          totalCases = Math.round((arimaTotal + prophetTotal) / 2)
        }

        // Calculate daily average
        const dailyAverage = periodEntries.length > 0 ? Math.round(totalCases / periodEntries.length) : 0

        // Calculate trend (compare first half to second half)
        const halfPoint = Math.floor(periodEntries.length / 2)
        const firstHalf = periodEntries.slice(0, halfPoint)
        const secondHalf = periodEntries.slice(halfPoint)

        const getModelValue = (entry: (typeof periodEntries)[0]) => {
          if (forecastModel === "arima") return entry.arima || 0
          if (forecastModel === "prophet") return entry.prophet || 0
          return ((entry.arima || 0) + (entry.prophet || 0)) / 2
        }

        const firstHalfAvg = firstHalf.reduce((sum, e) => sum + getModelValue(e), 0) / (firstHalf.length || 1)
        const secondHalfAvg = secondHalf.reduce((sum, e) => sum + getModelValue(e), 0) / (secondHalf.length || 1)

        const trendPercent = firstHalfAvg > 0 ? Math.round(((secondHalfAvg - firstHalfAvg) / firstHalfAvg) * 100) : 0

        // Determine risk level
        let riskLevel: "critical" | "high" | "medium" | "low"
        if (dailyAverage > 40) riskLevel = "critical"
        else if (dailyAverage > 25) riskLevel = "high"
        else if (dailyAverage > 10) riskLevel = "medium"
        else riskLevel = "low"

        return {
          ...barangay,
          totalCases,
          dailyAverage,
          trendPercent,
          riskLevel,
          arimaTotal,
          prophetTotal,
        }
      })
      .sort((a, b) => b.totalCases - a.totalCases)
  }, [timePeriod, forecastModel])

  const filteredBarangays = useMemo(() => {
    if (!searchQuery) return rankedBarangays
    return rankedBarangays.filter((b) => b.name.toLowerCase().includes(searchQuery.toLowerCase()))
  }, [rankedBarangays, searchQuery])

  const displayedBarangays = showAll ? filteredBarangays : filteredBarangays.slice(0, 10)

  const totalForecastedCases = rankedBarangays.reduce((sum, b) => sum + b.totalCases, 0)
  const criticalCount = rankedBarangays.filter((b) => b.riskLevel === "critical").length
  const highCount = rankedBarangays.filter((b) => b.riskLevel === "high").length

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case "critical":
        return "bg-red-500/20 text-red-400 border-red-500/30"
      case "high":
        return "bg-orange-500/20 text-orange-400 border-orange-500/30"
      case "medium":
        return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30"
      default:
        return "bg-green-500/20 text-green-400 border-green-500/30"
    }
  }

  return (
    <Card className="bg-card border-border">
      <CardHeader className="p-3 pb-2 md:p-6 md:pb-3">
        <div className="flex flex-col gap-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 md:h-5 md:w-5 text-primary" />
              <CardTitle className="text-base md:text-lg font-semibold">Forecast Rankings</CardTitle>
            </div>
            <div className="flex items-center gap-2">
              {criticalCount > 0 && (
                <Badge
                  variant="outline"
                  className="text-[10px] md:text-xs bg-red-500/10 text-red-400 border-red-500/30"
                >
                  <AlertTriangle className="h-3 w-3 mr-1" />
                  {criticalCount} Critical
                </Badge>
              )}
              {highCount > 0 && (
                <Badge
                  variant="outline"
                  className="text-[10px] md:text-xs bg-orange-500/10 text-orange-400 border-orange-500/30"
                >
                  {highCount} High Risk
                </Badge>
              )}
            </div>
          </div>

          {/* Time Period Tabs */}
          <Tabs value={timePeriod} onValueChange={(v) => setTimePeriod(v as TimePeriod)} className="w-full">
            <TabsList className="grid grid-cols-6 w-full h-8 md:h-9">
              {(Object.keys(timePeriodLabels) as TimePeriod[]).map((period) => (
                <TabsTrigger key={period} value={period} className="text-[10px] md:text-xs px-1 md:px-2">
                  {period.toUpperCase()}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          {/* Model Selection and Search */}
          <div className="flex flex-col sm:flex-row gap-2">
            <div className="flex gap-1 p-1 bg-secondary/50 rounded-lg">
              <Button
                variant={forecastModel === "average" ? "default" : "ghost"}
                size="sm"
                onClick={() => setForecastModel("average")}
                className="h-7 text-[10px] md:text-xs px-2 md:px-3"
              >
                <Activity className="h-3 w-3 mr-1" />
                Average
              </Button>
              <Button
                variant={forecastModel === "arima" ? "default" : "ghost"}
                size="sm"
                onClick={() => setForecastModel("arima")}
                className="h-7 text-[10px] md:text-xs px-2 md:px-3"
              >
                ARIMA
              </Button>
              <Button
                variant={forecastModel === "prophet" ? "default" : "ghost"}
                size="sm"
                onClick={() => setForecastModel("prophet")}
                className="h-7 text-[10px] md:text-xs px-2 md:px-3"
              >
                <Brain className="h-3 w-3 mr-1" />
                Prophet
              </Button>
            </div>
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-1/2 transform -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                placeholder="Search barangay..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-7 md:h-8 pl-8 text-xs md:text-sm bg-secondary/50"
              />
            </div>
          </div>

          {/* Summary Stats */}
          <div className="grid grid-cols-3 gap-2 p-2 md:p-3 bg-secondary/30 rounded-lg">
            <div className="text-center">
              <p className="text-lg md:text-2xl font-bold text-foreground">{totalForecastedCases.toLocaleString()}</p>
              <p className="text-[10px] md:text-xs text-muted-foreground">Total Forecast</p>
            </div>
            <div className="text-center border-x border-border">
              <p className="text-lg md:text-2xl font-bold text-foreground">{timePeriodLabels[timePeriod]}</p>
              <p className="text-[10px] md:text-xs text-muted-foreground">Time Period</p>
            </div>
            <div className="text-center">
              <p className="text-lg md:text-2xl font-bold text-foreground capitalize">{forecastModel}</p>
              <p className="text-[10px] md:text-xs text-muted-foreground">Model</p>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-3 pt-0 md:p-6 md:pt-0">
        <ScrollArea className="h-[320px] md:h-[400px]">
          <div className="space-y-2">
            {displayedBarangays.map((barangay, index) => {
              const actualRank = rankedBarangays.findIndex((b) => b.id === barangay.id) + 1
              const isSelected = selectedBarangayId === barangay.id

              return (
                <div
                  key={barangay.id}
                  onClick={() => onBarangaySelect(isSelected ? null : barangay.id)}
                  className={`flex items-center gap-2 md:gap-3 p-2 md:p-3 rounded-lg cursor-pointer transition-all ${
                    isSelected
                      ? "bg-primary/20 border border-primary"
                      : "bg-secondary/30 hover:bg-secondary/50 border border-transparent"
                  }`}
                >
                  {/* Rank */}
                  <div
                    className={`flex items-center justify-center w-6 h-6 md:w-8 md:h-8 rounded-full text-xs md:text-sm font-bold ${
                      actualRank <= 3
                        ? "bg-primary text-primary-foreground"
                        : actualRank <= 10
                          ? "bg-primary/30 text-primary"
                          : "bg-secondary text-muted-foreground"
                    }`}
                  >
                    {actualRank}
                  </div>

                  {/* Barangay Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <p className="font-medium text-sm md:text-base truncate">{barangay.name}</p>
                      {isSelected && <MapPin className="h-3 w-3 text-primary flex-shrink-0" />}
                    </div>
                    <div className="flex items-center gap-2 mt-0.5">
                      <Badge
                        variant="outline"
                        className={`text-[9px] md:text-[10px] ${getRiskColor(barangay.riskLevel)}`}
                      >
                        {barangay.riskLevel.toUpperCase()}
                      </Badge>
                      <span className="text-[10px] md:text-xs text-muted-foreground">
                        ~{barangay.dailyAverage}/day avg
                      </span>
                    </div>
                  </div>

                  {/* Stats */}
                  <div className="text-right flex-shrink-0">
                    <p className="font-bold text-sm md:text-base">{barangay.totalCases.toLocaleString()}</p>
                    <div
                      className={`flex items-center justify-end gap-0.5 text-[10px] md:text-xs ${
                        barangay.trendPercent > 0
                          ? "text-red-400"
                          : barangay.trendPercent < 0
                            ? "text-green-400"
                            : "text-muted-foreground"
                      }`}
                    >
                      {barangay.trendPercent > 0 ? (
                        <ChevronUp className="h-3 w-3" />
                      ) : barangay.trendPercent < 0 ? (
                        <ChevronDown className="h-3 w-3" />
                      ) : null}
                      {Math.abs(barangay.trendPercent)}%
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </ScrollArea>

        {filteredBarangays.length > 10 && (
          <Button variant="outline" size="sm" onClick={() => setShowAll(!showAll)} className="w-full mt-3 text-xs">
            {showAll ? `Show Top 10` : `Show All ${filteredBarangays.length} Barangays`}
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
