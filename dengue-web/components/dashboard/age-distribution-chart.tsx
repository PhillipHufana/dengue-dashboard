"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Bar, BarChart, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts"

const data = [
  { age: "0-4", cases: 3200 },
  { age: "5-14", cases: 5800 },
  { age: "15-24", cases: 4500 },
  { age: "25-34", cases: 3800 },
  { age: "35-44", cases: 2900 },
  { age: "45-54", cases: 2100 },
  { age: "55+", cases: 1600 },
]

function CustomTooltip({ active, payload, label }: any) {
  if (active && payload && payload.length) {
    return (
      <div className="rounded-lg border border-border bg-background p-2 md:p-3 shadow-md text-xs md:text-sm">
        <p className="mb-0.5 md:mb-1 font-medium">Age: {label}</p>
        <p className="text-[#4a9d8e]">Cases: {payload[0].value.toLocaleString()}</p>
      </div>
    )
  }
  return null
}

export function AgeDistributionChart() {
  return (
    <Card className="bg-card border-border">
      <CardHeader className="p-3 pb-2 md:p-6 md:pb-2">
        <CardTitle className="text-base md:text-lg font-semibold">Age Distribution</CardTitle>
      </CardHeader>
      <CardContent className="p-3 pt-0 md:p-6 md:pt-0">
        <div className="h-[200px] md:h-60 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 0, right: 5, left: -20, bottom: 0 }}>
              <XAxis
                dataKey="age"
                tick={{ fill: "#888", fontSize: 9 }}
                axisLine={{ stroke: "#333" }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#888", fontSize: 9 }}
                axisLine={{ stroke: "#333" }}
                tickLine={false}
                tickFormatter={(value) => `${value / 1000}K`}
                width={35}
              />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="cases" fill="#4a9d8e" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
