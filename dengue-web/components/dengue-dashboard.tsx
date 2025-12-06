"use client"

import { useState } from "react"
import { KpiCards } from "./dashboard/kpi-cards"
// import { ChoroplethMap } from "./dashboard/choropleth-map"
import { ForecastChart } from "./dashboard/forecast-chart"
import { ForecastRankings } from "./dashboard/forecast-rankings"
import { LoginModal } from "./dashboard/login-modal"
import { ThemeToggle } from "./dashboard/theme-toggle"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet"
import { Bug, Calendar, Menu } from "lucide-react"
import dynamic from "next/dynamic";

const ChoroplethMap = dynamic(
  () =>
    import("./dashboard/choropleth-map").then((mod) => mod.ChoroplethMap),
  {
    ssr: false,
    loading: () => (
      <div className="h-[300px] flex items-center justify-center">
        Loading map…
      </div>
    ),
  }
);

export function DengueDashboard() {
  const [timeRange, setTimeRange] = useState("7d")
  const [selectedBarangay, setSelectedBarangay] = useState<{
    pretty: string;
    clean: string;
  } | null>(null);


  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60
 px-4 py-3 md:px-6 md:py-4">
        <div className="flex items-center justify-between gap-3">
          {/* Logo and Title */}
          <div className="flex items-center gap-2 md:gap-3">
            <div className="flex h-8 w-8 md:h-10 md:w-10 items-center justify-center rounded-lg bg-primary">
              <Bug className="h-4 w-4 md:h-5 md:w-5 text-primary-foreground" />
            </div>
            <div>
              <h1 className="text-base md:text-xl font-semibold text-foreground">Dengue Surveillance</h1>
              <p className="hidden sm:block text-xs md:text-sm text-muted-foreground">
                Predictive outbreak monitoring - 182 Barangays
              </p>
            </div>
          </div>

          {/* Desktop Controls */}
          <div className="hidden md:flex items-center gap-3">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Calendar className="h-4 w-4" />
              <span>Last updated: Nov 30, 2025</span>
            </div>
            <Select value={timeRange} onValueChange={setTimeRange}>
              <SelectTrigger className="w-[140px] bg-secondary">
                <SelectValue placeholder="Time range" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="24h">Last 24 hours</SelectItem>
                <SelectItem value="7d">Last 7 days</SelectItem>
                <SelectItem value="30d">Last 30 days</SelectItem>
                <SelectItem value="90d">Last 90 days</SelectItem>
              </SelectContent>
            </Select>
            <ThemeToggle />
            <LoginModal />
          </div>

          {/* Mobile Menu */}
          <div className="flex md:hidden items-center gap-2">
            <Select value={timeRange} onValueChange={setTimeRange}>
              <SelectTrigger className="w-[100px] h-8 bg-secondary text-xs">
                <SelectValue placeholder="Range" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="24h">24 hours</SelectItem>
                <SelectItem value="7d">7 days</SelectItem>
                <SelectItem value="30d">30 days</SelectItem>
                <SelectItem value="90d">90 days</SelectItem>
              </SelectContent>
            </Select>
            <ThemeToggle />
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="outline" size="icon" className="h-8 w-8 bg-transparent">
                  <Menu className="h-4 w-4" />
                </Button>
              </SheetTrigger>
              <SheetContent side="right" className="w-[280px]">
                <div className="flex flex-col gap-4 mt-6">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Calendar className="h-4 w-4" />
                    <span>Last updated: Nov 30, 2025</span>
                  </div>
                  <LoginModal variant="mobile" />
                </div>
              </SheetContent>
            </Sheet>
          </div>
        </div>
      </header>

      <main className="p-3 md:p-6">
        <div className="space-y-4 md:space-y-6">
          <KpiCards />

          <div className="grid gap-4 md:gap-6 lg:grid-cols-2">
            <ForecastChart selectedBarangay={selectedBarangay} />
            <ForecastRankings
              selectedBarangay={selectedBarangay}
              onBarangaySelect={setSelectedBarangay}
            />
          </div>

          <ChoroplethMap
            selectedBarangay={selectedBarangay}
            onBarangaySelect={setSelectedBarangay}
          />


        </div>
      </main>
    </div>
  )
}
