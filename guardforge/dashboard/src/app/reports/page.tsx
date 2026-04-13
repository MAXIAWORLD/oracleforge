"use client";

import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import { useTranslations } from "next-intl";
import {
  BarChart3,
  RefreshCw,
  Download,
  FileText,
  AlertTriangle,
  Activity,
  FileSearch,
  TrendingUp,
} from "lucide-react";
import { DashboardShell } from "@/components/dashboard-shell";
import { api, type ReportSummary, type ReportTimeline } from "@/lib/api";

const NEON = {
  cyan: "#00e5ff",
  violet: "#b44aff",
  pink: "#ff2d87",
  green: "#0afe7e",
  amber: "#ffb800",
} as const;

// Default date range: last 30 days from 2026-04-13
function getDefaultDates() {
  const today = new Date("2026-04-13");
  const from = new Date(today);
  from.setDate(from.getDate() - 30);
  return {
    to: today.toISOString().slice(0, 10),
    from: from.toISOString().slice(0, 10),
  };
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

const RISK_COLORS: Record<string, string> = {
  critical: NEON.pink,
  high: "#f97316",
  medium: NEON.cyan,
  low: NEON.green,
  none: "#6b7194",
};

/** Simple horizontal bar */
function HBar({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.max(4, (value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-muted-foreground font-mono w-36 truncate shrink-0">{label}</span>
      <div className="flex-1 h-2 rounded-full bg-border/40 overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="h-full rounded-full glow-bar"
          style={{ backgroundColor: color }}
        />
      </div>
      <span className="text-xs font-bold tabular-nums w-8 text-right" style={{ color }}>{value}</span>
    </div>
  );
}

/** Mini timeline sparkline using SVG */
function TimelineChart({ series, noDataLabel }: { series: { date: string; scans: number; pii: number }[]; noDataLabel: string }) {
  if (series.length === 0) {
    return <p className="text-xs text-muted-foreground text-center py-4">{noDataLabel}</p>;
  }
  const W = 600;
  const H = 80;
  const PAD = 8;
  const maxScans = Math.max(...series.map((s) => s.scans), 1);
  const maxPii = Math.max(...series.map((s) => s.pii), 1);

  const xStep = (W - PAD * 2) / Math.max(series.length - 1, 1);

  function toPath(values: number[], maxVal: number): string {
    return values
      .map((v, i) => {
        const x = PAD + i * xStep;
        const y = H - PAD - ((v / maxVal) * (H - PAD * 2));
        return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(" ");
  }

  const scanPath = toPath(series.map((s) => s.scans), maxScans);
  const piiPath = toPath(series.map((s) => s.pii), maxPii);

  const firstDate = series[0]?.date.slice(5) ?? "";
  const lastDate = series[series.length - 1]?.date.slice(5) ?? "";

  return (
    <div className="w-full overflow-hidden">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: 80 }}>
        <path d={scanPath} fill="none" stroke={NEON.cyan} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
        <path d={piiPath} fill="none" stroke={NEON.pink} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" strokeDasharray="4 2" />
      </svg>
      <div className="flex justify-between mt-1">
        <span className="text-[9px] text-muted-foreground font-mono">{firstDate}</span>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1 text-[9px]" style={{ color: NEON.cyan }}>
            <span className="w-3 h-0.5 inline-block rounded" style={{ backgroundColor: NEON.cyan }} /> Scans
          </span>
          <span className="flex items-center gap-1 text-[9px]" style={{ color: NEON.pink }}>
            <span className="w-3 h-0.5 inline-block rounded border-t-2 border-dashed" style={{ borderColor: NEON.pink }} /> PII
          </span>
        </div>
        <span className="text-[9px] text-muted-foreground font-mono">{lastDate}</span>
      </div>
    </div>
  );
}

export default function ReportsPage() {
  const t = useTranslations("reports");
  const defaults = getDefaultDates();

  const [fromDate, setFromDate] = useState(defaults.from);
  const [toDate, setToDate] = useState(defaults.to);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [timeline, setTimeline] = useState<ReportTimeline | null>(null);

  const fetchReports = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [summaryData, timelineData] = await Promise.all([
        api.reportSummary(fromDate, toDate),
        api.reportTimeline(fromDate, toDate, "day"),
      ]);
      setSummary(summaryData);
      setTimeline(timelineData);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load reports";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [fromDate, toDate]);

  const handleExport = () => {
    if (!summary) return;
    const blob = new Blob([JSON.stringify({ summary, timeline }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `guardforge-report-${fromDate}-${toDate}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportPdf = async () => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8004";
    const apiKey = process.env.NEXT_PUBLIC_API_KEY || "";
    const params = new URLSearchParams({ from_date: fromDate, to_date: toDate });
    try {
      const res = await fetch(`${apiBase}/api/reports/pdf?${params.toString()}`, {
        headers: { "X-API-Key": apiKey },
      });
      if (!res.ok) {
        throw new Error(`PDF export failed: ${res.statusText}`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `guardforge-compliance-${fromDate}-to-${toDate}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "PDF export failed";
      setError(message);
    }
  };

  const topPiiType = summary
    ? Object.entries(summary.pii_by_type).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "\u2014"
    : "\u2014";

  const criticalCount = summary ? (summary.risk_distribution.critical ?? 0) : 0;
  const piiByTypeMax = summary ? Math.max(...Object.values(summary.pii_by_type), 1) : 1;
  const actionMax = summary ? Math.max(...Object.values(summary.action_distribution), 1) : 1;

  const PII_TYPE_COLORS = [NEON.cyan, NEON.violet, NEON.amber, NEON.pink, NEON.green, "#f97316", "#4ecdc4", "#ffe66d"];

  return (
    <DashboardShell>
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="space-y-5 max-w-[1400px] mx-auto"
      >
        {/* Title + controls */}
        <motion.div variants={itemVariants} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight">{t("title")}</h1>
            <p className="text-sm text-muted-foreground mt-0.5">{t("subtitle")}</p>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              <label className="text-xs text-muted-foreground font-medium">{t("from")}</label>
              <input
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                className="px-3 py-1.5 rounded-lg text-xs bg-card border border-border text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/40"
              />
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs text-muted-foreground font-medium">{t("to")}</label>
              <input
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                className="px-3 py-1.5 rounded-lg text-xs bg-card border border-border text-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/40"
              />
            </div>
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              onClick={fetchReports}
              disabled={loading}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 text-white text-xs font-semibold disabled:opacity-40 hover:shadow-[0_0_16px_rgba(245,158,11,0.3)]"
            >
              {loading ? <Activity className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
              {t("refresh_btn")}
            </motion.button>
            {summary && (
              <motion.button
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                onClick={handleExport}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-card border border-border text-xs font-semibold text-foreground hover:bg-accent transition-all"
              >
                <Download className="w-3.5 h-3.5" />
                {t("export_btn")}
              </motion.button>
            )}
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              onClick={handleExportPdf}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-gradient-to-r from-pink-500 to-violet-500 text-white text-xs font-semibold hover:shadow-[0_0_16px_rgba(180,74,255,0.3)] transition-all"
            >
              <FileText className="w-3.5 h-3.5" />
              {t("export_pdf_btn")}
            </motion.button>
          </div>
        </motion.div>

        {/* Error */}
        {error && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-4"
            style={{ "--glow": NEON.pink } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 text-red-400">
              <AlertTriangle className="w-4 h-4" />
              <span className="text-sm font-semibold">{error}</span>
            </div>
          </motion.div>
        )}

        {/* Empty state */}
        {!loading && !error && !summary && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-14 text-center"
            style={{ "--glow": NEON.cyan } as React.CSSProperties}
          >
            <FileSearch className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
            <p className="text-sm font-semibold text-muted-foreground">{t("empty_state")}</p>
            <p className="text-xs text-muted-foreground/60 mt-1">
              {t("empty_state_subtitle")}
            </p>
          </motion.div>
        )}

        {/* Loading */}
        {loading && (
          <motion.div variants={itemVariants} className="flex items-center justify-center py-20">
            <Activity className="w-6 h-6 text-muted-foreground animate-spin" />
          </motion.div>
        )}

        {summary && (
          <>
            {/* 4 stat cards */}
            <motion.div variants={itemVariants} className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {[
                { label: t("total_scans"), value: summary.total_scans, color: NEON.cyan, icon: BarChart3 },
                { label: t("total_pii"), value: summary.total_pii_detected, color: NEON.violet, icon: AlertTriangle },
                { label: t("critical_count"), value: criticalCount, color: NEON.pink, icon: AlertTriangle },
                { label: t("top_pii"), value: topPiiType, color: NEON.amber, icon: TrendingUp },
              ].map((stat) => (
                <motion.div
                  key={stat.label}
                  whileHover={{ y: -4, boxShadow: `0 0 24px ${stat.color}25` }}
                  className="glass-card neon-card p-5 flex flex-col justify-between"
                  style={{ "--glow": stat.color } as React.CSSProperties}
                >
                  <div className="flex items-center gap-2">
                    <stat.icon className="w-4 h-4" style={{ color: stat.color }} />
                    <span className="text-xs font-medium text-muted-foreground">{stat.label}</span>
                  </div>
                  <p
                    className="text-2xl font-bold mt-3 neon-value truncate"
                    style={{ "--glow": stat.color } as React.CSSProperties}
                  >
                    {stat.value}
                  </p>
                </motion.div>
              ))}
            </motion.div>

            {/* Charts row 1: PII by type + Action distribution */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* PII by type */}
              <motion.div
                variants={itemVariants}
                className="glass-card neon-card p-5"
                style={{ "--glow": NEON.violet } as React.CSSProperties}
              >
                <h3 className="text-sm font-semibold mb-4">{t("pii_by_type")}</h3>
                {Object.keys(summary.pii_by_type).length === 0 ? (
                  <p className="text-xs text-muted-foreground text-center py-4">No data</p>
                ) : (
                  <div className="space-y-3">
                    {Object.entries(summary.pii_by_type)
                      .sort((a, b) => b[1] - a[1])
                      .map(([type, count], i) => (
                        <HBar
                          key={type}
                          label={type}
                          value={count}
                          max={piiByTypeMax}
                          color={PII_TYPE_COLORS[i % PII_TYPE_COLORS.length]}
                        />
                      ))}
                  </div>
                )}
              </motion.div>

              {/* Action distribution */}
              <motion.div
                variants={itemVariants}
                className="glass-card neon-card p-5"
                style={{ "--glow": NEON.amber } as React.CSSProperties}
              >
                <h3 className="text-sm font-semibold mb-4">{t("action_dist")}</h3>
                {Object.keys(summary.action_distribution).length === 0 ? (
                  <p className="text-xs text-muted-foreground text-center py-4">No data</p>
                ) : (
                  <div className="space-y-3">
                    {Object.entries(summary.action_distribution)
                      .sort((a, b) => b[1] - a[1])
                      .map(([action, count]) => {
                        const color =
                          action === "block" ? NEON.pink : action === "allow" ? NEON.green : NEON.amber;
                        return (
                          <HBar key={action} label={action} value={count} max={actionMax} color={color} />
                        );
                      })}
                  </div>
                )}
              </motion.div>
            </div>

            {/* Charts row 2: Risk distribution + Timeline */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Risk distribution */}
              <motion.div
                variants={itemVariants}
                className="glass-card neon-card p-5"
                style={{ "--glow": NEON.pink } as React.CSSProperties}
              >
                <h3 className="text-sm font-semibold mb-4">{t("risk_dist")}</h3>
                {Object.keys(summary.risk_distribution).length === 0 ? (
                  <p className="text-xs text-muted-foreground text-center py-4">No data</p>
                ) : (
                  <div className="grid grid-cols-2 gap-3">
                    {(["critical", "high", "medium", "low"] as const).map((level) => {
                      const count = summary.risk_distribution[level] ?? 0;
                      const color = RISK_COLORS[level] ?? NEON.cyan;
                      return (
                        <div
                          key={level}
                          className="rounded-xl border p-3 flex flex-col gap-1"
                          style={{
                            borderColor: `${color}30`,
                            backgroundColor: `${color}0a`,
                          }}
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
                )}
              </motion.div>

              {/* Timeline */}
              <motion.div
                variants={itemVariants}
                className="glass-card neon-card p-5"
                style={{ "--glow": NEON.cyan } as React.CSSProperties}
              >
                <h3 className="text-sm font-semibold mb-4">{t("timeline")}</h3>
                {timeline && timeline.series.length > 0 ? (
                  <TimelineChart series={timeline.series} noDataLabel={t("no_timeline_data")} />
                ) : (
                  <p className="text-xs text-muted-foreground text-center py-4">{t("no_timeline_data")}</p>
                )}
              </motion.div>
            </div>
          </>
        )}
      </motion.div>
    </DashboardShell>
  );
}
