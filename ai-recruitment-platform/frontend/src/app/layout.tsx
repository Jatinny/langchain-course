import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { Sidebar } from "@/components/dashboard/Sidebar";
import { TopNav } from "@/components/dashboard/TopNav";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "RecruitAI - AI-Powered Recruitment Platform",
    template: "%s | RecruitAI",
  },
  description:
    "AI-powered recruitment business development tool for sourcing employers, managing outreach, matching candidates, and tracking commissions.",
  keywords: [
    "recruitment",
    "AI",
    "sourcing",
    "talent acquisition",
    "outreach",
    "staffing",
    "hiring",
  ],
  authors: [{ name: "RecruitAI Team" }],
  robots: "noindex, nofollow",
  icons: {
    icon: "/favicon.ico",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning className={inter.variable}>
      <body className="min-h-screen bg-background font-sans antialiased">
        <Providers>
          <div className="flex h-screen overflow-hidden">
            <Sidebar />
            <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
              <TopNav />
              <main className="flex-1 overflow-y-auto bg-muted/30 dark:bg-background">
                <div className="container-fluid p-6 max-w-screen-2xl mx-auto">
                  {children}
                </div>
              </main>
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
