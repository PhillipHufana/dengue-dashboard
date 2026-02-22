"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  FileSpreadsheet,
  Search,
  Filter,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  Clock,
  AlertCircle,
  XCircle,
  Download,
  Eye,
} from "lucide-react"

interface UploadLog {
  id: number
  dateUploaded: string
  uploaderName: string
  association: string
  fileName: string
  status: "approved" | "pending" | "processing" | "rejected"
  recordCount: number
}

const uploadLogs: UploadLog[] = [
  {
    id: 1,
    dateUploaded: "2025-11-30 14:32",
    uploaderName: "Dr. Maria Santos",
    association: "Davao City Health Office",
    fileName: "dengue_cases_nov30.xlsx",
    status: "approved",
    recordCount: 47,
  },
  {
    id: 2,
    dateUploaded: "2025-11-30 11:15",
    uploaderName: "Juan Dela Cruz",
    association: "Brgy. Buhangin Health Center",
    fileName: "buhangin_weekly_report.csv",
    status: "approved",
    recordCount: 12,
  },
  {
    id: 3,
    dateUploaded: "2025-11-30 09:45",
    uploaderName: "Dr. Ana Reyes",
    association: "Southern Philippines Medical Center",
    fileName: "spmc_dengue_cases.xlsx",
    status: "processing",
    recordCount: 89,
  },
  {
    id: 4,
    dateUploaded: "2025-11-29 16:20",
    uploaderName: "Pedro Gonzales",
    association: "Brgy. Talomo Health Center",
    fileName: "talomo_nov_cases.csv",
    status: "approved",
    recordCount: 23,
  },
  {
    id: 5,
    dateUploaded: "2025-11-29 14:05",
    uploaderName: "Maria Clara",
    association: "Brgy. Agdao Health Center",
    fileName: "agdao_report_nov29.xlsx",
    status: "pending",
    recordCount: 31,
  },
  {
    id: 6,
    dateUploaded: "2025-11-29 10:30",
    uploaderName: "Dr. Jose Rizal",
    association: "Davao Regional Medical Center",
    fileName: "drmc_dengue_weekly.csv",
    status: "approved",
    recordCount: 156,
  },
  {
    id: 7,
    dateUploaded: "2025-11-28 15:45",
    uploaderName: "Andres Bonifacio",
    association: "Brgy. Matina Health Center",
    fileName: "matina_cases_nov.xlsx",
    status: "rejected",
    recordCount: 0,
  },
  {
    id: 8,
    dateUploaded: "2025-11-28 13:20",
    uploaderName: "Dr. Gabriela Silang",
    association: "San Pedro Hospital",
    fileName: "sph_dengue_report.csv",
    status: "approved",
    recordCount: 67,
  },
  {
    id: 9,
    dateUploaded: "2025-11-28 09:10",
    uploaderName: "Emilio Aguinaldo",
    association: "Brgy. Toril Health Center",
    fileName: "toril_weekly_nov28.xlsx",
    status: "approved",
    recordCount: 19,
  },
  {
    id: 10,
    dateUploaded: "2025-11-27 16:55",
    uploaderName: "Dr. Melchora Aquino",
    association: "Davao Doctors Hospital",
    fileName: "ddh_dengue_cases.csv",
    status: "approved",
    recordCount: 45,
  },
  {
    id: 11,
    dateUploaded: "2025-11-27 11:30",
    uploaderName: "Lapu Lapu",
    association: "Brgy. Panacan Health Center",
    fileName: "panacan_nov_report.xlsx",
    status: "pending",
    recordCount: 28,
  },
  {
    id: 12,
    dateUploaded: "2025-11-27 08:45",
    uploaderName: "Dr. Trinidad Tecson",
    association: "Metro Davao Medical Center",
    fileName: "mdmc_weekly_dengue.csv",
    status: "approved",
    recordCount: 73,
  },
  {
    id: 13,
    dateUploaded: "2025-11-26 14:15",
    uploaderName: "Diego Silang",
    association: "Brgy. Calinan Health Center",
    fileName: "calinan_cases_nov26.xlsx",
    status: "processing",
    recordCount: 15,
  },
  {
    id: 14,
    dateUploaded: "2025-11-26 10:00",
    uploaderName: "Dr. Josefa Llanes",
    association: "Davao City Health Office",
    fileName: "weekly_consolidated.csv",
    status: "approved",
    recordCount: 234,
  },
  {
    id: 15,
    dateUploaded: "2025-11-25 15:30",
    uploaderName: "Gregoria de Jesus",
    association: "Brgy. Bunawan Health Center",
    fileName: "bunawan_dengue_nov.xlsx",
    status: "approved",
    recordCount: 11,
  },
]

const statusConfig = {
  approved: {
    label: "Approved",
    icon: CheckCircle2,
    color: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  },
  pending: { label: "Pending", icon: Clock, color: "bg-amber-500/20 text-amber-400 border-amber-500/30" },
  processing: { label: "Processing", icon: AlertCircle, color: "bg-blue-500/20 text-blue-400 border-blue-500/30" },
  rejected: { label: "Rejected", icon: XCircle, color: "bg-red-500/20 text-red-400 border-red-500/30" },
}

export function DataUploadLogs() {
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 5

  const filteredLogs = uploadLogs.filter((log) => {
    const matchesSearch =
      log.uploaderName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.association.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.fileName.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesStatus = statusFilter === "all" || log.status === statusFilter
    return matchesSearch && matchesStatus
  })

  const totalPages = Math.ceil(filteredLogs.length / itemsPerPage)
  const paginatedLogs = filteredLogs.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage)

  const statusCounts = {
    all: uploadLogs.length,
    approved: uploadLogs.filter((l) => l.status === "approved").length,
    pending: uploadLogs.filter((l) => l.status === "pending").length,
    processing: uploadLogs.filter((l) => l.status === "processing").length,
    rejected: uploadLogs.filter((l) => l.status === "rejected").length,
  }

  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5 text-primary" />
            <div>
              <CardTitle className="text-base md:text-lg text-foreground">Data Upload Logs</CardTitle>
              <CardDescription className="text-xs md:text-sm">
                Recent dengue case reports submitted by health workers
              </CardDescription>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {(["all", "approved", "pending", "processing", "rejected"] as const).map((status) => (
              <Button
                key={status}
                variant={statusFilter === status ? "default" : "outline"}
                size="sm"
                onClick={() => {
                  setStatusFilter(status)
                  setCurrentPage(1)
                }}
                className="text-xs h-7 px-2"
              >
                {status === "all" ? "All" : statusConfig[status].label}
                <span className="ml-1 text-[10px] opacity-70">({statusCounts[status]})</span>
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Search and Filter Bar */}
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search by uploader, association, or file name..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value)
                setCurrentPage(1)
              }}
              className="pl-9 bg-secondary border-border text-sm"
            />
          </div>
          <Select
            value={statusFilter}
            onValueChange={(val) => {
              setStatusFilter(val)
              setCurrentPage(1)
            }}
          >
            <SelectTrigger className="w-full sm:w-[150px] bg-secondary border-border">
              <Filter className="h-4 w-4 mr-2" />
              <SelectValue placeholder="Filter" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Status</SelectItem>
              <SelectItem value="approved">Approved</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="processing">Processing</SelectItem>
              <SelectItem value="rejected">Rejected</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Table */}
        <div className="rounded-lg border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="bg-secondary/50 hover:bg-secondary/50">
                  <TableHead className="text-xs font-semibold text-foreground whitespace-nowrap">
                    Date Uploaded
                  </TableHead>
                  <TableHead className="text-xs font-semibold text-foreground whitespace-nowrap">
                    Uploader Name
                  </TableHead>
                  <TableHead className="text-xs font-semibold text-foreground whitespace-nowrap hidden md:table-cell">
                    Association
                  </TableHead>
                  <TableHead className="text-xs font-semibold text-foreground whitespace-nowrap">File Name</TableHead>
                  <TableHead className="text-xs font-semibold text-foreground whitespace-nowrap text-center">
                    Records
                  </TableHead>
                  <TableHead className="text-xs font-semibold text-foreground whitespace-nowrap text-center">
                    Status
                  </TableHead>
                  <TableHead className="text-xs font-semibold text-foreground whitespace-nowrap text-center">
                    Actions
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {paginatedLogs.length > 0 ? (
                  paginatedLogs.map((log) => {
                    const StatusIcon = statusConfig[log.status].icon
                    return (
                      <TableRow key={log.id} className="hover:bg-secondary/30">
                        <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                          {log.dateUploaded}
                        </TableCell>
                        <TableCell className="text-xs text-foreground font-medium whitespace-nowrap">
                          {log.uploaderName}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground hidden md:table-cell max-w-[200px] truncate">
                          {log.association}
                        </TableCell>
                        <TableCell className="text-xs text-foreground max-w-[150px] truncate">{log.fileName}</TableCell>
                        <TableCell className="text-xs text-center text-foreground">
                          {log.recordCount > 0 ? log.recordCount : "-"}
                        </TableCell>
                        <TableCell className="text-center">
                          <Badge
                            variant="outline"
                            className={`text-[10px] px-2 py-0.5 ${statusConfig[log.status].color}`}
                          >
                            <StatusIcon className="h-3 w-3 mr-1" />
                            {statusConfig[log.status].label}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-center">
                          <div className="flex items-center justify-center gap-1">
                            <Button variant="ghost" size="icon" className="h-7 w-7" title="View Details">
                              <Eye className="h-3.5 w-3.5" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-7 w-7" title="Download File">
                              <Download className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })
                ) : (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-8 text-muted-foreground text-sm">
                      No upload logs found matching your criteria
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </div>

        {/* Pagination */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
          <p className="text-xs text-muted-foreground">
            Showing {paginatedLogs.length > 0 ? (currentPage - 1) * itemsPerPage + 1 : 0} to{" "}
            {Math.min(currentPage * itemsPerPage, filteredLogs.length)} of {filteredLogs.length} entries
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="h-8 px-3"
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Prev
            </Button>
            <div className="flex items-center gap-1">
              {Array.from({ length: totalPages }, (_, i) => i + 1)
                .filter((page) => {
                  if (totalPages <= 5) return true
                  if (page === 1 || page === totalPages) return true
                  if (Math.abs(page - currentPage) <= 1) return true
                  return false
                })
                .map((page, idx, arr) => (
                  <div key={page} className="flex items-center">
                    {idx > 0 && arr[idx - 1] !== page - 1 && <span className="text-muted-foreground px-1">...</span>}
                    <Button
                      variant={currentPage === page ? "default" : "outline"}
                      size="sm"
                      onClick={() => setCurrentPage(page)}
                      className="h-8 w-8 p-0"
                    >
                      {page}
                    </Button>
                  </div>
                ))}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages || totalPages === 0}
              className="h-8 px-3"
            >
              Next
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
