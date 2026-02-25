"use client";

import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabaseClient";

export function AdminGuard({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<"checking" | "authed" | "unauthed">("checking");
  const [message, setMessage] = useState<string>("");

  useEffect(() => {
    let alive = true;

    const check = async () => {
      setStatus("checking");
      setMessage("");

      const { data, error } = await supabase.auth.getSession();
      const session = data.session;

      if (!alive) return;

      if (error || !session) {
        setStatus("unauthed");
        setMessage("Please login to access admin features.");
        return;
      }

      // ✅ logged in (role enforcement comes next via backend)
      setStatus("authed");
      setMessage("");
    };

    check();

    const onChange = () => check();
    window.addEventListener("admin-auth-changed", onChange);

    // Supabase also emits auth state changes
    const { data: sub } = supabase.auth.onAuthStateChange(() => {
      window.dispatchEvent(new Event("admin-auth-changed"));
    });

    return () => {
      alive = false;
      window.removeEventListener("admin-auth-changed", onChange);
      sub.subscription.unsubscribe();
    };
  }, []);

  if (status === "checking") {
    return <div className="text-sm text-muted-foreground">Checking admin access…</div>;
  }

  if (status === "unauthed") {
    return <div className="text-sm text-muted-foreground">{message}</div>;
  }

  return <>{children}</>;
}