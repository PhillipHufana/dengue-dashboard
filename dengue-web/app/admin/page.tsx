"use client";

import { useEffect, useMemo, useState } from "react";
import { AdminUpload } from "@/components/dashboard/AdminUpload";
import { DataUploadLogs } from "@/components/dashboard/upload-logs";
import { AdminGuard } from "@/components/dashboard/AdminGuard";
import { fetchUploadRuns } from "@/lib/adminApi";
import { AppHeader } from "@/components/dashboard/AppHeader";

export default function AdminPage() {
  const [lastSucceededAt, setLastSucceededAt] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;

    const refreshLastSucceeded = async () => {
      try {
        const rows = await fetchUploadRuns(200);
        const succeeded = rows
          .filter((r) => r.status === "succeeded" && !!r.created_at)
          .sort(
            (a, b) =>
              new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
          );
        const latest = succeeded[0]?.created_at ?? null;
        if (alive) setLastSucceededAt(latest);
      } catch {
        if (alive) setLastSucceededAt(null);
      }
    };

    refreshLastSucceeded();
    const interval = window.setInterval(refreshLastSucceeded, 30_000);

    const onAuthChanged = () => refreshLastSucceeded();
    window.addEventListener("admin-auth-changed", onAuthChanged);

    return () => {
      alive = false;
      window.clearInterval(interval);
      window.removeEventListener("admin-auth-changed", onAuthChanged);
    };
  }, []);

  const lastUpdatedLabel = useMemo(() => {
    if (!lastSucceededAt) return null;
    const d = new Date(lastSucceededAt);
    if (Number.isNaN(d.getTime())) return null;
    return d.toLocaleString([], {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }, [lastSucceededAt]);

  return (
    <div className="min-h-screen bg-background">
    <AppHeader mode="admin" lastUpdated={lastUpdatedLabel} />
    <main className="p-3 md:p-6">
    <div className="space-y-6">
      <AdminGuard>
        <AdminUpload />
        <DataUploadLogs />
      </AdminGuard>
    </div>
  </main>
  </div>
  );
}
      
