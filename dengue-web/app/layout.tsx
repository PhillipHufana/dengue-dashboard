import type React from "react"
import type { Metadata } from "next"
import { Analytics } from "@vercel/analytics/next"
import { ThemeProvider } from "@/components/theme-provider"
import "./globals.css"
import QueryProvider from "@/lib/query/provider";
import { Toaster } from "@/components/ui/sonner";

export const metadata: Metadata = {
  title: "Denguard - Dengue Surveillance Dashboard",
  description: "Real-time dengue fever monitoring and outbreak tracking system",
  generator: "v0.app",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="font-sans antialiased" suppressHydrationWarning={true}>
        <ThemeProvider attribute="class" defaultTheme="light" enableSystem disableTransitionOnChange>
        <QueryProvider>
          {children} 
          <Toaster richColors closeButton />
        </QueryProvider>
        </ThemeProvider>
        <Analytics />
      </body>
    </html>
  )
}
