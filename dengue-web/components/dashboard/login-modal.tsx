// components/dashboard/login-modal.tsx
"use client";

import type React from "react";
import { useState } from "react";
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
import { supabaseLogin, supabaseSignup } from "@/lib/adminApi";
import { toast } from "sonner";
import { set } from "date-fns";
interface LoginModalProps {
  variant?: "default" | "mobile";
}

export function LoginModal({ variant = "default" }: LoginModalProps) {
  const [open, setOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const [mode, setMode] = useState<"login" | "signup">("login");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      if (mode === "login") {
        await supabaseLogin(email.trim(), password);
        window.dispatchEvent(new Event("admin-auth-changed"));
        setOpen(false);
        return;
      }

      // signup / request access
      await supabaseSignup(email.trim(), password);

      // show confirmation
      toast.success("Request submitted", {
        description:
          "Your account was created. An admin must approve access before you can use admin tools.",
      });

      // reset UI
      setError("");
      setMode("login");
      setPassword("");
      setEmail("");
      setOpen(false);

      // optional: show toast instead of closing modal
      // but simplest: close and let UI show "not authorized" if they try.
    } catch (err: any) {
      setError(err?.message ?? (mode === "login" ? "Login failed" : "Signup failed"));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
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
              ? "Sign in with Supabase Auth (email + password)."
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