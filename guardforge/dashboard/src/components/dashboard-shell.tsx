"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  Shield,
  LayoutDashboard,
  ScanSearch,
  ShieldCheck,
  ScrollText,
  Lock,
  AlertTriangle,
  Play,
  BarChart3,
  Globe,
  Tag,
  Webhook,
} from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { LanguageSwitcher } from "@/components/language-switcher";

const NEON_GREEN = "#0afe7e";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8004";

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [isOnline, setIsOnline] = useState(false);
  const [clock, setClock] = useState("");
  const t = useTranslations();
  const tShell = useTranslations("shell");
  const tNav = useTranslations("nav");
  const tBrand = useTranslations("brand");

  const NAV_ITEMS = [
    { icon: LayoutDashboard, label: tNav("dashboard"), href: "/" },
    { icon: ScanSearch, label: tNav("scanner"), href: "/scanner" },
    { icon: ShieldCheck, label: tNav("policies"), href: "/policies" },
    { icon: ScrollText, label: tNav("audit"), href: "/audit" },
    { icon: Lock, label: tNav("vault"), href: "/vault" },
    { icon: Play, label: tNav("playground"), href: "/playground" },
    { icon: BarChart3, label: tNav("reports"), href: "/reports" },
    { icon: Globe, label: tNav("compliance"), href: "/compliance" },
    { icon: Tag, label: tNav("entities"), href: "/entities" },
    { icon: Webhook, label: tNav("webhooks"), href: "/webhooks" },
  ] as const;

  // Suppress unused warning
  void t;

  // Clock
  useEffect(() => {
    const tick = () =>
      setClock(
        new Date().toLocaleTimeString("en-GB", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })
      );
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  // Health check
  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (!res.ok) throw new Error("offline");
      await res.json();
      setIsOnline(true);
    } catch {
      setIsOnline(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const id = setInterval(checkHealth, 30000);
    return () => clearInterval(id);
  }, [checkHealth]);

  // Derive active label from pathname
  const activeLabel =
    NAV_ITEMS.find((item) =>
      item.href === "/" ? pathname === "/" : pathname.startsWith(item.href)
    )?.label ?? tNav("dashboard");

  return (
    <div className="flex h-screen overflow-hidden">
      {/* SIDEBAR */}
      <aside className="w-[200px] shrink-0 border-r border-border bg-card/80 dark:bg-[#070a14]/90 backdrop-blur-sm flex flex-col">
        {/* Logo */}
        <div className="h-16 flex items-center gap-2.5 px-5 border-b border-border">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center">
            <Shield className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-sm tracking-tight">{tBrand("name")}</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 px-3 space-y-1">
          {NAV_ITEMS.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 no-underline ${
                  isActive
                    ? "bg-amber-500/10 text-amber-500 dark:bg-amber-500/15 dark:text-amber-400"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                }`}
              >
                <item.icon className="w-[18px] h-[18px] shrink-0" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Bottom user */}
        <div className="p-4 border-t border-border">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-amber-400 to-orange-600 flex items-center justify-center text-white text-xs font-bold">
              A
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium truncate">{tBrand("user")}</p>
              <p className="text-[10px] text-muted-foreground">{tBrand("role")}</p>
            </div>
          </div>
        </div>
      </aside>

      {/* MAIN AREA */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header */}
        <header className="h-16 shrink-0 border-b border-border bg-card/50 dark:bg-[#0b0e1a]/80 backdrop-blur-sm flex items-center justify-between px-6">
          <div className="flex items-center gap-4">
            <h1 className="text-lg font-bold tracking-tight">{activeLabel}</h1>
            {!isOnline && (
              <span className="text-[11px] px-2.5 py-1 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/20 font-medium flex items-center gap-1.5">
                <AlertTriangle className="w-3 h-3" />
                {tShell("backendOffline")}
              </span>
            )}
          </div>
          <div className="flex items-center gap-4">
            {/* LIVE badge */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-card border border-border">
              <span
                className={`w-2 h-2 rounded-full ${
                  isOnline ? "bg-emerald-400 neon-pulse" : "bg-muted-foreground/40"
                }`}
                style={
                  isOnline
                    ? ({ "--pulse-color": NEON_GREEN } as React.CSSProperties)
                    : undefined
                }
              />
              <span
                className={`text-xs font-semibold ${
                  isOnline ? "text-emerald-400" : "text-muted-foreground"
                }`}
              >
                {isOnline ? tShell("live") : tShell("offline")}
              </span>
            </div>
            {/* Clock */}
            <span className="text-sm font-mono text-muted-foreground tabular-nums">
              {clock}
            </span>
            {/* Language switcher */}
            <LanguageSwitcher />
            {/* Theme toggle */}
            <ThemeToggle />
          </div>
        </header>

        {/* Scrollable content */}
        <main className="flex-1 overflow-y-auto scrollbar-thin p-5">
          <div className="space-y-5 max-w-[1400px] mx-auto">{children}</div>
        </main>
      </div>
    </div>
  );
}
