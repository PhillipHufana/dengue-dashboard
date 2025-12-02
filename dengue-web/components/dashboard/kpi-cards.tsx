"use client"

import { Card, CardContent } from "@/components/ui/card"
import { TrendingUp, TrendingDown, Users, Activity, Heart, AlertTriangle } from "lucide-react"

const kpis = [
  {
    title: "Total Cases",
    value: "28,459",
    change: "+12.5%",
    trend: "up",
    icon: Users,
    description: "This month",
  },
  {
    title: "Active Cases",
    value: "3,847",
    change: "+8.2%",
    trend: "up",
    icon: Activity,
    description: "Currently monitored",
  },
  {
    title: "Recovery Rate",
    value: "94.2%",
    change: "+2.1%",
    trend: "up",
    icon: Heart,
    description: "Past 30 days",
  },
  {
    title: "Mortality Rate",
    value: "0.8%",
    change: "-0.3%",
    trend: "down",
    icon: AlertTriangle,
    description: "Past 30 days",
  },
]

export function KpiCards() {
  return (
    <div className="grid grid-cols-2 gap-3 md:gap-4 lg:grid-cols-4">
      {kpis.map((kpi) => (
        <Card key={kpi.title} className="bg-card border-border">
          <CardContent className="p-3 md:p-6">
            <div className="flex items-center justify-between">
              <div className="flex h-8 w-8 md:h-10 md:w-10 items-center justify-center rounded-lg bg-secondary">
                <kpi.icon className="h-4 w-4 md:h-5 md:w-5 text-primary" />
              </div>
              <div
                className={`flex items-center gap-0.5 md:gap-1 text-xs md:text-sm font-medium ${
                  kpi.trend === "up"
                    ? kpi.title === "Mortality Rate"
                      ? "text-green-400"
                      : "text-primary"
                    : kpi.title === "Mortality Rate"
                      ? "text-green-400"
                      : "text-destructive"
                }`}
              >
                {kpi.trend === "up" ? (
                  <TrendingUp className="h-3 w-3 md:h-4 md:w-4" />
                ) : (
                  <TrendingDown className="h-3 w-3 md:h-4 md:w-4" />
                )}
                <span className="text-xs md:text-sm">{kpi.change}</span>
              </div>
            </div>
            <div className="mt-2 md:mt-4">
              <p className="text-lg md:text-2xl font-bold text-foreground">{kpi.value}</p>
              <p className="text-xs md:text-sm text-muted-foreground">{kpi.title}</p>
              <p className="mt-0.5 md:mt-1 text-[10px] md:text-xs text-muted-foreground">{kpi.description}</p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
