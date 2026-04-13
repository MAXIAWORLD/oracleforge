"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { useTranslations } from "next-intl";
import {
  ShieldCheck,
  ScrollText,
  Activity,
  Fingerprint,
  AlertTriangle,
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

interface Policy {
  name: string;
  action: string;
  pii_types?: string[];
  description?: string;
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

function getActionColor(action: string): string {
  switch (action) {
    case "block":
      return NEON.pink;
    case "allow":
      return NEON.green;
    default:
      return NEON.amber;
  }
}

const KNOWN_POLICIES = [
  "strict", "moderate", "permissive",
  "gdpr", "eu_ai_act", "hipaa", "ccpa", "lgpd", "pci_dss",
  "pipeda", "appi", "pdpa_sg", "popia", "dpdp_in", "pipl_cn", "privacy_au",
] as const;

function getPolicyDescription(
  name: string,
  t: (key: string) => string,
): string {
  if ((KNOWN_POLICIES as readonly string[]).includes(name)) {
    return t(`descriptions.${name}`);
  }
  return "";
}

export default function PoliciesPage() {
  const t = useTranslations("policies");

  const [isOnline, setIsOnline] = useState(false);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      setIsOnline(res.ok);
    } catch {
      setIsOnline(false);
    }
  }, []);

  const fetchPolicies = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/policies`, {
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": process.env.NEXT_PUBLIC_API_KEY || "",
        },
      });
      if (!res.ok) {
        throw new Error(`Failed to fetch policies: ${res.statusText}`);
      }
      const data = await res.json();
      setPolicies(data.policies || []);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Failed to load policies";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    fetchPolicies();
  }, [checkHealth, fetchPolicies]);

  return (
    <DashboardShell>
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="space-y-5 max-w-[1200px] mx-auto"
      >
        {/* Header card */}
        <motion.div
          variants={itemVariants}
          className="glass-card neon-card p-5"
          style={{ "--glow": NEON.violet } as React.CSSProperties}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-violet-400" />
              <h2 className="text-sm font-semibold">{t("title")}</h2>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-[10px] text-muted-foreground font-mono">
                GET /api/policies
              </span>
              <span
                className="neon-value text-2xl font-bold tabular-nums"
                style={{ "--glow": NEON.violet } as React.CSSProperties}
              >
                {policies.length}
              </span>
              <span className="text-xs text-muted-foreground">{t("active")}</span>
            </div>
          </div>
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
        {!loading && !error && policies.length === 0 && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-12"
            style={{ "--glow": NEON.violet } as React.CSSProperties}
          >
            <div className="text-center">
              <ShieldCheck className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">
                {isOnline ? t("noPoliciesConfigured") : t("backendOffline")}
              </p>
            </div>
          </motion.div>
        )}

        {/* Policies grid */}
        {!loading && policies.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {policies.map((policy) => {
              const actionColor = getActionColor(policy.action);
              return (
                <motion.div
                  key={policy.name}
                  variants={itemVariants}
                  whileHover={{
                    y: -4,
                    boxShadow: `0 0 24px ${actionColor}25`,
                  }}
                  className="glass-card neon-card p-5"
                  style={{ "--glow": actionColor } as React.CSSProperties}
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2.5">
                      <Fingerprint className="w-5 h-5" style={{ color: actionColor }} />
                      <h3 className="text-sm font-semibold">{policy.name}</h3>
                    </div>
                    <span
                      className="px-3 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wider"
                      style={{
                        color: actionColor,
                        backgroundColor: `${actionColor}15`,
                        borderWidth: "1px",
                        borderColor: `${actionColor}30`,
                      }}
                    >
                      {policy.action}
                    </span>
                  </div>

                  {(() => {
                    const desc = getPolicyDescription(policy.name, t);
                    return desc ? (
                      <p className="text-xs text-muted-foreground leading-relaxed mb-3">
                        {desc}
                      </p>
                    ) : null;
                  })()}

                  {policy.pii_types && policy.pii_types.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {policy.pii_types.map((piiType) => (
                        <span
                          key={piiType}
                          className="px-2 py-0.5 rounded-md text-[10px] font-medium bg-background/50 dark:bg-[#0d1020]/60 border border-border/50 text-muted-foreground"
                        >
                          {piiType}
                        </span>
                      ))}
                    </div>
                  )}
                </motion.div>
              );
            })}
          </div>
        )}

        {/* Policies table */}
        {!loading && policies.length > 0 && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-5"
            style={{ "--glow": NEON.cyan } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 mb-4">
              <ScrollText className="w-5 h-5 text-cyan-400" />
              <h2 className="text-sm font-semibold">{t("fullPoliciesTable")}</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/50">
                    <th className="text-left py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("name")}
                    </th>
                    <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("action")}
                    </th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("description")}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/30">
                  {policies.map((policy, i) => (
                    <motion.tr
                      key={policy.name}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.04 }}
                      className="hover:bg-accent/30 transition-colors"
                    >
                      <td className="py-3 px-3">
                        <div className="flex items-center gap-2">
                          <Fingerprint
                            className="w-4 h-4"
                            style={{ color: getActionColor(policy.action) }}
                          />
                          <span className="font-medium">{policy.name}</span>
                        </div>
                      </td>
                      <td className="py-3 px-3 text-center">
                        <span
                          className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider"
                          style={{
                            color: getActionColor(policy.action),
                            backgroundColor: `${getActionColor(policy.action)}15`,
                            borderWidth: "1px",
                            borderColor: `${getActionColor(policy.action)}30`,
                          }}
                        >
                          {policy.action}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-muted-foreground text-xs">
                        {getPolicyDescription(policy.name, t) || "\u2014"}
                      </td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
            </div>
          </motion.div>
        )}
      </motion.div>
    </DashboardShell>
  );
}
