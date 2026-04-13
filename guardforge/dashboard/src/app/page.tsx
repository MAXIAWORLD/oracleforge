"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { useTranslations } from "next-intl";
import Link from "next/link";
import {
  ShieldCheck,
  ScrollText,
  AlertTriangle,
  Fingerprint,
  Activity,
  Play,
  BarChart3,
  Eye,
} from "lucide-react";
import { DashboardShell } from "@/components/dashboard-shell";
import { api, type ReportSummary } from "@/lib/api";

// -- Neon colors --
const NEON = {
  cyan: "#00e5ff",
  violet: "#b44aff",
  pink: "#ff2d87",
  green: "#0afe7e",
  amber: "#ffb800",
  blue: "#3b82f6",
} as const;

// -- API base --
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8004";

// -- Types --
interface Policy {
  name: string;
  action: string;
  pii_types?: string[];
  description?: string;
}

interface AuditEntry {
  input_hash: string;
  pii_count: number;
  action: string;
  timestamp?: string;
  pii_types?: string[];
}

const RISK_COLORS: Record<string, string> = {
  critical: NEON.pink,
  high: "#f97316",
  medium: NEON.cyan,
  low: NEON.green,
};

// -- Stagger animations --
const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: {
    opacity: 1,
    y: 0,
    transition: { type: "spring" as const, stiffness: 300, damping: 24 },
  },
};

// -- Main Page Component --
export default function GuardForgeDashboard() {
  const t = useTranslations("dashboard");
  const tCommon = useTranslations("common");

  const [isOnline, setIsOnline] = useState(false);

  // Policies state
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [policiesLoading, setPoliciesLoading] = useState(true);

  // Audit state
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [auditLoading, setAuditLoading] = useState(true);

  // Risk distribution (last 7 days)
  const [riskSummary, setRiskSummary] = useState<ReportSummary | null>(null);

  // Health check
  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      setIsOnline(res.ok);
    } catch {
      setIsOnline(false);
    }
  }, []);

  // Fetch policies
  const fetchPolicies = useCallback(async () => {
    setPoliciesLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/policies`, {
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": process.env.NEXT_PUBLIC_API_KEY || "",
        },
      });
      if (res.ok) {
        const data = await res.json();
        setPolicies(data.policies || []);
      }
    } catch {
      // Backend offline
    } finally {
      setPoliciesLoading(false);
    }
  }, []);

  // Fetch audit
  const fetchAudit = useCallback(async () => {
    setAuditLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/audit?limit=20`, {
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": process.env.NEXT_PUBLIC_API_KEY || "",
        },
      });
      if (res.ok) {
        const data = await res.json();
        setAudit(data.entries || []);
      }
    } catch {
      // Backend offline
    } finally {
      setAuditLoading(false);
    }
  }, []);

  // Fetch risk summary for last 7 days
  const fetchRiskSummary = useCallback(async () => {
    try {
      const today = new Date("2026-04-13");
      const from = new Date(today);
      from.setDate(from.getDate() - 7);
      const data = await api.reportSummary(from.toISOString().slice(0, 10), today.toISOString().slice(0, 10));
      setRiskSummary(data);
    } catch {
      // Non-critical, silently ignore
    }
  }, []);

  // Initial load
  useEffect(() => {
    checkHealth();
    fetchPolicies();
    fetchAudit();
    fetchRiskSummary();
  }, [checkHealth, fetchPolicies, fetchAudit, fetchRiskSummary]);

  return (
    <DashboardShell>
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="space-y-5 max-w-[1600px] mx-auto"
      >
        {/* ====== ROW 3: Policies + Audit Log ====== */}
        <div className="grid grid-cols-12 gap-5">
          {/* Policies */}
          <motion.div
            variants={itemVariants}
            className="col-span-5 glass-card neon-card p-5"
            style={{ "--glow": NEON.violet } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 mb-4">
              <ShieldCheck className="w-5 h-5 text-violet-400" />
              <h2 className="text-sm font-semibold">{t("policies")}</h2>
              <span className="ml-auto text-[10px] text-muted-foreground font-mono">
                GET /api/policies
              </span>
            </div>
            {policiesLoading ? (
              <div className="flex items-center justify-center py-8">
                <Activity className="w-5 h-5 text-muted-foreground animate-spin" />
              </div>
            ) : policies.length === 0 ? (
              <div className="text-center py-8">
                <ShieldCheck className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">
                  {isOnline
                    ? t("noPoliciesConfigured")
                    : tCommon("backendOffline")}
                </p>
                <p className="text-xs text-muted-foreground/60 mt-1">
                  &mdash;
                </p>
              </div>
            ) : (
              <div className="space-y-2 max-h-[300px] overflow-y-auto scrollbar-thin">
                {policies.map((policy) => (
                  <motion.div
                    key={policy.name}
                    whileHover={{ x: 4 }}
                    className="flex items-center justify-between px-3 py-2.5 rounded-xl border border-border/50 bg-background/30 dark:bg-[#0d1020]/40 transition-colors hover:border-violet-500/30"
                  >
                    <div className="flex items-center gap-2.5">
                      <Fingerprint className="w-4 h-4 text-violet-400" />
                      <span className="text-sm font-medium">
                        {policy.name}
                      </span>
                    </div>
                    <span
                      className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider"
                      style={{
                        color:
                          policy.action === "block"
                            ? NEON.pink
                            : policy.action === "allow"
                              ? NEON.green
                              : NEON.amber,
                        backgroundColor:
                          policy.action === "block"
                            ? `${NEON.pink}15`
                            : policy.action === "allow"
                              ? `${NEON.green}15`
                              : `${NEON.amber}15`,
                        borderWidth: "1px",
                        borderColor:
                          policy.action === "block"
                            ? `${NEON.pink}30`
                            : policy.action === "allow"
                              ? `${NEON.green}30`
                              : `${NEON.amber}30`,
                      }}
                    >
                      {policy.action}
                    </span>
                  </motion.div>
                ))}
              </div>
            )}
          </motion.div>

          {/* Audit Log */}
          <motion.div
            variants={itemVariants}
            className="col-span-7 glass-card neon-card p-5"
            style={{ "--glow": NEON.cyan } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 mb-4">
              <ScrollText className="w-5 h-5 text-cyan-400" />
              <h2 className="text-sm font-semibold">{t("auditLog")}</h2>
              <span className="ml-auto text-[10px] text-muted-foreground font-mono">
                GET /api/audit?limit=20
              </span>
            </div>
            {auditLoading ? (
              <div className="flex items-center justify-center py-8">
                <Activity className="w-5 h-5 text-muted-foreground animate-spin" />
              </div>
            ) : audit.length === 0 ? (
              <div className="text-center py-8">
                <ScrollText className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">
                  {isOnline ? t("noAuditEntries") : tCommon("backendOffline")}
                </p>
                <p className="text-xs text-muted-foreground/60 mt-1">
                  &mdash;
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border/50">
                      <th className="text-left py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        Hash
                      </th>
                      <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        PII
                      </th>
                      <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        Action
                      </th>
                      <th className="text-right py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        Time
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/30">
                    {audit.map((entry, i) => (
                      <motion.tr
                        key={`${entry.input_hash}-${i}`}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.03 }}
                        className="hover:bg-accent/30 transition-colors"
                      >
                        <td className="py-2.5 px-3">
                          <span className="font-mono text-xs text-muted-foreground">
                            {entry.input_hash
                              ? `${entry.input_hash.slice(0, 12)}...`
                              : "\u2014"}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <span
                            className="inline-flex items-center justify-center w-7 h-7 rounded-lg text-xs font-bold"
                            style={{
                              color:
                                entry.pii_count > 0
                                  ? NEON.pink
                                  : NEON.green,
                              backgroundColor:
                                entry.pii_count > 0
                                  ? `${NEON.pink}15`
                                  : `${NEON.green}15`,
                            }}
                          >
                            {entry.pii_count}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <span
                            className="px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider"
                            style={{
                              color:
                                entry.action === "block"
                                  ? NEON.pink
                                  : entry.action === "allow"
                                    ? NEON.green
                                    : NEON.amber,
                              backgroundColor:
                                entry.action === "block"
                                  ? `${NEON.pink}15`
                                  : entry.action === "allow"
                                    ? `${NEON.green}15`
                                    : `${NEON.amber}15`,
                            }}
                          >
                            {entry.action || "\u2014"}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <span className="text-xs text-muted-foreground font-mono">
                            {entry.timestamp
                              ? new Date(
                                  entry.timestamp
                                ).toLocaleTimeString("en-GB", {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })
                              : "\u2014"}
                          </span>
                        </td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </motion.div>
        </div>

        {/* ====== ROW 4: Quick stats ====== */}
        <div className="grid grid-cols-4 gap-4">
          {[
            {
              icon: Eye,
              label: t("totalScans"),
              value: audit.length > 0 ? `${audit.length}` : "\u2014",
              color: NEON.cyan,
            },
            {
              icon: AlertTriangle,
              label: t("piiDetected"),
              value:
                audit.length > 0
                  ? `${audit.filter((a) => a.pii_count > 0).length}`
                  : "\u2014",
              color: NEON.pink,
            },
            {
              icon: ShieldCheck,
              label: t("policiesActive"),
              value: policies.length > 0 ? `${policies.length}` : "\u2014",
              color: NEON.violet,
            },
            {
              icon: Activity,
              label: t("apiStatus"),
              value: isOnline ? tCommon("online") : tCommon("offline"),
              color: isOnline ? NEON.green : NEON.pink,
            },
          ].map((stat) => (
            <motion.div
              key={stat.label}
              variants={itemVariants}
              whileHover={{
                y: -4,
                boxShadow: `0 0 24px ${stat.color}25`,
              }}
              className="glass-card neon-card p-5 flex flex-col justify-between"
              style={{ "--glow": stat.color } as React.CSSProperties}
            >
              <div className="flex items-center gap-2">
                <stat.icon
                  className="w-4 h-4"
                  style={{ color: stat.color }}
                />
                <span className="text-xs font-medium text-muted-foreground">
                  {stat.label}
                </span>
              </div>
              <p
                className="text-2xl font-bold mt-3 neon-value"
                style={{ "--glow": stat.color } as React.CSSProperties}
              >
                {stat.value}
              </p>
            </motion.div>
          ))}
        </div>

        {/* ====== ROW 5: Risk Distribution (last 7 days) ====== */}
        {riskSummary && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-5"
            style={{ "--glow": NEON.pink } as React.CSSProperties}
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-pink-400" />
                <h2 className="text-sm font-semibold">{t("riskDistribution")}</h2>
                <span className="text-[10px] text-muted-foreground ml-1">({t("last_7_days")})</span>
              </div>
              <Link
                href="/reports"
                className="text-[10px] text-amber-400 hover:text-amber-300 font-medium transition-colors"
              >
                {t("view_full_report")}
              </Link>
            </div>
            <div className="grid grid-cols-4 gap-3">
              {(["critical", "high", "medium", "low"] as const).map((level) => {
                const count = riskSummary.risk_distribution[level] ?? 0;
                const color = RISK_COLORS[level] ?? NEON.cyan;
                return (
                  <div
                    key={level}
                    className="rounded-xl border p-3 flex flex-col gap-1"
                    style={{ borderColor: `${color}30`, backgroundColor: `${color}0a` }}
                  >
                    <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color }}>
                      {level}
                    </span>
                    <span
                      className="text-2xl font-bold tabular-nums neon-value"
                      style={{ "--glow": color } as React.CSSProperties}
                    >
                      {count}
                    </span>
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}

        {/* ====== ROW 6: Quick nav tiles ====== */}
        <div className="grid grid-cols-2 gap-4">
          <motion.div variants={itemVariants}>
            <Link href="/playground" className="block no-underline">
              <motion.div
                whileHover={{ y: -4, boxShadow: `0 0 24px ${NEON.violet}25` }}
                className="glass-card neon-card p-5 flex items-center gap-4 cursor-pointer"
                style={{ "--glow": NEON.violet } as React.CSSProperties}
              >
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                  style={{ backgroundColor: `${NEON.violet}20`, border: `1px solid ${NEON.violet}30` }}
                >
                  <Play className="w-5 h-5" style={{ color: NEON.violet }} />
                </div>
                <div>
                  <p className="text-sm font-semibold">{t("playgroundTile")}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{t("playground_desc")}</p>
                </div>
              </motion.div>
            </Link>
          </motion.div>
          <motion.div variants={itemVariants}>
            <Link href="/reports" className="block no-underline">
              <motion.div
                whileHover={{ y: -4, boxShadow: `0 0 24px ${NEON.cyan}25` }}
                className="glass-card neon-card p-5 flex items-center gap-4 cursor-pointer"
                style={{ "--glow": NEON.cyan } as React.CSSProperties}
              >
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                  style={{ backgroundColor: `${NEON.cyan}20`, border: `1px solid ${NEON.cyan}30` }}
                >
                  <BarChart3 className="w-5 h-5" style={{ color: NEON.cyan }} />
                </div>
                <div>
                  <p className="text-sm font-semibold">{t("reportsTile")}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{t("reports_desc")}</p>
                </div>
              </motion.div>
            </Link>
          </motion.div>
        </div>
      </motion.div>
    </DashboardShell>
  );
}
