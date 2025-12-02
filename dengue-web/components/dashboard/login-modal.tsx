"use client"

import type React from "react"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LogIn, Eye, EyeOff, Loader2 } from "lucide-react"

interface LoginModalProps {
  variant?: "default" | "mobile"
}

export function LoginModal({ variant = "default" }: LoginModalProps) {
  const [open, setOpen] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setIsLoading(true)

    // Simulate login - replace with actual auth logic
    await new Promise((resolve) => setTimeout(resolve, 1500))

    if (email === "admin@dengue.gov" && password === "admin123") {
      setOpen(false)
      // Handle successful login
    } else {
      setError("Invalid credentials. Please try again.")
    }
    setIsLoading(false)
  }

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
          <DialogDescription>
            Sign in to access admin features including data management, report generation, and system settings.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 mt-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              placeholder="admin@dengue.gov"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="bg-secondary"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="bg-secondary pr-10"
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="absolute right-0 top-0 h-full px-3 hover:bg-transparent"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? (
                  <EyeOff className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <Eye className="h-4 w-4 text-muted-foreground" />
                )}
              </Button>
            </div>
          </div>

          {error && <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-md">{error}</div>}

          <div className="flex items-center justify-between">
            <Button type="button" variant="link" className="px-0 text-sm text-muted-foreground">
              Forgot password?
            </Button>
          </div>

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
            Contact your system administrator if you need access.
          </p>
        </form>
      </DialogContent>
    </Dialog>
  )
}
