"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { fetchUploadRuns, UploadRunRow, cancelUpload } from "@/lib/adminApi";
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
} from "lucide-react";

const statusConfig = {
  approved: { label: "Approved", icon: CheckCircle2, color: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30" },
  pending: { label: "Pending", icon: Clock, color: "bg-amber-500/20 text-amber-400 border-amber-500/30" },
  processing: { label: "Processing", icon: AlertCircle, color: "bg-blue-500/20 text-blue-400 border-blue-500/30" },
  rejected: { label: "Rejected", icon: XCircle, color: "bg-red-500/20 text-red-400 border-red-500/30" },
};

type UiStatus = "approved" | "pending" | "processing" | "rejected";

function mapDbStatusToUi(status: UploadRunRow["status"]): UiStatus {
  if (status === "queued") return "pending";
  if (status === "running") return "processing";
  if (status === "succeeded") return "approved";
  return "rejected"; // failed/canceled/deleted
}

function fmtDate(ts: string) {
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
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 5;

  const [rows, setRows] = useState<UploadRunRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState<string>("");

  const load = async () => {
    setLoading(true);
    try {
      const data = await fetchUploadRuns(200);
      setRows(data);
      setApiError("");
    } catch (e: any) {
      setRows([]);
      setApiError(e?.message ?? "Failed to load upload runs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, statusFilter]);

  const filteredLogs = useMemo(() => {
    return rows
      .map((r) => {
        const uploaderName =
          [r.first_name, r.last_name].filter(Boolean).join(" ") ||
          (r.user_id ? r.user_id.slice(0, 8) + "…" : "—");

        return {
          upload_id: r.upload_id,
          dateUploaded: fmtDate(r.created_at),
          fileName: r.original_filename ?? r.storage_path.split("/").pop() ?? "upload",
          status: mapDbStatusToUi(r.status),
          recordCount: r.rows_count ?? 0,
          run_id: r.run_id,
          error: r.error_message,

          uploaderName,
          association: r.association ?? "—",
          rawStatus: r.status,
        };
      })
      .filter((log) => {
        const q = searchQuery.toLowerCase();
        const matchesSearch =
          log.fileName.toLowerCase().includes(q) ||
          log.uploaderName.toLowerCase().includes(q) ||
          log.association.toLowerCase().includes(q) ||
          (log.run_id ?? "").toLowerCase().includes(q);

        const matchesStatus = statusFilter === "all" || log.status === statusFilter;
        return matchesSearch && matchesStatus;
      });
  }, [rows, searchQuery, statusFilter]);

  const totalPages = Math.ceil(filteredLogs.length / itemsPerPage);
  const paginatedLogs = filteredLogs.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);

  const statusCounts = {
    all: filteredLogs.length,
    approved: filteredLogs.filter((l) => l.status === "approved").length,
    pending: filteredLogs.filter((l) => l.status === "pending").length,
    processing: filteredLogs.filter((l) => l.status === "processing").length,
    rejected: filteredLogs.filter((l) => l.status === "rejected").length,
  };

  const onCancel = async (upload_id: string) => {
    const t = toast.loading("Canceling upload…");
    try {
      await cancelUpload(upload_id);
      toast.success("Upload canceled", { id: t });
      await load(); // refresh immediately
    } catch (e: any) {
      toast.error("Cancel failed", { id: t, description: e?.message ?? "Unknown error" });
    }
  };

  return (
    <Card className="bg-card border-border">
      <CardHeader className="pb-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5 text-primary" />
            <div>
              <CardTitle className="text-base md:text-lg text-foreground">Data Upload Logs</CardTitle>
              <CardDescription className="text-xs md:text-sm">
                {loading ? "Refreshing…" : "Recent uploads and pipeline status"}
              </CardDescription>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {(["all", "approved", "pending", "processing", "rejected"] as const).map((status) => (
              <Button
                key={status}
                variant={statusFilter === status ? "default" : "outline"}
                size="sm"
                onClick={() => setStatusFilter(status)}
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
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search by uploader, association, run id, file name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 bg-secondary border-border text-sm"
            />
          </div>

          <Select value={statusFilter} onValueChange={setStatusFilter}>
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

        <div className="rounded-lg border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="bg-secondary/50 hover:bg-secondary/50">
                  <TableHead className="text-xs font-semibold text-foreground whitespace-nowrap">Date Uploaded</TableHead>
                  <TableHead className="text-xs font-semibold text-foreground whitespace-nowrap">Uploader Name</TableHead>
                  <TableHead className="text-xs font-semibold text-foreground whitespace-nowrap hidden md:table-cell">
                    Association
                  </TableHead>
                  <TableHead className="text-xs font-semibold text-foreground whitespace-nowrap">File Name</TableHead>
                  <TableHead className="text-xs font-semibold text-foreground whitespace-nowrap text-center">Records</TableHead>
                  <TableHead className="text-xs font-semibold text-foreground whitespace-nowrap text-center">Status</TableHead>
                  <TableHead className="text-xs font-semibold text-foreground whitespace-nowrap text-center">Actions</TableHead>
                </TableRow>
              </TableHeader>

              <TableBody>
                {paginatedLogs.length > 0 ? (
                  paginatedLogs.map((log) => {
                    const StatusIcon = statusConfig[log.status].icon;

                    return (
                      <TableRow key={log.upload_id} className="hover:bg-secondary/30">
                        <TableCell className="text-xs text-muted-foreground whitespace-nowrap">{log.dateUploaded}</TableCell>

                        <TableCell className="text-xs text-foreground font-medium whitespace-nowrap">
                          {log.uploaderName}
                        </TableCell>

                        <TableCell className="text-xs text-muted-foreground hidden md:table-cell max-w-[220px] truncate">
                          {log.association}
                        </TableCell>

                        <TableCell className="text-xs text-foreground max-w-[180px] truncate">{log.fileName}</TableCell>

                        <TableCell className="text-xs text-center text-foreground">{log.recordCount || "-"}</TableCell>

                        <TableCell className="text-center">
                          <Badge variant="outline" className={`text-[10px] px-2 py-0.5 ${statusConfig[log.status].color}`}>
                            <StatusIcon className="h-3 w-3 mr-1" />
                            {statusConfig[log.status].label}
                          </Badge>
                        </TableCell>

                        <TableCell className="text-center">
                          {(log.rawStatus === "queued" || log.rawStatus === "running") ? (
                            <Button
                              variant="outline"
                              size="sm"
                              className="h-7 px-2 text-xs"
                              onClick={() => onCancel(log.upload_id)}
                            >
                              Cancel
                            </Button>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </TableCell>
                      </TableRow>
                    );
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
  );
}