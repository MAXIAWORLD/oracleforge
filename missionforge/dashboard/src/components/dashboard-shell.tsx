"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  LayoutDashboard,
  Rocket,
  MessageSquare,
  Activity,
  Database,
  Zap,
  AlertTriangle,
} from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { LanguageSwitcher } from "@/components/language-switcher";

// ── Neon colors (shared) ─────────────────────────────────────────
export const NEON = {
  cyan: "#00e5ff",
  violet: "#b44aff",
  pink: "#ff2d87",
  green: "#0afe7e",
  amber: "#ffb800",
  blue: "#3b82f6",
} as const;

// ── API base ─────────────────────────────────────────────────────
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

// ── Nav items (icon + i18n key + href) ───────────────────────────
const NAV_ITEMS = [
  { icon: LayoutDashboard, key: "dashboard", href: "/" },
  { icon: Rocket, key: "missions", href: "/missions" },
  { icon: MessageSquare, key: "chat", href: "/chat" },
  { icon: Activity, key: "observability", href: "/observability" },
  { icon: Database, key: "ragStore", href: "/rag" },
] as const;

// ── Stagger variants (shared) ────────────────────────────────────
export const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08 },
  },
};

export const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: {
    opacity: 1,
    y: 0,
    transition: { type: "spring" as const, stiffness: 300, damping: 24 },
  },
};

// ── DashboardShell ───────────────────────────────────────────────
export function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const tNav = useTranslations("nav");
  const tShell = useTranslations("shell");
  const tBrand = useTranslations("brand");
  const [clock, setClock] = useState("");
  const [isOnline, setIsOnline] = useState(false);

  // Clock
  useEffect(() => {
    const tick = () =>
      setClock(
        new Date().toLocaleTimeString("en-GB", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        }),
      );
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  // Health check polling every 30s
  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      try {
        const res = await fetch(`${API_BASE}/health`, {
          signal: AbortSignal.timeout(5000),
        });
        if (!cancelled) setIsOnline(res.ok);
      } catch {
        if (!cancelled) setIsOnline(false);
      }
    };

    check();
    const id = setInterval(check, 30_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  // Derive active nav item from pathname
  const activeItem = NAV_ITEMS.find((item) =>
    item.href === "/" ? pathname === "/" : pathname.startsWith(item.href),
  );
  const activeLabel = activeItem ? tNav(activeItem.key) : tNav("dashboard");

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── Sidebar ── */}
      <aside className="w-[200px] shrink-0 border-r border-border bg-card/80 dark:bg-[#070a14]/90 backdrop-blur-sm flex flex-col">
        {/* Logo */}
        <div className="h-16 flex items-center gap-2.5 px-5 border-b border-border">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-sm tracking-tight">
            {tBrand("name")}
          </span>
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
                key={item.key}
                href={item.href}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 no-underline ${
                  isActive
                    ? "bg-primary/10 text-primary dark:bg-primary/15 dark:text-blue-400"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                }`}
              >
                <item.icon className="w-[18px] h-[18px] shrink-0" />
                <span>{tNav(item.key)}</span>
              </Link>
            );
          })}
        </nav>

        {/* Bottom */}
        <div className="p-4 border-t border-border">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center text-white text-xs font-bold">
              A
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium truncate">{tBrand("user")}</p>
              <p className="text-[10px] text-muted-foreground">
                {tBrand("role")}
              </p>
            </div>
          </div>
        </div>
      </aside>

      {/* ── Main content ── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header */}
        <header className="h-16 shrink-0 border-b border-border bg-card/50 dark:bg-[#0b0e1a]/80 backdrop-blur-sm flex items-center justify-between px-6">
          <div className="flex items-center gap-4">
            <h1 className="text-lg font-bold tracking-tight">{activeLabel}</h1>
            {!isOnline && (
              <div className="flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/20 font-medium">
                <AlertTriangle className="w-3 h-3" />
                {tShell("backendOffline")}
              </div>
            )}
          </div>
          <div className="flex items-center gap-3">
            {/* LIVE / OFFLINE badge */}
            {isOnline ? (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-card border border-border">
                <span
                  className="w-2 h-2 rounded-full bg-emerald-400 neon-pulse"
                  style={{ "--pulse-color": NEON.green } as React.CSSProperties}
                />
                <span className="text-xs font-semibold text-emerald-400">
                  {tShell("live")}
                </span>
              </div>
            ) : (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-card border border-border">
                <span className="w-2 h-2 rounded-full bg-muted-foreground/40" />
                <span className="text-xs font-semibold text-muted-foreground">
                  {tShell("offline")}
                </span>
              </div>
            )}
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

        {/* Scrollable content area */}
        <main className="flex-1 overflow-y-auto scrollbar-thin p-5">
          {children}
        </main>
      </div>
    </div>
  );
}
