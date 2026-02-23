"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { uploadCasesFile } from "@/lib/adminApi";

export function AdminUpload() {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");

  const onUpload = async () => {
    if (!file) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const res = await uploadCasesFile(file);
      setResult(res);
    } catch (e: any) {
      setError(e?.message ?? "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      <Input type="file" accept=".csv,.xlsx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      <Button onClick={onUpload} disabled={!file || busy}>
        {busy ? "Uploading..." : "Upload file"}
      </Button>

      {error && <div className="text-sm text-destructive">{error}</div>}
      {result && <pre className="text-xs bg-secondary p-3 rounded-md overflow-auto">{JSON.stringify(result, null, 2)}</pre>}
    </div>
  );
}