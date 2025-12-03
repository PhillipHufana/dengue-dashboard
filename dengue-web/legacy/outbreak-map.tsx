// "use client"

// import { useState, useMemo } from "react"
// import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
// import { Badge } from "@/components/ui/badge"
// import { Input } from "@/components/ui/input"
// import { Search, ChevronLeft, ChevronRight } from "lucide-react"
// import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
// import { Button } from "@/components/ui/button"

// const generateBarangays = () => {
//   const barangayNames = [
//     "Poblacion",
//     "San Jose",
//     "San Antonio",
//     "San Isidro",
//     "Santo Niño",
//     "Sta. Cruz",
//     "Sta. Maria",
//     "San Miguel",
//     "San Rafael",
//     "San Vicente",
//     "Bagumbayan",
//     "Maligaya",
//     "Mabuhay",
//     "Kamuning",
//     "Barangka",
//     "Plainview",
//     "Addition Hills",
//     "Highway Hills",
//     "Burol",
//     "Paliparan",
//     "Langkaan",
//     "Salawag",
//     "Sampaloc",
//     "Sabang",
//     "Salitran",
//     "Datu",
//     "Fatima",
//     "San Agustin",
//     "San Dionisio",
//     "San Francisco",
//     "San Juan",
//     "San Nicolas",
//     "San Pedro",
//     "San Roque",
//     "Santa Ana",
//     "Santa Barbara",
//     "Santa Elena",
//     "Santa Lucia",
//     "Santa Monica",
//     "Santa Rosa",
//     "Santiago",
//     "Santo Cristo",
//     "Santo Domingo",
//     "Assumption",
//     "Bel-Air",
//     "Cembo",
//     "Comembo",
//     "Dasmariñas",
//     "East Rembo",
//     "Forbes Park",
//     "Guadalupe Nuevo",
//     "Guadalupe Viejo",
//     "Kasilawan",
//     "La Paz",
//     "Magallanes",
//     "Olympia",
//     "Palanan",
//     "Pio del Pilar",
//     "Pitogo",
//     "Post Proper North",
//     "Post Proper South",
//     "Rizal",
//     "San Isidro Labrador",
//     "Santa Clara",
//     "Singkamas",
//     "South Cembo",
//     "Tejeros",
//     "Valenzuela",
//     "West Rembo",
//     "Bangkal",
//     "Buting",
//     "Carmona",
//     "Dela Paz",
//     "East Kamias",
//     "Escopa",
//     "Kapasigan",
//     "Kapitolyo",
//     "Manggahan",
//     "Maybunga",
//     "Oranbo",
//     "Pasig",
//     "Pinagbuhatan",
//     "Pineda",
//     "Rosario",
//     "Sagad",
//     "San Joaquin",
//     "Santa Lucia Old",
//     "Santolan",
//     "Sumilang",
//     "Ugong",
//     "Bambang",
//     "Bignay",
//     "Caniogan",
//     "Concepcion",
//     "Dulong Bayan",
//     "Gulod",
//     "Malanday",
//     "Malis",
//     "Panghulo",
//     "Potrero",
//     "Sta. Clara Del Monte",
//     "Sto. Cristo",
//     "Sto. Rosario",
//     "Tugatog",
//     "Ubihan",
//     "Baesa",
//     "Bagong Barrio",
//     "Balintawak",
//     "Capri",
//     "Coloong",
//     "Deparo",
//     "Gen. T. de Leon",
//     "Isla",
//     "Karuhatan",
//     "Lawang Bato",
//     "Lingunan",
//     "Mabolo",
//     "Malanday Norte",
//     "Malinta",
//     "Mapulang Lupa",
//     "Marulas",
//     "Maysan",
//     "Parada",
//     "Pariancillo Villa",
//     "Paso de Blas",
//     "Pasolo",
//     "Poblacion Norte",
//     "Poblacion Sur",
//     "Polo",
//     "Punturin",
//     "Rincon",
//     "Tagalag",
//     "Ugong Norte",
//     "Viente Reales",
//     "Wawang Pulo",
//     "Arkong Bato",
//     "Balangkas",
//     "Bignay Sur",
//     "Bisig",
//     "Canumay",
//     "Coloong Sur",
//     "Dalandanan",
//     "Hen. de Leon",
//     "Isla Norte",
//     "Isla Sur",
//     "Karuhatan Sur",
//     "Lawang Bato Sur",
//     "Lingunan Sur",
//     "Mabolo Sur",
//     "Malanday Sur",
//     "Malinta Sur",
//     "Mapulang Lupa Sur",
//     "Marulas Sur",
//     "Maysan Sur",
//     "Parada Sur",
//     "Pasolo Sur",
//     "Polo Sur",
//     "Punturin Sur",
//     "Rincon Sur",
//     "Tagalag Sur",
//     "Ugong Sur",
//     "Veinte Reales Sur",
//     "Bagong Silang",
//     "Batasan Hills",
//     "Commonwealth",
//     "Holy Spirit",
//     "Payatas",
//     "Bagong Pag-asa",
//     "Bahay Toro",
//     "Balingasa",
//     "Bungad",
//     "Damar",
//     "Damayan",
//     "Del Monte",
//     "Katipunan",
//     "Lourdes",
//     "Maharlika",
//     "Manresa",
//     "Masambong",
//     "N.S. Amoranto",
//     "Nayong Kanluran",
//     "Paang Bundok",
//     "Pag-ibig sa Nayon",
//     "Paltok",
//     "Paraiso",
//     "Phil-Am",
//     "Project 6",
//     "Ramon Magsaysay",
//     "Saint Peter",
//     "Salvacion",
//     "San Martin de Porres",
//     "Sto. Tomas",
//     "Santa Cruz",
//     "Santa Teresita",
//   ]

//   return barangayNames.slice(0, 182).map((name, i) => {
//     const cases = Math.floor(Math.random() * 500) + 10
//     let severity: "critical" | "high" | "medium" | "low"
//     if (cases > 350) severity = "critical"
//     else if (cases > 200) severity = "high"
//     else if (cases > 100) severity = "medium"
//     else severity = "low"

//     return {
//       id: i + 1,
//       name: `${name}${i > 40 ? ` ${Math.floor(i / 40)}` : ""}`,
//       cases,
//       severity,
//       trend: Math.random() > 0.5 ? "up" : "down",
//       change: Math.floor(Math.random() * 30) - 10,
//     }
//   })
// }

// const barangays = generateBarangays()

// const severityColors = {
//   critical: "bg-red-500/20 text-red-400 border-red-500/30",
//   high: "bg-orange-500/20 text-orange-400 border-orange-500/30",
//   medium: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
//   low: "bg-green-500/20 text-green-400 border-green-500/30",
// }

// const ITEMS_PER_PAGE = 10

// export function OutbreakMap() {
//   const [search, setSearch] = useState("")
//   const [severityFilter, setSeverityFilter] = useState<string>("all")
//   const [page, setPage] = useState(1)
//   const [sortBy, setSortBy] = useState<"cases" | "name">("cases")

//   const filteredBarangays = useMemo(() => {
//     const result = barangays.filter(
//       (b) =>
//         b.name.toLowerCase().includes(search.toLowerCase()) &&
//         (severityFilter === "all" || b.severity === severityFilter),
//     )

//     result.sort((a, b) => {
//       if (sortBy === "cases") return b.cases - a.cases
//       return a.name.localeCompare(b.name)
//     })

//     return result
//   }, [search, severityFilter, sortBy])

//   const totalPages = Math.ceil(filteredBarangays.length / ITEMS_PER_PAGE)
//   const paginatedBarangays = filteredBarangays.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE)

//   const stats = useMemo(
//     () => ({
//       critical: barangays.filter((b) => b.severity === "critical").length,
//       high: barangays.filter((b) => b.severity === "high").length,
//       medium: barangays.filter((b) => b.severity === "medium").length,
//       low: barangays.filter((b) => b.severity === "low").length,
//     }),
//     [],
//   )

//   return (
//     <Card className="bg-card border-border">
//       <CardHeader className="p-3 pb-2 md:p-6 md:pb-3">
//         <div className="flex flex-col gap-2 md:gap-3">
//           <div className="flex items-center justify-between">
//             <CardTitle className="text-base md:text-lg font-semibold">Barangay Status</CardTitle>
//             <Badge variant="outline" className="text-[10px] md:text-xs">
//               {barangays.length} Total
//             </Badge>
//           </div>

//           <div className="flex gap-1.5 md:gap-2 overflow-x-auto pb-1 -mx-1 px-1 scrollbar-hide">
//             <div className="flex-shrink-0 flex items-center gap-1 md:gap-1.5 rounded-full bg-red-500/10 px-2 md:px-3 py-0.5 md:py-1 text-[10px] md:text-xs">
//               <div className="h-1.5 w-1.5 md:h-2 md:w-2 rounded-full bg-red-500" />
//               <span className="text-red-400">{stats.critical} Crit</span>
//             </div>
//             <div className="flex-shrink-0 flex items-center gap-1 md:gap-1.5 rounded-full bg-orange-500/10 px-2 md:px-3 py-0.5 md:py-1 text-[10px] md:text-xs">
//               <div className="h-1.5 w-1.5 md:h-2 md:w-2 rounded-full bg-orange-500" />
//               <span className="text-orange-400">{stats.high} High</span>
//             </div>
//             <div className="flex-shrink-0 flex items-center gap-1 md:gap-1.5 rounded-full bg-yellow-500/10 px-2 md:px-3 py-0.5 md:py-1 text-[10px] md:text-xs">
//               <div className="h-1.5 w-1.5 md:h-2 md:w-2 rounded-full bg-yellow-500" />
//               <span className="text-yellow-400">{stats.medium} Med</span>
//             </div>
//             <div className="flex-shrink-0 flex items-center gap-1 md:gap-1.5 rounded-full bg-green-500/10 px-2 md:px-3 py-0.5 md:py-1 text-[10px] md:text-xs">
//               <div className="h-1.5 w-1.5 md:h-2 md:w-2 rounded-full bg-green-500" />
//               <span className="text-green-400">{stats.low} Low</span>
//             </div>
//           </div>

//           <div className="flex flex-col sm:flex-row gap-2">
//             <div className="relative flex-1">
//               <Search className="absolute left-2.5 md:left-3 top-1/2 h-3.5 w-3.5 md:h-4 md:w-4 -translate-y-1/2 text-muted-foreground" />
//               <Input
//                 placeholder="Search barangay..."
//                 className="bg-secondary pl-8 md:pl-9 text-xs md:text-sm h-8 md:h-9"
//                 value={search}
//                 onChange={(e) => {
//                   setSearch(e.target.value)
//                   setPage(1)
//                 }}
//               />
//             </div>
//             <div className="flex gap-2">
//               <Select
//                 value={severityFilter}
//                 onValueChange={(v) => {
//                   setSeverityFilter(v)
//                   setPage(1)
//                 }}
//               >
//                 <SelectTrigger className="w-[100px] md:w-[120px] bg-secondary h-8 md:h-9 text-xs md:text-sm">
//                   <SelectValue placeholder="Severity" />
//                 </SelectTrigger>
//                 <SelectContent>
//                   <SelectItem value="all">All</SelectItem>
//                   <SelectItem value="critical">Critical</SelectItem>
//                   <SelectItem value="high">High</SelectItem>
//                   <SelectItem value="medium">Medium</SelectItem>
//                   <SelectItem value="low">Low</SelectItem>
//                 </SelectContent>
//               </Select>
//               <Select value={sortBy} onValueChange={(v: "cases" | "name") => setSortBy(v)}>
//                 <SelectTrigger className="w-[100px] md:w-[120px] bg-secondary h-8 md:h-9 text-xs md:text-sm">
//                   <SelectValue placeholder="Sort" />
//                 </SelectTrigger>
//                 <SelectContent>
//                   <SelectItem value="cases">Cases</SelectItem>
//                   <SelectItem value="name">Name</SelectItem>
//                 </SelectContent>
//               </Select>
//             </div>
//           </div>
//         </div>
//       </CardHeader>
//       <CardContent className="p-3 pt-0 md:p-6 md:pt-0">
//         <div className="space-y-1.5 md:space-y-2">
//           {paginatedBarangays.map((barangay) => (
//             <div
//               key={barangay.id}
//               className="flex items-center justify-between rounded-lg bg-secondary/50 px-2.5 md:px-3 py-2 md:py-2.5 hover:bg-secondary/80 transition-colors"
//             >
//               <div className="flex items-center gap-2 md:gap-3 min-w-0">
//                 <div
//                   className={`h-1.5 w-1.5 md:h-2 md:w-2 rounded-full flex-shrink-0 ${
//                     barangay.severity === "critical"
//                       ? "bg-red-500"
//                       : barangay.severity === "high"
//                         ? "bg-orange-500"
//                         : barangay.severity === "medium"
//                           ? "bg-yellow-500"
//                           : "bg-green-500"
//                   }`}
//                 />
//                 <span className="text-xs md:text-sm font-medium truncate">{barangay.name}</span>
//               </div>
//               <div className="flex items-center gap-2 md:gap-3">
//                 <span className={`text-[10px] md:text-xs ${barangay.change >= 0 ? "text-red-400" : "text-green-400"}`}>
//                   {barangay.change >= 0 ? "+" : ""}
//                   {barangay.change}%
//                 </span>
//                 <Badge
//                   variant="outline"
//                   className={`text-[10px] md:text-xs font-semibold min-w-[45px] md:min-w-[60px] justify-center ${severityColors[barangay.severity]}`}
//                 >
//                   {barangay.cases}
//                 </Badge>
//               </div>
//             </div>
//           ))}
//         </div>

//         <div className="mt-3 md:mt-4 flex items-center justify-between">
//           <span className="text-[10px] md:text-xs text-muted-foreground">
//             {(page - 1) * ITEMS_PER_PAGE + 1}-{Math.min(page * ITEMS_PER_PAGE, filteredBarangays.length)} of{" "}
//             {filteredBarangays.length}
//           </span>
//           <div className="flex items-center gap-1">
//             <Button
//               variant="outline"
//               size="icon"
//               className="h-7 w-7 md:h-8 md:w-8 bg-transparent"
//               disabled={page === 1}
//               onClick={() => setPage((p) => p - 1)}
//             >
//               <ChevronLeft className="h-3.5 w-3.5 md:h-4 md:w-4" />
//             </Button>
//             <span className="px-2 md:px-3 text-xs md:text-sm">
//               {page}/{totalPages}
//             </span>
//             <Button
//               variant="outline"
//               size="icon"
//               className="h-7 w-7 md:h-8 md:w-8 bg-transparent"
//               disabled={page === totalPages}
//               onClick={() => setPage((p) => p + 1)}
//             >
//               <ChevronRight className="h-3.5 w-3.5 md:h-4 md:w-4" />
//             </Button>
//           </div>
//         </div>
//       </CardContent>
//     </Card>
//   )
// }
