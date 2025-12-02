"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { AlertTriangle, TrendingUp, MapPin, Clock } from "lucide-react"

const alerts = [
  {
    id: 1,
    type: "outbreak",
    title: "New Outbreak Detected",
    location: "Quezon City, NCR",
    time: "2 hours ago",
    severity: "critical",
    description: "Cluster of 47 new cases reported in Barangay Commonwealth",
  },
  {
    id: 2,
    type: "surge",
    title: "Case Surge Alert",
    location: "Cebu City, Region VII",
    time: "5 hours ago",
    severity: "high",
    description: "25% increase in cases over the past 48 hours",
  },
  {
    id: 3,
    type: "outbreak",
    title: "Hospital Capacity Warning",
    location: "Davao City, Region XI",
    time: "8 hours ago",
    severity: "medium",
    description: "ICU bed occupancy reaching 85% threshold",
  },
  {
    id: 4,
    type: "update",
    title: "Vector Control Update",
    location: "Iloilo City, Region VI",
    time: "12 hours ago",
    severity: "low",
    description: "Fogging operations completed in 12 barangays",
  },
]

const severityConfig = {
  critical: { color: "bg-red-500/10 text-red-400 border-red-500/20", dot: "bg-red-500" },
  high: { color: "bg-orange-500/10 text-orange-400 border-orange-500/20", dot: "bg-orange-500" },
  medium: { color: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20", dot: "bg-yellow-500" },
  low: { color: "bg-green-500/10 text-green-400 border-green-500/20", dot: "bg-green-500" },
}

export function RecentAlerts() {
  return (
    <Card className="bg-card border-border">
      <CardHeader className="p-3 pb-2 md:p-6 md:pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base md:text-lg font-semibold">Recent Alerts</CardTitle>
          <Badge variant="secondary" className="text-[10px] md:text-xs">
            {alerts.length} Active
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="p-3 pt-0 md:p-6 md:pt-0">
        <div className="space-y-3 md:space-y-4">
          {alerts.map((alert) => {
            const config = severityConfig[alert.severity as keyof typeof severityConfig]
            return (
              <div
                key={alert.id}
                className="flex gap-2.5 md:gap-4 rounded-lg border border-border bg-secondary/30 p-2.5 md:p-4 transition-colors hover:bg-secondary/50"
              >
                <div
                  className={`flex h-8 w-8 md:h-10 md:w-10 shrink-0 items-center justify-center rounded-lg ${config.color}`}
                >
                  {alert.type === "outbreak" ? (
                    <AlertTriangle className="h-4 w-4 md:h-5 md:w-5" />
                  ) : (
                    <TrendingUp className="h-4 w-4 md:h-5 md:w-5" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-1 sm:gap-2">
                    <h4 className="font-medium text-xs md:text-sm text-foreground">{alert.title}</h4>
                    <Badge variant="outline" className={`shrink-0 self-start text-[10px] md:text-xs ${config.color}`}>
                      {alert.severity}
                    </Badge>
                  </div>
                  <p className="mt-0.5 md:mt-1 text-[10px] md:text-sm text-muted-foreground line-clamp-2">
                    {alert.description}
                  </p>
                  <div className="mt-1.5 md:mt-2 flex flex-wrap items-center gap-2 md:gap-4 text-[10px] md:text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <MapPin className="h-2.5 w-2.5 md:h-3 md:w-3" />
                      {alert.location}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="h-2.5 w-2.5 md:h-3 md:w-3" />
                      {alert.time}
                    </span>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
