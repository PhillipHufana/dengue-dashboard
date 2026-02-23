"use client";

import { useEffect, useState } from "react";
import { adminLogin, getAdminToken } from "@/lib/adminApi";

export function AdminGuard({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<"checking" | "authed" | "unauthed">("checking");
  const [message, setMessage] = useState<string>("");

  useEffect(() => {
    let alive = true;

    const verify = async () => {
      const token = (getAdminToken() ?? "").trim();
      if (!token) {
        if (!alive) return;
        setStatus("unauthed");
        setMessage("Please login with the Admin Token to use admin features.");
        return;
      }

      try {
        await adminLogin(token); // ✅ verifies token against FastAPI
        if (!alive) return;
        setStatus("authed");
        setMessage("");
      } catch (e: any) {
        if (!alive) return;
        setStatus("unauthed");
        setMessage(e?.message ?? "Unauthorized");
      }
    };

    verify();

    const onChange = () => verify();
    window.addEventListener("admin-token-changed", onChange);

    return () => {
      alive = false;
      window.removeEventListener("admin-token-changed", onChange);
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