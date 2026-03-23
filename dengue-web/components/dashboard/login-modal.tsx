// components/dashboard/login-modal.tsx
"use client";

import type React from "react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LogIn, Loader2 } from "lucide-react";
import { supabaseLogin, supabaseSignup, requestAccessProfile } from "@/lib/adminApi";
import { toast } from "sonner";
interface LoginModalProps {
  variant?: "default" | "mobile";
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  showTrigger?: boolean;
  redirectToAdminOnLogin?: boolean;
}

const PENDING_PROFILE_KEY_PREFIX = "pending_access_profile:";

function pendingKey(email: string): string {
  return `${PENDING_PROFILE_KEY_PREFIX}${email.trim().toLowerCase()}`;
}

function stashPendingProfile(email: string, payload: { first_name: string; last_name: string; association?: string | null }) {
  if (typeof window === "undefined") return;
  localStorage.setItem(pendingKey(email), JSON.stringify(payload));
}

function popPendingProfile(email: string): { first_name: string; last_name: string; association?: string | null } | null {
  if (typeof window === "undefined") return null;
  const key = pendingKey(email);
  const raw = localStorage.getItem(key);
  if (!raw) return null;
  localStorage.removeItem(key);
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function LoginModal({
  variant = "default",
  open,
  onOpenChange,
  showTrigger = true,
  redirectToAdminOnLogin = false,
}: LoginModalProps) {
  const router = useRouter();
  const [localOpen, setLocalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [association, setAssociation] = useState("");

  const [mode, setMode] = useState<"login" | "signup">("login");

  const resolvedOpen = open ?? localOpen;
  const setResolvedOpen = (next: boolean) => {
    if (open === undefined) setLocalOpen(next);
    onOpenChange?.(next);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      if (mode === "login") {
        const loginRes = await supabaseLogin(email.trim(), password);

        // Best-effort profile persistence after login:
        // 1) pending profile from prior signup attempt, else
        // 2) user metadata saved during signup
        let profilePayload = popPendingProfile(email.trim());
        if (!profilePayload) {
          const meta: any = loginRes?.user?.user_metadata ?? {};
          const first = String(meta.first_name ?? meta.firstName ?? "").trim();
          const last = String(meta.last_name ?? meta.lastName ?? "").trim();
          const assocRaw = String(meta.association ?? "").trim();
          const assoc = assocRaw.length ? assocRaw : null;
          if (first && last) {
            profilePayload = { first_name: first, last_name: last, association: assoc };
          }
        }

        if (profilePayload) {
          try {
            await requestAccessProfile(profilePayload);
          } catch {
            // Do not block login if profile upsert fails transiently.
          }
        }
        window.dispatchEvent(new Event("admin-auth-changed"));
        setResolvedOpen(false);
        if (redirectToAdminOnLogin) {
          router.push("/admin");
        }
        return;
      }

      if (mode === "signup") {
        if (!firstName.trim() || !lastName.trim()) {
          setError("First name and last name are required.");
          setIsLoading(false);
          return;
        }
      }

      const profilePayload = {
        first_name: firstName,
        last_name: lastName,
        association,
      };
      stashPendingProfile(email.trim(), profilePayload);

      // signup
      await supabaseSignup(email.trim(), password, profilePayload);

      // try immediate sign-in so request-access can persist profile fields
      try {
        await supabaseLogin(email.trim(), password);
      } catch (signInErr: any) {
        setError(
          "Account created. Please verify your email first, then sign in once to finish your access request profile."
        );
        setIsLoading(false);
        return;
      }

      await requestAccessProfile(profilePayload);
      popPendingProfile(email.trim());

      toast.success("Request submitted", {
        description: "Your account was created. An admin must approve access before you can use admin tools.",
      });
      window.dispatchEvent(new Event("admin-auth-changed"));

      // reset UI
      setMode("login");
      setPassword("");
      setEmail("");
      setFirstName("");
      setLastName("");
      setAssociation("");
      setResolvedOpen(false);
      if (redirectToAdminOnLogin) {
        router.push("/admin");
      }

      // optional: show toast instead of closing modal
      // but simplest: close and let UI show "not authorized" if they try.
    } catch (err: any) {
      setError(err?.message ?? (mode === "login" ? "Login failed" : "Signup failed"));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={resolvedOpen} onOpenChange={setResolvedOpen}>
      {showTrigger ? (
        <DialogTrigger asChild>
          {variant === "mobile" ? (
            <Button variant="outline" className="gap-2 justify-start bg-transparent w-full">
              <LogIn className="h-4 w-4" />
              Admin Login
            </Button>
          ) : (
            <Button variant="outline" className="gap-2 bg-transparent">
              <LogIn className="h-4 w-4" />
              Admin Login
            </Button>
          )}
        </DialogTrigger>
      ) : null}

      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <LogIn className="h-4 w-4 text-primary-foreground" />
            </div>
            {mode === "login" ? "Admin Login" : "Request Admin Access"}
          </DialogTitle>
          <DialogDescription>
            {mode === "login"
              ? "Sign in with email + password."
              : "Create an account to request admin access. An existing admin must approve you."}
          </DialogDescription>
        </DialogHeader>
        <div className="flex gap-2 mt-3">
          <Button
            type="button"
            variant={mode === "login" ? "default" : "outline"}
            className="flex-1"
            onClick={() => { setMode("login"); setError(""); }}
          >
            Sign In
          </Button>
          <Button
            type="button"
            variant={mode === "signup" ? "default" : "outline"}
            className="flex-1"
            onClick={() => { setMode("signup"); setError(""); }}
          >
            Request Access
          </Button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 mt-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              placeholder="admin@domain.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="bg-secondary"
            />
          </div>
          {mode === "signup" && (
            <>
              <div className="space-y-2">
                <Label htmlFor="first">First name</Label>
                <Input
                  id="first"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  required
                  className="bg-secondary"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="last">Last name</Label>
                <Input
                  id="last"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  required
                  className="bg-secondary"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="assoc">Association</Label>
                <Input
                  id="assoc"
                  value={association}
                  onChange={(e) => setAssociation(e.target.value)}
                  className="bg-secondary"
                />
              </div>
            </>
          )}

          <div className="space-y-2">
            <Label htmlFor="pw">Password</Label>
            <Input
              id="pw"
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="bg-secondary"
            />
          </div>

          {error && <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-md">{error}</div>}

          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                {mode === "login" ? "Signing in..." : "Creating account..."}
              </>
            ) : (
              <>
                <LogIn className="h-4 w-4 mr-2" />
                {mode === "login" ? "Sign In" : "Request Access"}
              </>
            )}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
