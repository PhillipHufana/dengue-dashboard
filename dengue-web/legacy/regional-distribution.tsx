"use client"

import { useState, useMemo } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Search, ChevronDown, ChevronUp } from "lucide-react"
import { Badge } from "@/components/ui/badge"

const topBarangays = [
  { name: "Poblacion", cases: 487, change: 12 },
  { name: "Bagong Silang", cases: 423, change: -5 },
  { name: "Commonwealth", cases: 398, change: 8 },
  { name: "Payatas", cases: 367, change: 15 },
  { name: "Batasan Hills", cases: 345, change: -2 },
  { name: "Holy Spirit", cases: 312, change: 6 },
  { name: "Fairview", cases: 298, change: -8 },
  { name: "North Fairview", cases: 276, change: 4 },
  { name: "Greater Lagro", cases: 254, change: 11 },
  { name: "Novaliches Proper", cases: 243, change: -3 },
  { name: "Gulod", cases: 231, change: 7 },
  { name: "Kaligayahan", cases: 218, change: 2 },
  { name: "Nagkaisang Nayon", cases: 205, change: -6 },
  { name: "San Bartolome", cases: 198, change: 9 },
  { name: "Santa Monica", cases: 187, change: -1 },
  { name: "Tandang Sora", cases: 176, change: 4 },
  { name: "Pasong Tamo", cases: 165, change: -4 },
  { name: "Culiat", cases: 154, change: 3 },
  { name: "Sauyo", cases: 143, change: 1 },
  { name: "Talipapa", cases: 132, change: -2 },
]

export function RegionalDistribution() {
  const [search, setSearch] = useState("")
  const [expanded, setExpanded] = useState(false)

  const maxCases = topBarangays[0].cases

  const filteredBarangays = useMemo(() => {
    const filtered = topBarangays.filter((b) => b.name.toLowerCase().includes(search.toLowerCase()))
    return expanded ? filtered : filtered.slice(0, 8)
  }, [search, expanded])

  return (
    <Card className="bg-card border-border">
      <CardHeader className="p-3 pb-2 md:p-6 md:pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base md:text-lg font-semibold">Top Affected</CardTitle>
          <Badge variant="outline" className="text-[10px] md:text-xs">
            Top 20
          </Badge>
        </div>
        <div className="relative mt-1.5 md:mt-2">
          <Search className="absolute left-2.5 md:left-3 top-1/2 h-3.5 w-3.5 md:h-4 md:w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search..."
            className="bg-secondary pl-8 md:pl-9 text-xs md:text-sm h-7 md:h-8"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </CardHeader>
      <CardContent className="p-3 pt-0 md:p-6 md:pt-0">
        <div className="space-y-1.5 md:space-y-2">
          {filteredBarangays.map((barangay, index) => (
            <div key={barangay.name} className="group">
              <div className="flex items-center justify-between text-xs md:text-sm mb-0.5 md:mb-1">
                <span className="text-muted-foreground truncate max-w-[120px] md:max-w-[140px]">
                  {index + 1}. {barangay.name}
                </span>
                <div className="flex items-center gap-1.5 md:gap-2">
                  <span
                    className={`text-[10px] md:text-xs ${barangay.change >= 0 ? "text-red-400" : "text-green-400"}`}
                  >
                    {barangay.change >= 0 ? "+" : ""}
                    {barangay.change}%
                  </span>
                  <span className="font-medium text-foreground">{barangay.cases}</span>
                </div>
              </div>
              <div className="h-1.5 md:h-2 w-full rounded-full bg-secondary overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-[#d4a847] to-[#b8912e] transition-all group-hover:opacity-80"
                  style={{ width: `${(barangay.cases / maxCases) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>

        {!search && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="mt-2.5 md:mt-3 flex w-full items-center justify-center gap-1 rounded-lg bg-secondary/50 py-1.5 md:py-2 text-[10px] md:text-xs text-muted-foreground hover:bg-secondary transition-colors"
          >
            {expanded ? (
              <>
                Show Less <ChevronUp className="h-3 w-3" />
              </>
            ) : (
              <>
                Show More <ChevronDown className="h-3 w-3" />
              </>
            )}
          </button>
        )}
      </CardContent>
    </Card>
  )
}
