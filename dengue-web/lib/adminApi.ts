// lib/adminApi.ts
import { supabase } from "@/lib/supabaseClient";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const TOKEN_KEY = "ADMIN_TOKEN";

export function getAdminToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setAdminToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
  window.dispatchEvent(new Event("admin-token-changed"));
}

export function clearAdminToken() {
  localStorage.removeItem(TOKEN_KEY);
  window.dispatchEvent(new Event("admin-token-changed"));
}

async function getSupabaseAccessToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}


async function getJwt(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  const jwt = data.session?.access_token;
  if (!jwt) throw new Error("Not logged in");
  return jwt;
}

async function adminFetch(path: string, init: RequestInit = {}) {
  const jwt = await getJwt();
  const headers = new Headers(init.headers || {});
  headers.set("Authorization", `Bearer ${jwt}`);
  headers.set("Accept", "application/json");

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    try {
      const j = JSON.parse(text);
      throw new Error(j?.detail ?? text ?? `HTTP ${res.status}`);
    } catch {
      throw new Error(text || `HTTP ${res.status}`);
    }
  }
  return res;
}

// ✅ New: Supabase login
export async function supabaseLogin(email: string, password: string) {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw new Error(error.message);
  return { ok: true, session: data.session, user: data.user };
}

export async function supabaseSignup(
  email: string,
  password: string,
  profile?: { first_name?: string; last_name?: string; association?: string | null }
) {
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      data: profile ?? {},
    },
  });
  if (error) throw new Error(error.message);
  return { ok: true, user: data.user, session: data.session };
}

export async function supabaseLogout() {
  const { error } = await supabase.auth.signOut();
  if (error) throw new Error(error.message);
  return { ok: true };
}

export type AdminProfile = {
  user_id: string;
  first_name: string | null;
  last_name: string | null;
  association: string | null;
  role: string | null;
};

export async function fetchMyProfile(): Promise<AdminProfile> {
  const res = await adminFetch(`/admin/me`);
  return res.json();
}

export type UploadRunRow = {
  upload_id: string;
  created_at: string;
  original_filename: string | null;
  file_md5: string | null;
  storage_path: string;
  run_id: string | null;

  status: "queued" | "running" | "succeeded" | "failed" | "canceled" | "deleted";
  error_message: string | null;
  rows_count: number | null;

  min_onset_date: string | null;
  max_onset_date: string | null;
  min_week_start: string | null;
  max_week_start: string | null;

  user_id: string | null;
  first_name: string | null;
  last_name: string | null;
  association: string | null;
};

export async function fetchUploadRuns(limit = 50): Promise<UploadRunRow[]> {
  const res = await adminFetch(`/admin/upload-runs?limit=${limit}`);
  const json = await res.json();
  return (json.uploads ?? []) as UploadRunRow[];
}

export async function uploadCasesFile(file: File, opts?: { force?: boolean }) {
  const fd = new FormData();
  fd.append("file", file);
  const q = opts?.force ? "?force=true" : "";
  const res = await adminFetch(`/admin/uploads${q}`, { method: "POST", body: fd });
  return res.json();
}

export async function cancelUpload(upload_id: string) {
  const res = await adminFetch(`/admin/uploads/${upload_id}/cancel`, { method: "POST" });
  return res.json();
}

export async function preflightCasesFile(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await adminFetch(`/admin/uploads/preflight`, { method: "POST", body: fd });
  return res.json();
}

export async function requestAccessProfile(input: {
  first_name: string;
  last_name: string;
  association?: string | null;
}) {
  const res = await adminFetch(`/admin/request-access`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return res.json();
}
