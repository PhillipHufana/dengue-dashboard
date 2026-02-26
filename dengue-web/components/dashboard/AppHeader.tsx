"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo } from "react";
import { Bug, Calendar, Menu, Shield } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { ThemeToggle } from "@/components/dashboard/theme-toggle";
import { clearAdminToken, getAdminToken } from "@/lib/adminApi";
import { LoginModal } from "@/components/dashboard/login-modal";
import { supabaseLogout } from "@/lib/adminApi";
import { RiskMetricToggle } from "@/components/dashboard/risk-metric-toggle";
import { PeriodSelect } from "@/components/dashboard/period-select";
type HeaderMode = "public" | "admin";

export function AppHeader({
  mode,
  lastUpdated,
  rightSlot,
}: {
  mode: HeaderMode;
  lastUpdated?: string | null;
  rightSlot?: React.ReactNode; // optional extra controls (like time range) on desktop
}) {
  const router = useRouter();
  const hasAdminToken = useMemo(() => !!getAdminToken(), []);

  const onLogout = () => {
    clearAdminToken();
    window.dispatchEvent(new Event("admin-token-changed"));
    router.push("/"); // ✅ go back to dashboard
  };

  const title = mode === "admin" ? "Denguard Admin Console" : "Denguard Dengue Surveillance";
  const subtitle =
    mode === "admin"
      ? "Uploads • Runs • Logs"
      : "Predictive outbreak monitoring - 182 Barangays";

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60 px-4 py-3 md:px-6 md:py-4">
      <div className="flex items-center justify-between gap-3">
        {/* Logo and Title */}
        <div className="flex items-center gap-2 md:gap-3">
          <div className="flex h-8 w-8 md:h-10 md:w-10 items-center justify-center rounded-lg bg-primary">
            {mode === "admin" ? (
              <Shield className="h-4 w-4 md:h-5 md:w-5 text-primary-foreground" />
            ) : (
              <Bug className="h-4 w-4 md:h-5 md:w-5 text-primary-foreground" />
            )}
          </div>
          <div>
            <h1 className="text-base md:text-xl font-semibold text-foreground">{title}</h1>
            <p className="hidden sm:block text-xs md:text-sm text-muted-foreground">{subtitle}</p>
          </div>
        </div>

        {/* Desktop Controls */}
        <div className="hidden md:flex items-center gap-3">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Calendar className="h-4 w-4" />
            <span>Last updated: {lastUpdated ?? "—"}</span>
          </div>

          {rightSlot ?? null}

          {mode === "public" ? (
            <Link href="/admin">
              <Button variant="outline" className="bg-transparent">
                Admin
              </Button>
            </Link>
          ) : (
            <Link href="/">
              <Button variant="outline" className="bg-transparent">
                Dashboard
              </Button>
            </Link>
          )}

          <ThemeToggle />

          {/* Token auth (temporary) */}
          {mode === "admin" ? (
            <>
              <LoginModal />
              <Button
                variant="outline"
                onClick={async () => {
                  await supabaseLogout();
                  window.dispatchEvent(new Event("admin-auth-changed"));
                  router.push("/"); // go back to dashboard
                }}
              >
                Logout
              </Button>
            </>
          ) : null}
        </div>

        {/* Mobile Menu */}
        <div className="flex md:hidden items-center gap-2">
          <ThemeToggle />
          <Sheet>
            <SheetTrigger asChild>
              <Button variant="outline" size="icon" className="h-8 w-8 bg-transparent">
                <Menu className="h-4 w-4" />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-[280px]">
              <div className="flex flex-col gap-3">
                {mode === "public" ? (
                  <Link href="/admin">
                    <Button variant="outline" className="w-full bg-transparent">
                      Admin
                    </Button>
                  </Link>
                ) : (
                  <Link href="/">
                    <Button variant="outline" className="w-full bg-transparent">
                      Dashboard
                    </Button>
                  </Link>
                )}

                <RiskMetricToggle compact />
                <PeriodSelect compact />
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Calendar className="h-4 w-4" />
                  <span>Last updated: {lastUpdated ?? "—"}</span>
                </div>

                {mode === "admin" ? (
                  <>
                    <LoginModal variant="mobile" />
                    <Button
                      variant="outline"
                      onClick={async () => {
                        await supabaseLogout();
                        window.dispatchEvent(new Event("admin-auth-changed"));
                        router.push("/"); // go back to dashboard
                      }}
                    >
                      Logout
                    </Button>
                  </>
                ) : null}
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}