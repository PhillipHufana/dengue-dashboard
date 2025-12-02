"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts"

const data = [
  { name: "Mild", value: 18500, color: "#4a9d8e" },
  { name: "Moderate", value: 6800, color: "#d4a847" },
  { name: "Severe", value: 2400, color: "#e67e22" },
  { name: "Critical", value: 759, color: "#c0392b" },
]

function CustomTooltip({ active, payload }: any) {
  if (active && payload && payload.length) {
    const entry = payload[0]
    return (
      <div className="rounded-lg border border-border bg-background p-2 md:p-3 shadow-md text-xs md:text-sm">
        <p className="mb-0.5 md:mb-1 font-medium" style={{ color: entry.payload.color }}>
          {entry.name}
        </p>
        <p className="text-foreground">Cases: {entry.value.toLocaleString()}</p>
      </div>
    )
  }
  return null
}

export function SeverityBreakdown() {
  return (
    <Card className="bg-card border-border">
      <CardHeader className="p-3 pb-2 md:p-6 md:pb-2">
        <CardTitle className="text-base md:text-lg font-semibold">Severity Breakdown</CardTitle>
      </CardHeader>
      <CardContent className="p-3 pt-0 md:p-6 md:pt-0">
        <div className="h-[180px] md:h-[240px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={data} cx="50%" cy="50%" innerRadius={35} outerRadius={60} paddingAngle={2} dataKey="value">
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend
                verticalAlign="bottom"
                height={30}
                formatter={(value) => <span className="text-[10px] md:text-xs text-muted-foreground">{value}</span>}
                iconSize={8}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
