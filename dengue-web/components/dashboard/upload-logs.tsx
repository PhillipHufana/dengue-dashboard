"use client"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useEffect, useMemo, useState } from "react";
import { fetchUploadRuns, UploadRunRow } from "@/lib/adminApi";
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
function mapDbStatusToUi(status: UploadRunRow["status"]): "approved" | "pending" | "processing" | "rejected" {
  if (status === "queued") return "pending";
  if (status === "running") return "processing";
  if (status === "succeeded") return "approved";
  return "rejected";
}

function fmtDate(ts: string) {
  // ts is ISO from Supabase; show YYYY-MM-DD HH:mm
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd} ${hh}:${mi}`;
}

export function DataUploadLogs() {
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [currentPage, setCurrentPage] = useState(1)
  const itemsPerPage = 5
  const [rows, setRows] = useState<UploadRunRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState<string>("");

  const filteredLogs = useMemo(() => {
    return rows
        .map((r) => ({
        upload_id: r.upload_id,
        dateUploaded: fmtDate(r.created_at),
        fileName: r.original_filename ?? r.storage_path.split("/").pop() ?? "upload",
        status: mapDbStatusToUi(r.status),
        recordCount: r.rows_count ?? 0,
        run_id: r.run_id,
        error: r.error_message,
        }))
        .filter((log) => {
        const matchesSearch =
            log.fileName.toLowerCase().includes(searchQuery.toLowerCase()) ||
            (log.run_id ?? "").toLowerCase().includes(searchQuery.toLowerCase());
        const matchesStatus = statusFilter === "all" || log.status === statusFilter;
        return matchesSearch && matchesStatus;
        });
    }, [rows, searchQuery, statusFilter]);

  const totalPages = Math.ceil(filteredLogs.length / itemsPerPage)
  const paginatedLogs = filteredLogs.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage)

  const statusCounts = {
    all: filteredLogs.length,
    approved: filteredLogs.filter((l) => l.status === "approved").length,
    pending: filteredLogs.filter((l) => l.status === "pending").length,
    processing: filteredLogs.filter((l) => l.status === "processing").length,
    rejected: filteredLogs.filter((l) => l.status === "rejected").length,
    };
  
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, statusFilter]);

  useEffect(() => {
    let alive = true;

    const tick = async () => {
        setLoading(true);
        try {
          const data = await fetchUploadRuns(200);
          if (alive) {
            setRows(data);
            setApiError("");
          }
        } catch (e: any) {
          if (alive) {
            setRows([]);
            setApiError(e?.message ?? "Failed to load upload runs");
          }
        } finally {
          if (alive) setLoading(false);
        }
    };

    tick();
    const t = setInterval(tick, 8000);
    return () => {
        alive = false;
        clearInterval(t);
    };
    }, []);

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
                      <TableRow key={log.upload_id} className="hover:bg-secondary/30">
                        <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                          {log.dateUploaded}
                        </TableCell>
                        <TableCell className="text-xs text-foreground font-medium whitespace-nowrap">
                          {log.run_id ?? "-"}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground hidden md:table-cell max-w-[200px] truncate">
                          {log.error ? `⚠ ${log.error}` : "-"}
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
                      {apiError ? apiError : "No upload logs found matching your criteria"}
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
