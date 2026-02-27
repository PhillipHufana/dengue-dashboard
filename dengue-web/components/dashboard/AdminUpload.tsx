"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { uploadCasesFile } from "@/lib/adminApi";
import { Info } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { preflightCasesFile } from "@/lib/adminApi";

type UploadResponse = {
  idempotent?: boolean;
  reason?: "already_active" | "already_succeeded";
  upload_id?: string;
  run_id?: string;
  status?: string;
  rows_count?: number;
  warnings?: { dob_after_onset_count?: number };
  [k: string]: any;
};

type PreflightMeta = {
  rows_count: number;
  min_onset_date: string | null;
  max_onset_date: string | null;
  min_week_start: string | null;
  max_week_start: string | null;
  warnings?: {
      dob_after_onset_count?: number;
      dob_after_onset_sample_rows?: number[];
    };
    matched_columns?: Record<string, string>;
  };

export function AdminUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  // keep last selected file so you can "rerun anyway" even after input clears
  const [lastFile, setLastFile] = useState<File | null>(null);

  // ✅ separate "data" vs "visibility"
  const [detailsData, setDetailsData] = useState<UploadResponse | null>(null);
  const [showDetails, setShowDetails] = useState(false);

  const [preflightLoading, setPreflightLoading] = useState(false);

  // show rerun button only when backend says "already_succeeded"
  const canRerun = useMemo(
    () => !!detailsData?.idempotent && detailsData?.reason === "already_succeeded" && !!lastFile,
    [detailsData, lastFile]
  );

  const runUpload = async (opts?: { force?: boolean }) => {
    const f = file ?? lastFile;
    if (!f) return;

    setBusy(true);
    setPreflightLoading(false);
    setDetailsData(null);
    setShowDetails(false);

    const t = toast.loading(opts?.force ? "Re-running upload…" : "Uploading file…");

    try {
      const res: UploadResponse = await uploadCasesFile(f, opts);

      setDetailsData(res);
      setLastFile(f);

      // ---- idempotent cases ----
      if (res.idempotent && res.reason === "already_active") {
        toast.info("Already queued / running", {
          id: t,
          description: `Upload ${String(res.upload_id ?? "").slice(0, 8)}… • Run ${String(res.run_id ?? "").slice(0, 8)}…`,
        });
        return;
      }

      if (res.idempotent && res.reason === "already_succeeded") {
        toast.message("Already processed", {
          id: t,
          description: `This exact file was already processed (run ${String(res.run_id ?? "").slice(0, 8)}…). Click “Re-run anyway” to force a new run.`,
        });
        return;
      }

      // ---- normal (new) upload created ----
      toast.success("Upload queued", {
        id: t,
        description: `Run ${String(res.run_id).slice(0, 8)}… • ${res.rows_count ?? "?"} rows`,
      });

      // warnings toast
      if ((res?.warnings?.dob_after_onset_count ?? 0) > 0) {
        toast.warning("Data warnings found", {
          description: `${res.warnings?.dob_after_onset_count} rows have DOB after DOnset`,
        });
      }

      // clear the file input after successful creation
      setFile(null);
      setPreflight(null);
      setPreflightErr("");
    } catch (e: any) {
      toast.error(opts?.force ? "Re-run failed" : "Upload failed", {
        id: t,
        description: e?.message ?? "Unknown error",
      });
    } finally {
      setBusy(false);
    }
  };


  const [preflight, setPreflight] = useState<PreflightMeta | null>(null);
  const [preflightErr, setPreflightErr] = useState<string>("");

  const onPickFile = async (f: File | null) => {
    setFile(f);
    setPreflight(null);
    setPreflightErr("");

    if (!f) return;

    setPreflightLoading(true);
    try {
      const meta = await preflightCasesFile(f);
      setPreflight(meta);
    } catch (e: any) {
      setPreflightErr(e?.message ?? "Preflight failed");
    } finally {
      setPreflightLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      <Input
        type="file"
        accept=".csv,.xlsx"
        onChange={(e) => onPickFile(e.target.files?.[0] ?? null)}
      />

      <div className="flex flex-wrap items-center gap-2">
      
        <Button
          onClick={() => runUpload()}
          disabled={!(file || lastFile) || busy || !!preflightErr || preflightLoading}
        >
          {busy ? "Working…" : preflightLoading ? "Checking…" : "Upload file"}
        </Button>

        <Popover>
          <PopoverTrigger asChild>
            <Button type="button" variant="ghost" size="icon" className="h-8 w-8">
              <Info className="h-4 w-4" />
            </Button>
          </PopoverTrigger>

          <PopoverContent className="w-80 text-sm">
            <div className="space-y-2">
              <p className="font-medium">Upload requirements</p>

              <ul className="list-disc pl-4 text-xs text-muted-foreground space-y-1">
                <li>File type: .xlsx or .csv</li>
                <li>
                  Required columns: <b>CASE ID</b>, <b>DOnset</b>, <b>(Current Address) Barangay</b>
                </li>
                <li>DOnset must be a valid date and not in the future</li>
                <li>DOB and Sex are optional</li>
              </ul>

              <a
                className="text-xs text-primary underline"
                href="/templates/denguard_upload_template.xlsx"
                download
              >
                Download Excel template
              </a>

              {preflightLoading ? (
                <div className="mt-3 text-xs text-muted-foreground">Running preflight…</div>
              ) : preflight ? (
                <div className="mt-3 text-xs bg-secondary/50 border border-border rounded-md p-2 space-y-1">
                  <div><b>Rows:</b> {preflight.rows_count}</div>
                  <div><b>Onset:</b> {preflight.min_onset_date} → {preflight.max_onset_date}</div>
                  <div><b>Weeks:</b> {preflight.min_week_start} → {preflight.max_week_start}</div>

                  {(preflight?.warnings?.dob_after_onset_count ?? 0) > 0 && (
                    <div className="text-amber-400">
                      Warning: {preflight.warnings?.dob_after_onset_count ?? 0} row(s) have DOB after DOnset.
                    </div>
                  )}
                </div>
              ) : preflightErr ? (
                <div className="mt-3 text-xs text-destructive">{preflightErr}</div>
              ) : (
                <div className="mt-3 text-xs text-muted-foreground">
                  Pick a file to run checker.
                </div>
              )}
            </div>
          </PopoverContent>
        </Popover>

        {/* ✅ only appears when backend says "already_succeeded" */}
        {canRerun && (
          <Button
            type="button"
            variant="secondary"
            onClick={() => runUpload({ force: true })}
            disabled={busy}
          >
            Re-run anyway
          </Button>
        )}

        {detailsData && (
          <Button
            type="button"
            variant="outline"
            onClick={() => setShowDetails((v) => !v)}
          >
            {showDetails ? "Hide details" : "Show details"}
          </Button>
        )}
      </div>

      {detailsData && showDetails && (
        <pre className="text-xs bg-secondary p-3 rounded-md overflow-auto">
          {JSON.stringify(detailsData, null, 2)}
        </pre>
      )}
    </div>
  );
}