"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { useTranslations } from "next-intl";
import { Globe, ShieldCheck, Activity, AlertTriangle, CheckCircle2, Circle } from "lucide-react";
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

interface PolicyMeta {
  name: string;
  description: string;
  action: string;
  jurisdiction?: string;
  regulation?: string;
}

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.05 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: {
    opacity: 1,
    y: 0,
    transition: { type: "spring" as const, stiffness: 300, damping: 24 },
  },
};

// Map jurisdiction code → flag emoji + region group for visual sorting
const JURISDICTION_META: Record<string, { flag: string; region: string }> = {
  EU: { flag: "🇪🇺", region: "Europe" },
  US: { flag: "🇺🇸", region: "North America" },
  "US-CA": { flag: "🇺🇸", region: "North America" },
  CA: { flag: "🇨🇦", region: "North America" },
  BR: { flag: "🇧🇷", region: "South America" },
  JP: { flag: "🇯🇵", region: "Asia" },
  SG: { flag: "🇸🇬", region: "Asia" },
  IN: { flag: "🇮🇳", region: "Asia" },
  CN: { flag: "🇨🇳", region: "Asia" },
  ZA: { flag: "🇿🇦", region: "Africa" },
  AU: { flag: "🇦🇺", region: "Oceania" },
  Worldwide: { flag: "🌍", region: "Worldwide" },
};

// Tier 1 = full mappings, Tier 2 = stubs (RGPD-baseline)
const TIER_1 = new Set(["gdpr", "eu_ai_act", "hipaa", "ccpa", "lgpd", "pci_dss"]);

const KNOWN_POLICIES = [
  "gdpr", "eu_ai_act", "hipaa", "ccpa", "lgpd", "pci_dss",
  "pipeda", "appi", "pdpa_sg", "popia", "dpdp_in", "pipl_cn", "privacy_au",
] as const;

function getJurisdictionDescription(name: string, t: (key: string) => string): string {
  if ((KNOWN_POLICIES as readonly string[]).includes(name)) {
    return t(`descriptions.${name}`);
  }
  return "";
}

function getActionColor(action: string): string {
  switch (action) {
    case "block":
      return NEON.pink;
    case "anonymize":
      return NEON.amber;
    case "warn":
      return NEON.cyan;
    default:
      return NEON.green;
  }
}

export default function CompliancePage() {
  const t = useTranslations("compliance");
  const tPolicies = useTranslations("policies");

  const [isOnline, setIsOnline] = useState(false);
  const [policies, setPolicies] = useState<PolicyMeta[]>([]);
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

  // Filter: only policies with jurisdiction metadata
  const jurisdictions = policies.filter((p) => p.jurisdiction);

  // Stats
  const tier1Count = jurisdictions.filter((p) => TIER_1.has(p.name)).length;
  const tier2Count = jurisdictions.filter((p) => !TIER_1.has(p.name)).length;

  return (
    <DashboardShell>
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="space-y-5 max-w-[1400px] mx-auto"
      >
        {/* Header */}
        <motion.div
          variants={itemVariants}
          className="glass-card neon-card p-6"
          style={{ "--glow": NEON.cyan } as React.CSSProperties}
        >
          <div className="flex items-center gap-3 mb-2">
            <Globe className="w-6 h-6 text-cyan-400" />
            <h1 className="text-xl font-bold">{t("title")}</h1>
          </div>
          <p className="text-sm text-muted-foreground max-w-3xl">
            {t("subtitle")}
          </p>
        </motion.div>

        {/* Stats */}
        <motion.div variants={itemVariants} className="grid grid-cols-3 gap-4">
          <div
            className="glass-card neon-card p-5"
            style={{ "--glow": NEON.cyan } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 mb-2">
              <Globe className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                {t("total_jurisdictions")}
              </span>
            </div>
            <p
              className="text-3xl font-bold neon-value tabular-nums"
              style={{ "--glow": NEON.cyan } as React.CSSProperties}
            >
              {jurisdictions.length}
            </p>
          </div>
          <div
            className="glass-card neon-card p-5"
            style={{ "--glow": NEON.green } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                {t("tier_1_full")}
              </span>
            </div>
            <p
              className="text-3xl font-bold neon-value tabular-nums"
              style={{ "--glow": NEON.green } as React.CSSProperties}
            >
              {tier1Count}
            </p>
          </div>
          <div
            className="glass-card neon-card p-5"
            style={{ "--glow": NEON.amber } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 mb-2">
              <Circle className="w-4 h-4 text-amber-400" />
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                {t("tier_2_baseline")}
              </span>
            </div>
            <p
              className="text-3xl font-bold neon-value tabular-nums"
              style={{ "--glow": NEON.amber } as React.CSSProperties}
            >
              {tier2Count}
            </p>
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
        {!loading && !error && jurisdictions.length === 0 && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-12"
            style={{ "--glow": NEON.cyan } as React.CSSProperties}
          >
            <div className="text-center">
              <Globe className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">
                {isOnline ? t("no_jurisdictions") : t("backend_offline")}
              </p>
            </div>
          </motion.div>
        )}

        {/* Jurisdiction matrix */}
        {!loading && jurisdictions.length > 0 && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-5"
            style={{ "--glow": NEON.violet } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 mb-4">
              <ShieldCheck className="w-5 h-5 text-violet-400" />
              <h2 className="text-sm font-semibold">{t("matrix_title")}</h2>
              <span className="text-[10px] text-muted-foreground font-mono ml-2">
                GET /api/policies
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/50">
                    <th className="text-left py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("col_status")}
                    </th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("col_region")}
                    </th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("col_regulation")}
                    </th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("col_description")}
                    </th>
                    <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("col_action")}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/30">
                  {jurisdictions.map((policy, i) => {
                    const meta = JURISDICTION_META[policy.jurisdiction || ""] || {
                      flag: "🌐",
                      region: "—",
                    };
                    const isTier1 = TIER_1.has(policy.name);
                    const actionColor = getActionColor(policy.action);
                    const description = getJurisdictionDescription(policy.name, tPolicies);
                    return (
                      <motion.tr
                        key={policy.name}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.03 }}
                        className="hover:bg-accent/30 transition-colors"
                      >
                        <td className="py-3 px-3">
                          {isTier1 ? (
                            <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                              <CheckCircle2 className="w-3 h-3" />
                              {t("badge_full")}
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wider bg-amber-500/10 text-amber-400 border border-amber-500/30">
                              <Circle className="w-3 h-3" />
                              {t("badge_baseline")}
                            </span>
                          )}
                        </td>
                        <td className="py-3 px-3">
                          <div className="flex items-center gap-2">
                            <span className="text-xl">{meta.flag}</span>
                            <div className="flex flex-col">
                              <span className="font-semibold text-foreground">
                                {policy.jurisdiction}
                              </span>
                              <span className="text-[10px] text-muted-foreground">
                                {meta.region}
                              </span>
                            </div>
                          </div>
                        </td>
                        <td className="py-3 px-3">
                          <div className="flex flex-col">
                            <span className="font-semibold text-xs text-foreground uppercase tracking-wider">
                              {policy.name}
                            </span>
                            <span className="text-[10px] text-muted-foreground mt-0.5">
                              {policy.regulation}
                            </span>
                          </div>
                        </td>
                        <td className="py-3 px-3 text-muted-foreground text-xs max-w-md">
                          {description || "—"}
                        </td>
                        <td className="py-3 px-3 text-center">
                          <span
                            className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider"
                            style={{
                              color: actionColor,
                              backgroundColor: `${actionColor}15`,
                              borderWidth: "1px",
                              borderColor: `${actionColor}30`,
                            }}
                          >
                            {policy.action}
                          </span>
                        </td>
                      </motion.tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </motion.div>
        )}

        {/* Legend */}
        {!loading && jurisdictions.length > 0 && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-5"
            style={{ "--glow": NEON.cyan } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle className="w-4 h-4 text-cyan-400" />
              <h3 className="text-xs font-semibold uppercase tracking-wider">
                {t("legend_title")}
              </h3>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs text-muted-foreground">
              <div>
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 mr-1">
                  <CheckCircle2 className="w-2.5 h-2.5" />
                  {t("badge_full")}
                </span>
                {t("legend_full")}
              </div>
              <div>
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30 mr-1">
                  <Circle className="w-2.5 h-2.5" />
                  {t("badge_baseline")}
                </span>
                {t("legend_baseline")}
              </div>
            </div>
          </motion.div>
        )}
      </motion.div>
    </DashboardShell>
  );
}
