"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { uploadCasesFile } from "@/lib/adminApi";

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

export function AdminUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  // keep last selected file so you can "rerun anyway" even after input clears
  const [lastFile, setLastFile] = useState<File | null>(null);

  // ✅ separate "data" vs "visibility"
  const [detailsData, setDetailsData] = useState<UploadResponse | null>(null);
  const [showDetails, setShowDetails] = useState(false);

  // show rerun button only when backend says "already_succeeded"
  const canRerun = useMemo(
    () => !!detailsData?.idempotent && detailsData?.reason === "already_succeeded" && !!lastFile,
    [detailsData, lastFile]
  );

  const runUpload = async (opts?: { force?: boolean }) => {
    const f = file ?? lastFile;
    if (!f) return;

    setBusy(true);
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
    } catch (e: any) {
      toast.error(opts?.force ? "Re-run failed" : "Upload failed", {
        id: t,
        description: e?.message ?? "Unknown error",
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      <Input
        type="file"
        accept=".csv,.xlsx"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />

      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={() => runUpload()} disabled={!(file || lastFile) || busy}>
          {busy ? "Working…" : "Upload file"}
        </Button>

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