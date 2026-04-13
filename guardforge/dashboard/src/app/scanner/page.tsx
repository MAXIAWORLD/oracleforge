"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { useTranslations } from "next-intl";
import {
  ScanSearch,
  ShieldCheck,
  AlertTriangle,
  Eye,
  EyeOff,
  Activity,
  FileWarning,
  Fingerprint,
  Copy,
  Check,
} from "lucide-react";
import { DashboardShell } from "@/components/dashboard-shell";
import { api, type ScanResponse, type ScanEntity } from "@/lib/api";

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
  description?: string;
}

const PII_COLORS: Record<string, string> = {
  EMAIL: NEON.cyan,
  PHONE: NEON.violet,
  SSN: NEON.pink,
  CREDIT_CARD: NEON.amber,
  NAME: NEON.green,
  PERSON_NAME: NEON.green,
  ADDRESS: NEON.blue,
  IP_ADDRESS: "#ff6b6b",
  DATE_OF_BIRTH: "#4ecdc4",
  PASSPORT: "#ffe66d",
  IBAN: "#f472b6",
  SIRET_FR: NEON.amber,
  DEFAULT: NEON.amber,
};

function getPiiColor(piiType: string): string {
  return PII_COLORS[piiType.toUpperCase()] ?? PII_COLORS.DEFAULT;
}

const RISK_CONFIG: Record<string, { color: string; bg: string; label: string }> = {
  critical: { color: NEON.pink, bg: `${NEON.pink}18`, label: "CRITICAL" },
  high: { color: "#f97316", bg: "#f9731618", label: "HIGH" },
  medium: { color: NEON.cyan, bg: `${NEON.cyan}18`, label: "MEDIUM" },
  low: { color: NEON.green, bg: `${NEON.green}18`, label: "LOW" },
  none: { color: NEON.green, bg: `${NEON.green}18`, label: "NONE" },
};

function getRiskConfig(level: string) {
  return RISK_CONFIG[level.toLowerCase()] ?? RISK_CONFIG.medium;
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

const STRATEGIES = ["redact", "mask", "hash"] as const;

export default function ScannerPage() {
  const t = useTranslations("scanner");
  const tRisk = useTranslations("risk");

  const [isOnline, setIsOnline] = useState(false);
  const [scanText, setScanText] = useState("");
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResponse | null>(null);
  const [scanError, setScanError] = useState("");
  const [strategy, setStrategy] = useState<string>("redact");
  const [selectedPolicy, setSelectedPolicy] = useState<string>("");
  const [dryRun, setDryRun] = useState(false);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [copied, setCopied] = useState(false);

  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      setIsOnline(res.ok);
    } catch {
      setIsOnline(false);
    }
  }, []);

  const fetchPolicies = useCallback(async () => {
    try {
      const data = await api.policies();
      setPolicies(data.policies || []);
    } catch {
      // Backend offline
    }
  }, []);

  useEffect(() => {
    checkHealth();
    fetchPolicies();
  }, [checkHealth, fetchPolicies]);

  // isOnline used for conditional rendering
  void isOnline;

  const handleScan = async () => {
    if (!scanText.trim()) return;
    setScanning(true);
    setScanError("");
    setScanResult(null);
    try {
      const data = await api.scan(scanText, selectedPolicy || undefined, dryRun, strategy);
      setScanResult(data);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Scan failed";
      setScanError(message);
    } finally {
      setScanning(false);
    }
  };

  const handleCopyAnonymized = async () => {
    if (!scanResult?.anonymized_text) return;
    try {
      await navigator.clipboard.writeText(scanResult.anonymized_text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard not available
    }
  };

  const riskDistributionTotal = scanResult
    ? Object.values(scanResult.risk_distribution).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <DashboardShell>
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="space-y-5 max-w-[1200px] mx-auto"
      >
        {/* Input card */}
        <motion.div
          variants={itemVariants}
          className="glass-card neon-card p-6"
          style={{ "--glow": NEON.amber } as React.CSSProperties}
        >
          <div className="flex items-center gap-2 mb-4">
            <Eye className="w-5 h-5 text-amber-400" />
            <h2 className="text-sm font-semibold">{t("title")}</h2>
            <span className="ml-auto text-[10px] text-muted-foreground font-mono">
              POST /api/scan
            </span>
          </div>

          <textarea
            className="w-full h-48 rounded-xl border border-border bg-background/50 dark:bg-[#0d1020]/60 px-4 py-3 text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-amber-500/40 transition-all placeholder:text-muted-foreground/50"
            placeholder={t("placeholder")}
            value={scanText}
            onChange={(e) => setScanText(e.target.value)}
          />

          {/* Controls row */}
          <div className="flex flex-wrap items-center gap-4 mt-4">
            {/* Strategy */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground font-medium">{t("strategy")}</span>
              <div className="flex gap-1">
                {STRATEGIES.map((s) => (
                  <button
                    key={s}
                    onClick={() => setStrategy(s)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      strategy === s
                        ? "bg-amber-500/15 text-amber-400 border border-amber-500/30"
                        : "bg-card border border-border text-muted-foreground hover:text-foreground hover:bg-accent"
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {/* Policy selector */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground font-medium">{t("policy")}</span>
              <select
                value={selectedPolicy}
                onChange={(e) => setSelectedPolicy(e.target.value)}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-card border border-border text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/40"
              >
                <option value="">{t("policyDefault")}</option>
                {policies.map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Dry run toggle */}
            <button
              onClick={() => setDryRun(!dryRun)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                dryRun
                  ? "bg-violet-500/15 text-violet-400 border border-violet-500/30"
                  : "bg-card border border-border text-muted-foreground hover:text-foreground hover:bg-accent"
              }`}
            >
              <EyeOff className="w-3.5 h-3.5" />
              {dryRun ? t("dryRunOn") : t("dryRunOff")}
            </button>

            <div className="flex-1" />

            {/* Scan button */}
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleScan}
              disabled={scanning || !scanText.trim()}
              className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 text-white text-sm font-semibold transition-all disabled:opacity-40 disabled:cursor-not-allowed hover:shadow-[0_0_20px_rgba(245,158,11,0.3)]"
            >
              {scanning ? (
                <span className="flex items-center gap-2">
                  <Activity className="w-4 h-4 animate-spin" />
                  {t("scanning")}
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <ScanSearch className="w-4 h-4" />
                  {dryRun ? t("dryRunScan") : t("scanAnonymize")}
                </span>
              )}
            </motion.button>
          </div>
        </motion.div>

        {/* Error */}
        {scanError && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-5"
            style={{ "--glow": NEON.pink } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 text-red-400">
              <AlertTriangle className="w-5 h-5" />
              <span className="text-sm font-semibold">{t("scanError")}</span>
            </div>
            <p className="text-sm text-red-300 mt-2">{scanError}</p>
          </motion.div>
        )}

        {/* Results */}
        {scanResult && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-6"
            style={{
              "--glow": scanResult.pii_count > 0 ? getRiskConfig(scanResult.overall_risk).color : NEON.green,
            } as React.CSSProperties}
          >
            {/* Header: PII count + overall risk badge */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <FileWarning
                  className={`w-5 h-5 ${scanResult.pii_count > 0 ? "text-pink-400" : "text-emerald-400"}`}
                />
                <h2 className="text-sm font-semibold">{t("scanResults")}</h2>
                {scanResult.dry_run && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-violet-500/15 text-violet-400 border border-violet-500/30">
                    {t("dryRunBadge")}
                  </span>
                )}
                {/* Overall risk badge */}
                <span
                  className="px-3 py-1 rounded-full text-xs font-bold border tracking-wider"
                  style={{
                    color: getRiskConfig(scanResult.overall_risk).color,
                    borderColor: `${getRiskConfig(scanResult.overall_risk).color}40`,
                    backgroundColor: getRiskConfig(scanResult.overall_risk).bg,
                  }}
                >
                  {tRisk("overall_label")}: {tRisk(scanResult.overall_risk as Parameters<typeof tRisk>[0])}
                </span>
              </div>
              <div className="text-right">
                <span
                  className="neon-value text-3xl font-bold tabular-nums"
                  style={{
                    "--glow": scanResult.pii_count > 0 ? NEON.pink : NEON.green,
                  } as React.CSSProperties}
                >
                  {scanResult.pii_count}
                </span>
                <p className="text-xs text-muted-foreground mt-0.5">{t("piiFound")}</p>
              </div>
            </div>

            {/* Risk distribution bar */}
            {scanResult.pii_count > 0 && riskDistributionTotal > 0 && (
              <div className="mb-5">
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold mb-2">
                  {tRisk("distribution_label")}
                </p>
                <div className="flex gap-3 flex-wrap">
                  {(["critical", "high", "medium", "low"] as const).map((level) => {
                    const count = scanResult.risk_distribution[level] ?? 0;
                    if (count === 0) return null;
                    const cfg = getRiskConfig(level);
                    return (
                      <div key={level} className="flex items-center gap-1.5">
                        <span
                          className="inline-flex items-center justify-center min-w-[22px] h-[22px] rounded-md text-[10px] font-bold px-1.5"
                          style={{ color: cfg.color, backgroundColor: cfg.bg, border: `1px solid ${cfg.color}40` }}
                        >
                          {count}
                        </span>
                        <span className="text-[10px] text-muted-foreground font-medium uppercase tracking-wide">
                          {tRisk(level as Parameters<typeof tRisk>[0])}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Stats row */}
            <div className="grid grid-cols-3 gap-4 mb-5">
              <div className="rounded-xl border border-border/50 bg-background/30 dark:bg-[#0d1020]/40 p-3">
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold mb-1">
                  {t("originalLength")}
                </p>
                <p className="text-lg font-bold tabular-nums">{scanResult.original_length}</p>
              </div>
              <div className="rounded-xl border border-border/50 bg-background/30 dark:bg-[#0d1020]/40 p-3">
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold mb-1">
                  {t("piiTypes")}
                </p>
                <p className="text-lg font-bold tabular-nums">{scanResult.pii_types.length}</p>
              </div>
              <div className="rounded-xl border border-border/50 bg-background/30 dark:bg-[#0d1020]/40 p-3">
                <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold mb-1">
                  {t("policyAction")}
                </p>
                <p
                  className="text-lg font-bold"
                  style={{
                    color:
                      scanResult.policy_decision.action === "block"
                        ? NEON.pink
                        : scanResult.policy_decision.action === "allow"
                          ? NEON.green
                          : NEON.amber,
                  }}
                >
                  {scanResult.policy_decision.action}
                </p>
              </div>
            </div>

            {/* PII type badges */}
            {scanResult.pii_types.length > 0 && (
              <div className="mb-5">
                <p className="text-xs text-muted-foreground font-semibold mb-2 uppercase tracking-wider">
                  {t("detectedPiiTypes")}
                </p>
                <div className="flex flex-wrap gap-2">
                  {scanResult.pii_types.map((piiType) => (
                    <span
                      key={piiType}
                      className="px-3 py-1.5 rounded-full text-xs font-semibold border"
                      style={{
                        color: getPiiColor(piiType),
                        borderColor: `${getPiiColor(piiType)}40`,
                        backgroundColor: `${getPiiColor(piiType)}15`,
                      }}
                    >
                      {piiType}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Entities detail with risk badges */}
            {scanResult.entities && scanResult.entities.length > 0 && (
              <div className="mb-5">
                <p className="text-xs text-muted-foreground font-semibold mb-2 uppercase tracking-wider">
                  {t("detectedEntities")}
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border/50">
                        <th className="text-left py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                          {t("type")}
                        </th>
                        <th className="text-left py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                          {t("riskLevel")}
                        </th>
                        <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                          {t("position")}
                        </th>
                        <th className="text-right py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                          {t("confidence")}
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/30">
                      {scanResult.entities.map((entity: ScanEntity, i: number) => {
                        const riskCfg = getRiskConfig(entity.risk_level);
                        return (
                          <motion.tr
                            key={`${entity.type}-${entity.start}-${i}`}
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: i * 0.03 }}
                            className="hover:bg-accent/30 transition-colors"
                          >
                            <td className="py-2.5 px-3">
                              <div className="flex items-center gap-1.5">
                                <Fingerprint className="w-3.5 h-3.5 shrink-0" style={{ color: getPiiColor(entity.type) }} />
                                <span
                                  className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold border"
                                  style={{
                                    color: getPiiColor(entity.type),
                                    borderColor: `${getPiiColor(entity.type)}40`,
                                    backgroundColor: `${getPiiColor(entity.type)}15`,
                                  }}
                                >
                                  {entity.type}
                                </span>
                              </div>
                            </td>
                            <td className="py-2.5 px-3">
                              <span
                                className="px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-wider"
                                style={{
                                  color: riskCfg.color,
                                  borderColor: `${riskCfg.color}40`,
                                  backgroundColor: riskCfg.bg,
                                }}
                              >
                                {tRisk(entity.risk_level as Parameters<typeof tRisk>[0])}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 text-center font-mono text-xs text-muted-foreground">
                              {entity.start}:{entity.end}
                            </td>
                            <td className="py-2.5 px-3 text-right">
                              <span
                                className="font-mono text-xs font-semibold"
                                style={{
                                  color:
                                    entity.confidence >= 0.9
                                      ? NEON.green
                                      : entity.confidence >= 0.7
                                        ? NEON.amber
                                        : NEON.pink,
                                }}
                              >
                                {(entity.confidence * 100).toFixed(0)}%
                              </span>
                            </td>
                          </motion.tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Anonymized text */}
            {scanResult.anonymized_text && (
              <div className="mb-5">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">
                    {t("anonymizedOutput")}
                  </p>
                  <button
                    onClick={handleCopyAnonymized}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-card border border-border text-muted-foreground hover:text-foreground hover:bg-accent transition-all"
                  >
                    {copied ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                        {t("copied")}
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" />
                        {t("copy")}
                      </>
                    )}
                  </button>
                </div>
                <div className="rounded-xl border border-border bg-background/50 dark:bg-[#0d1020]/60 p-4 font-mono text-sm leading-relaxed whitespace-pre-wrap">
                  {scanResult.anonymized_text}
                </div>
              </div>
            )}

            {/* Policy decision */}
            {scanResult.policy_decision && (
              <div className="flex items-center gap-4 text-xs text-muted-foreground pt-4 border-t border-border/50 flex-wrap">
                <span className="flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
                  {t("policyLabel")}{" "}
                  <span className="text-foreground font-medium">
                    {scanResult.policy_decision.policy}
                  </span>
                </span>
                <span className="text-border">|</span>
                <span>
                  {t("actionLabel")}{" "}
                  <span
                    className="font-semibold"
                    style={{
                      color:
                        scanResult.policy_decision.action === "block"
                          ? NEON.pink
                          : scanResult.policy_decision.action === "allow"
                            ? NEON.green
                            : NEON.amber,
                    }}
                  >
                    {scanResult.policy_decision.action}
                  </span>
                </span>
                <span className="text-border">|</span>
                <span>{scanResult.policy_decision.reason}</span>
                <span className="text-border">|</span>
                <span>
                  {t("allowedLabel")}{" "}
                  <span
                    className="font-semibold"
                    style={{ color: scanResult.policy_decision.allowed ? NEON.green : NEON.pink }}
                  >
                    {scanResult.policy_decision.allowed ? t("yes") : t("no")}
                  </span>
                </span>
              </div>
            )}
          </motion.div>
        )}
      </motion.div>
    </DashboardShell>
  );
}
