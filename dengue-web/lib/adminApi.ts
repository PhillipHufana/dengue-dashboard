// lib/adminApi.ts
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

const TOKEN_KEY = "ADMIN_TOKEN";

export function getAdminToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setAdminToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearAdminToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function adminFetch(path: string, init: RequestInit = {}) {
  const token = getAdminToken();
  const headers = new Headers(init.headers || {});
  if (token) headers.set("X-Admin-Token", token);

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res;
}

export async function adminLogin(token: string) {
  const res = await fetch(`${API_BASE}/admin/login`, {
    method: "POST",
    headers: { "X-Admin-Token": token },
  });
  if (!res.ok) throw new Error("Invalid admin token");
  return res.json();
}

export type UploadRunRow = {
  upload_id: string;
  created_at: string;
  original_filename: string | null;
  file_md5: string | null;
  storage_path: string;
  run_id: string | null;
  status: "queued" | "running" | "succeeded" | "failed";
  error_message: string | null;
  rows_count: number | null;
  min_onset_date: string | null;
  max_onset_date: string | null;
  min_week_start: string | null;
  max_week_start: string | null;
};

export async function fetchUploadRuns(limit = 50): Promise<UploadRunRow[]> {
  const res = await adminFetch(`/admin/upload-runs?limit=${limit}`);
  const json = await res.json();
  return (json.uploads ?? []) as UploadRunRow[];
}

export async function uploadCasesFile(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await adminFetch("/admin/uploads", { method: "POST", body: fd });
  return res.json();
}