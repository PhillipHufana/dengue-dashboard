"use client";

import { LoginModal } from "@/components/dashboard/login-modal";
import { AdminUpload } from "@/components/dashboard/AdminUpload";
import { DataUploadLogs } from "@/components/dashboard/upload-logs";
import { AdminGuard } from "@/components/dashboard/AdminGuard";
import { clearAdminToken } from "@/lib/adminApi";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { DengueDashboard } from "@/components/dengue-dashboard";
import { AppHeader } from "@/components/dashboard/AppHeader";
export default function AdminPage() {
  return (
    <div className="min-h-screen bg-background">
    <AppHeader mode="admin" lastUpdated={null} />
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
      