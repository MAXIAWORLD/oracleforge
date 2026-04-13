"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { useTranslations } from "next-intl";
import {
  ScrollText,
  Activity,
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
} from "lucide-react";
import { DashboardShell } from "@/components/dashboard-shell";

const NEON = {
  cyan: "#00e5ff",
  violet: "#b44aff",
  pink: "#ff2d87",
  green: "#0afe7e",
  amber: "#ffb800",
  blue: "#3b82f6",
} as const;

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8004";

interface AuditEntry {
  input_hash: string;
  pii_count: number;
  action: string;
  ts?: number;
  timestamp?: string;
  pii_types?: string[];
  policy?: string;
  dry_run?: boolean;
}

interface AuditResponse {
  entries: AuditEntry[];
  total: number;
}

const PII_COLORS: Record<string, string> = {
  EMAIL: NEON.cyan,
  PHONE: NEON.violet,
  SSN: NEON.pink,
  CREDIT_CARD: NEON.amber,
  NAME: NEON.green,
  ADDRESS: NEON.blue,
  IP_ADDRESS: "#ff6b6b",
  DATE_OF_BIRTH: "#4ecdc4",
  PASSPORT: "#ffe66d",
  DEFAULT: NEON.amber,
};

function getPiiColor(piiType: string): string {
  return PII_COLORS[piiType.toUpperCase()] ?? PII_COLORS.DEFAULT;
}

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.08 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: {
    opacity: 1,
    y: 0,
    transition: { type: "spring" as const, stiffness: 300, damping: 24 },
  },
};

const PAGE_SIZE = 25;

export default function AuditPage() {
  const t = useTranslations("audit");

  const [isOnline, setIsOnline] = useState(false);
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(0);

  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      setIsOnline(res.ok);
    } catch {
      setIsOnline(false);
    }
  }, []);

  const fetchAudit = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/audit?limit=500`, {
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": process.env.NEXT_PUBLIC_API_KEY || "",
        },
      });
      if (!res.ok) {
        throw new Error(`Failed to fetch audit log: ${res.statusText}`);
      }
      const data: AuditResponse = await res.json();
      setEntries(data.entries || []);
      setTotal(data.total || 0);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Failed to load audit log";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    fetchAudit();
  }, [checkHealth, fetchAudit]);

  const totalPages = Math.max(1, Math.ceil(entries.length / PAGE_SIZE));
  const paginatedEntries = entries.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  function formatTimestamp(entry: AuditEntry): string {
    if (entry.timestamp) {
      return new Date(entry.timestamp).toLocaleString("en-GB", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    }
    if (entry.ts) {
      return new Date(entry.ts * 1000).toLocaleString("en-GB", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    }
    return "\u2014";
  }

  return (
    <DashboardShell>
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="space-y-5 max-w-[1400px] mx-auto"
      >
        {/* Stats bar */}
        <motion.div variants={itemVariants} className="grid grid-cols-4 gap-4">
          {[
            {
              label: t("totalEntries"),
              value: total > 0 ? `${total}` : "\u2014",
              color: NEON.cyan,
            },
            {
              label: t("piiDetected"),
              value: entries.length > 0
                ? `${entries.filter((e) => e.pii_count > 0).length}`
                : "\u2014",
              color: NEON.pink,
            },
            {
              label: t("blocked"),
              value: entries.length > 0
                ? `${entries.filter((e) => e.action === "block").length}`
                : "\u2014",
              color: NEON.pink,
            },
            {
              label: t("allowed"),
              value: entries.length > 0
                ? `${entries.filter((e) => e.action === "allow").length}`
                : "\u2014",
              color: NEON.green,
            },
          ].map((stat) => (
            <motion.div
              key={stat.label}
              whileHover={{ y: -4, boxShadow: `0 0 24px ${stat.color}25` }}
              className="glass-card neon-card p-4 flex flex-col"
              style={{ "--glow": stat.color } as React.CSSProperties}
            >
              <span className="text-xs font-medium text-muted-foreground">{stat.label}</span>
              <p
                className="text-2xl font-bold mt-2 neon-value tabular-nums"
                style={{ "--glow": stat.color } as React.CSSProperties}
              >
                {stat.value}
              </p>
            </motion.div>
          ))}
        </motion.div>

        {/* Error */}
        {error && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-5"
            style={{ "--glow": NEON.pink } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 text-red-400">
              <AlertTriangle className="w-5 h-5" />
              <span className="text-sm font-semibold">{t("error")}</span>
            </div>
            <p className="text-sm text-red-300 mt-2">{error}</p>
          </motion.div>
        )}

        {/* Loading */}
        {loading && (
          <motion.div variants={itemVariants} className="flex items-center justify-center py-16">
            <Activity className="w-6 h-6 text-muted-foreground animate-spin" />
          </motion.div>
        )}

        {/* Empty state */}
        {!loading && !error && entries.length === 0 && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-12"
            style={{ "--glow": NEON.cyan } as React.CSSProperties}
          >
            <div className="text-center">
              <ScrollText className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">
                {isOnline ? t("noAuditEntries") : t("backendOffline")}
              </p>
              <p className="text-xs text-muted-foreground/60 mt-1">
                {t("scanToGenerate")}
              </p>
            </div>
          </motion.div>
        )}

        {/* Audit table */}
        {!loading && entries.length > 0 && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-5"
            style={{ "--glow": NEON.cyan } as React.CSSProperties}
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <ScrollText className="w-5 h-5 text-cyan-400" />
                <h2 className="text-sm font-semibold">{t("scanHistory")}</h2>
                <span className="text-[10px] text-muted-foreground font-mono ml-2">
                  GET /api/audit?limit=500
                </span>
              </div>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => fetchAudit()}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-card border border-border text-muted-foreground hover:text-foreground hover:bg-accent transition-all"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                {t("refresh")}
              </motion.button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/50">
                    <th className="text-left py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("timestamp")}
                    </th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("inputHash")}
                    </th>
                    <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("piiCount")}
                    </th>
                    <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("action")}
                    </th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("policy")}
                    </th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("piiTypes")}
                    </th>
                    <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("mode")}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/30">
                  {paginatedEntries.map((entry, i) => (
                    <motion.tr
                      key={`${entry.input_hash}-${page}-${i}`}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.02 }}
                      className="hover:bg-accent/30 transition-colors"
                    >
                      <td className="py-2.5 px-3">
                        <span className="text-xs text-muted-foreground font-mono">
                          {formatTimestamp(entry)}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="font-mono text-xs text-muted-foreground">
                          {entry.input_hash
                            ? `${entry.input_hash.slice(0, 16)}...`
                            : "\u2014"}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        <span
                          className="inline-flex items-center justify-center w-7 h-7 rounded-lg text-xs font-bold"
                          style={{
                            color: entry.pii_count > 0 ? NEON.pink : NEON.green,
                            backgroundColor:
                              entry.pii_count > 0 ? `${NEON.pink}15` : `${NEON.green}15`,
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
                      <td className="py-2.5 px-3">
                        <span className="text-xs text-muted-foreground font-medium">
                          {entry.policy || "\u2014"}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <div className="flex flex-wrap gap-1">
                          {entry.pii_types && entry.pii_types.length > 0 ? (
                            entry.pii_types.map((piiType) => (
                              <span
                                key={piiType}
                                className="px-1.5 py-0.5 rounded text-[9px] font-semibold border"
                                style={{
                                  color: getPiiColor(piiType),
                                  borderColor: `${getPiiColor(piiType)}40`,
                                  backgroundColor: `${getPiiColor(piiType)}10`,
                                }}
                              >
                                {piiType}
                              </span>
                            ))
                          ) : (
                            <span className="text-xs text-muted-foreground">{"\u2014"}</span>
                          )}
                        </div>
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        {entry.dry_run ? (
                          <span className="px-2 py-0.5 rounded-full text-[9px] font-semibold bg-violet-500/15 text-violet-400 border border-violet-500/30">
                            DRY
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full text-[9px] font-semibold bg-cyan-500/15 text-cyan-400 border border-cyan-500/30">
                            LIVE
                          </span>
                        )}
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-border/50">
                <span className="text-xs text-muted-foreground">
                  {t("showing", {
                    from: page * PAGE_SIZE + 1,
                    to: Math.min((page + 1) * PAGE_SIZE, entries.length),
                    total: entries.length,
                  })}
                </span>
                <div className="flex items-center gap-2">
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => setPage(Math.max(0, page - 1))}
                    disabled={page === 0}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-card border border-border text-muted-foreground hover:text-foreground hover:bg-accent transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <ChevronLeft className="w-3.5 h-3.5" />
                    {t("prev")}
                  </motion.button>
                  <span className="text-xs text-muted-foreground font-mono tabular-nums">
                    {page + 1} / {totalPages}
                  </span>
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
                    disabled={page >= totalPages - 1}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-card border border-border text-muted-foreground hover:text-foreground hover:bg-accent transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {t("next")}
                    <ChevronRight className="w-3.5 h-3.5" />
                  </motion.button>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </motion.div>
    </DashboardShell>
  );
}
