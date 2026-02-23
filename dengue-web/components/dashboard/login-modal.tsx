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
import { adminLogin, getAdminToken, setAdminToken, clearAdminToken } from "@/lib/adminApi";

interface LoginModalProps {
  variant?: "default" | "mobile";
}

export function LoginModal({ variant = "default" }: LoginModalProps) {
  const [open, setOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [token, setToken] = useState(getAdminToken() ?? "");
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      const t = token.trim();
      await adminLogin(t);
      setAdminToken(t);
      window.dispatchEvent(new Event("admin-token-changed"));
      setError("");
      setOpen(false);
    } catch (err: any) {
      clearAdminToken();
      setError(err?.message ?? "Invalid token");
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
            Admin Login
          </DialogTitle>
          <DialogDescription>Enter the admin token to access upload tools and logs.</DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 mt-4">
          <div className="space-y-2">
            <Label htmlFor="token">Admin Token</Label>
            <Input
              id="token"
              type="password"
              placeholder="Paste token here"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              required
              className="bg-secondary"
            />
          </div>

          {error && <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-md">{error}</div>}

          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Signing in...
              </>
            ) : (
              <>
                <LogIn className="h-4 w-4 mr-2" />
                Sign In
              </>
            )}
          </Button>

          <p className="text-xs text-center text-muted-foreground">
            You’ll replace this with Supabase Auth later.
          </p>
        </form>
      </DialogContent>
    </Dialog>
  );
}