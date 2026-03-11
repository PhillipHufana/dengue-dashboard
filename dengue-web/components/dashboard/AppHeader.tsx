"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Bug, Calendar, LogIn, Shield, UserCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ThemeToggle } from "@/components/dashboard/theme-toggle";
import { LoginModal } from "@/components/dashboard/login-modal";
import { supabase } from "@/lib/supabaseClient";
import { fetchMyProfile, supabaseLogout, type AdminProfile } from "@/lib/adminApi";
import { RiskMetricToggle } from "@/components/dashboard/risk-metric-toggle";
import { PeriodSelect } from "@/components/dashboard/period-select";
import { ModelSelect } from "@/components/dashboard/model-select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

type HeaderMode = "public" | "admin";

function displayName(profile: AdminProfile | null): string {
  if (!profile) return "Profile";
  const first = (profile.first_name || "").trim();
  const last = (profile.last_name || "").trim();
  const full = `${first} ${last}`.trim();
  return full || "Profile";
}

function profileInitials(profile: AdminProfile | null): string {
  if (!profile) return "P";
  const first = (profile.first_name || "").trim();
  const last = (profile.last_name || "").trim();
  const a = first ? first[0] : "";
  const b = last ? last[0] : "";
  const out = `${a}${b}`.toUpperCase();
  return out || "P";
}

function formatReadableDate(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  const hasTime = /T|\d{1,2}:\d{2}/.test(value);
  return d.toLocaleString(
    [],
    hasTime
      ? {
          year: "numeric",
          month: "short",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
        }
      : {
          year: "numeric",
          month: "short",
          day: "2-digit",
        },
  );
}

function ProfileMenu({
  profile,
  email,
  onLogout,
  compact = false,
}: {
  profile: AdminProfile | null;
  email: string | null;
  onLogout: () => Promise<void>;
  compact?: boolean;
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size={compact ? "sm" : "default"}
          className={compact ? "h-8 px-2" : "bg-transparent"}
          title="Open profile and logout"
        >
          <UserCircle className="h-4 w-4 mr-1" />
          <span className={compact ? "max-w-[88px] truncate" : "max-w-[140px] truncate"}>
            {compact ? profileInitials(profile) : displayName(profile)}
          </span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72" align="end">
        <div className="space-y-2">
          <div className="text-sm font-semibold">{displayName(profile)}</div>
          <div className="text-xs text-muted-foreground">
            Email: {email || "—"}
          </div>
          <div className="text-xs text-muted-foreground">
            Association: {profile?.association || "—"}
          </div>
          <div className="text-xs text-muted-foreground">
            Role: {profile?.role || "user"}
          </div>
          <Button className="w-full mt-2" variant="outline" onClick={onLogout}>
            Logout
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}

export function AppHeader({
  mode,
  lastUpdated,
  disaggScheme,
  rightSlot,
}: {
  mode: HeaderMode;
  lastUpdated?: string | null;
  disaggScheme?: string | null;
  rightSlot?: React.ReactNode;
}) {
  const router = useRouter();
  const [isAuthed, setIsAuthed] = useState(false);
  const [profile, setProfile] = useState<AdminProfile | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  const [loginOpen, setLoginOpen] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);
  const autoOpenedLoginRef = useRef(false);

  useEffect(() => {
    let alive = true;

    const refresh = async () => {
      const { data } = await supabase.auth.getSession();
      const authed = !!data.session;
      if (!alive) return;
      setIsAuthed(authed);
      setEmail(data.session?.user?.email ?? null);
      setAuthChecked(true);

      if (!authed) {
        setProfile(null);
        setEmail(null);
        return;
      }
      try {
        const p = await fetchMyProfile();
        if (alive) setProfile(p);
      } catch {
        if (alive) setProfile(null);
      }
    };

    refresh();
    const { data: sub } = supabase.auth.onAuthStateChange(() => {
      window.dispatchEvent(new Event("admin-auth-changed"));
      refresh();
    });

    const onAuthChanged = () => refresh();
    window.addEventListener("admin-auth-changed", onAuthChanged);

    return () => {
      alive = false;
      sub.subscription.unsubscribe();
      window.removeEventListener("admin-auth-changed", onAuthChanged);
    };
  }, []);

  useEffect(() => {
    if (mode === "admin" && authChecked && !isAuthed && !autoOpenedLoginRef.current) {
      setLoginOpen(true);
      autoOpenedLoginRef.current = true;
    }
  }, [mode, authChecked, isAuthed]);

  const onLogout = async () => {
    await supabaseLogout();
    window.dispatchEvent(new Event("admin-auth-changed"));
    setLoginOpen(false);
    router.push("/");
  };

  const title = mode === "admin" ? "Denguard Admin Console" : "Denguard Dengue Surveillance";
  const subtitle = mode === "admin" ? "Uploads - Runs - Logs" : "Predictive outbreak monitoring - 182 Barangays";

  const adminActionDesktop = useMemo(() => {
    if (!isAuthed) return null;
    return <ProfileMenu profile={profile} email={email} onLogout={onLogout} />;
  }, [isAuthed, profile, email]);

  return (
    <header className="sticky top-0 z-[900] overflow-visible border-b border-border bg-background opacity-100 px-3 py-2 md:px-6 md:py-4">
      <LoginModal
        open={loginOpen}
        onOpenChange={setLoginOpen}
        showTrigger={false}
        redirectToAdminOnLogin
      />

      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 md:gap-3 min-w-0">
          <div className="flex h-7 w-7 md:h-10 md:w-10 items-center justify-center rounded-md md:rounded-lg bg-primary shrink-0">
            {mode === "admin" ? (
              <Shield className="h-4 w-4 md:h-5 md:w-5 text-primary-foreground" />
            ) : (
              <Bug className="h-4 w-4 md:h-5 md:w-5 text-primary-foreground" />
            )}
          </div>
          <div className="min-w-0">
            <h1 className="text-sm md:text-xl font-semibold text-foreground truncate">
              <span className="md:hidden">Denguard</span>
              <span className="hidden md:inline">{title}</span>
            </h1>
            <p className="hidden sm:block text-xs md:text-sm text-muted-foreground truncate">{subtitle}</p>
          </div>
        </div>

        <div className="hidden md:flex items-center gap-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Calendar className="h-4 w-4" />
            <span>Last updated: {lastUpdated ?? "—"}</span>
          </div>

          {rightSlot ?? null}
          {disaggScheme ? (
            <Badge variant="secondary" className="text-[10px] uppercase tracking-wide">
              Disagg: {disaggScheme}
            </Badge>
          ) : null}
          {mode === "public" ? <ModelSelect /> : null}

          {mode === "public" ? (
            isAuthed ? (
              <Link href="/admin">
                <Button variant="outline" className="bg-transparent">Admin</Button>
              </Link>
            ) : (
              <Button variant="outline" className="bg-transparent" onClick={() => setLoginOpen(true)}>
                <LogIn className="h-4 w-4 mr-1" />
                Admin Login
              </Button>
            )
          ) : null}

          {mode === "admin" ? (
            <Link href="/">
              <Button variant="outline" className="bg-transparent">Dashboard</Button>
            </Link>
          ) : null}

          <ThemeToggle />
          {adminActionDesktop}
        </div>

        <div className="flex md:hidden items-center gap-2 shrink-0">
          <ThemeToggle />
          {mode === "admin" ? (
            <Link href="/">
              <Button variant="outline" size="sm" className="h-8 px-3 bg-transparent">
                Dashboard
              </Button>
            </Link>
          ) : isAuthed ? (
            <Link href="/admin">
              <Button variant="outline" size="sm" className="h-8 px-3 bg-transparent">
                Admin
              </Button>
            </Link>
          ) : (
            <Button
              variant="outline"
              size="sm"
              className="h-8 px-3 bg-transparent"
              onClick={() => setLoginOpen(true)}
              title="Sign in to access admin"
            >
              Admin Login
            </Button>
          )}
          {isAuthed ? <ProfileMenu profile={profile} email={email} onLogout={onLogout} compact /> : null}
        </div>
      </div>

      <div className="mt-2 md:hidden space-y-1.5">
        {mode === "public" ? (
          <>
            <div className="grid grid-cols-2 gap-1.5">
              <ModelSelect compact />
              <PeriodSelect compact />
            </div>
            <RiskMetricToggle compact />
          </>
        ) : null}
        <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <Calendar className="h-3.5 w-3.5" />
          <span className="truncate">Last updated: {lastUpdated ?? "—"}</span>
          {disaggScheme ? (
            <Badge variant="secondary" className="text-[9px] uppercase tracking-wide ml-1">
              {disaggScheme}
            </Badge>
          ) : null}
        </div>
      </div>

      <div className="mt-1 flex md:hidden items-center gap-2 text-[11px] text-muted-foreground">
        <span className="truncate">Last updated: {lastUpdated ?? "—"}</span>
        {disaggScheme ? (
          <Badge variant="secondary" className="h-5 px-1.5 text-[10px] uppercase tracking-wide">
            Disagg: {disaggScheme}
          </Badge>
        ) : null}
      </div>
    </header>
  );
}
