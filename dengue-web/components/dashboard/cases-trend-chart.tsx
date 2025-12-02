"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Area, AreaChart, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts"

const data = [
  { date: "Nov 1", cases: 1200, recovered: 980 },
  { date: "Nov 5", cases: 1450, recovered: 1100 },
  { date: "Nov 10", cases: 1800, recovered: 1350 },
  { date: "Nov 15", cases: 2200, recovered: 1650 },
  { date: "Nov 20", cases: 1950, recovered: 1800 },
  { date: "Nov 25", cases: 2400, recovered: 2100 },
  { date: "Nov 30", cases: 2150, recovered: 1950 },
]

function CustomTooltip({ active, payload, label }: any) {
  if (active && payload && payload.length) {
    return (
      <div className="rounded-lg border border-border bg-background p-3 shadow-md">
        <p className="mb-2 text-sm font-medium">{label}</p>
        {payload.map((entry: any, index: number) => (
          <p key={index} className="text-sm" style={{ color: entry.color }}>
            {entry.dataKey === "cases" ? "New Cases" : "Recovered"}: {entry.value.toLocaleString()}
          </p>
        ))}
      </div>
    )
  }
  return null
}

export function CasesTrendChart() {
  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold">Cases Trend</CardTitle>
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-[#d4a847]" />
              <span className="text-muted-foreground">New Cases</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-[#4a9d8e]" />
              <span className="text-muted-foreground">Recovered</span>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-[320px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="casesGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#d4a847" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#d4a847" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="recoveredGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#4a9d8e" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#4a9d8e" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fill: "#888", fontSize: 12 }}
                axisLine={{ stroke: "#333" }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#888", fontSize: 12 }}
                axisLine={{ stroke: "#333" }}
                tickLine={false}
                tickFormatter={(value) => `${value / 1000}K`}
              />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="cases" stroke="#d4a847" strokeWidth={2} fill="url(#casesGradient)" />
              <Area
                type="monotone"
                dataKey="recovered"
                stroke="#4a9d8e"
                strokeWidth={2}
                fill="url(#recoveredGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
