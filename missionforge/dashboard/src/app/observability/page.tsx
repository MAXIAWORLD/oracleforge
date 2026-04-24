"use client";

import { useEffect, useState, useCallback } from "react";
import { motion, useSpring, useTransform } from "framer-motion";
import {
  Activity,
  Brain,
  DollarSign,
  Clock,
  Zap,
  TrendingUp,
} from "lucide-react";
import { useTranslations } from "next-intl";
import {
  DashboardShell,
  NEON,
  containerVariants,
  itemVariants,
} from "@/components/dashboard-shell";
import { api } from "@/lib/api";
import type { ObservabilitySummary } from "@/lib/api";

// ── Animated counter ───────────────────────────────────────────
function AnimatedNumber({
  value,
  prefix = "",
  suffix = "",
  decimals = 0,
}: {
  value: number;
  prefix?: string;
  suffix?: string;
  decimals?: number;
}) {
  const spring = useSpring(0, { stiffness: 80, damping: 20 });
  const display = useTransform(spring, (v) => {
    if (decimals > 0) return `${prefix}${v.toFixed(decimals)}${suffix}`;
    return `${prefix}${Math.round(v).toLocaleString()}${suffix}`;
  });

  useEffect(() => {
    spring.set(value);
  }, [spring, value]);

  return <motion.span>{display}</motion.span>;
}

// ── Tier badge colors ──────────────────────────────────────────
const TIER_COLORS: Record<string, { bg: string; text: string; glow: string }> =
  {
    fast: {
      bg: "bg-emerald-500/15",
      text: "text-emerald-400",
      glow: NEON.green,
    },
    balanced: { bg: "bg-blue-500/15", text: "text-blue-400", glow: NEON.blue },
    premium: {
      bg: "bg-violet-500/15",
      text: "text-violet-400",
      glow: NEON.violet,
    },
  };

// ── GlowBar ────────────────────────────────────────────────────
function GlowBar({
  label,
  value,
  displayValue,
  color,
  maxWidth = 100,
}: {
  label: string;
  value: number;
  displayValue: string;
  color: string;
  maxWidth?: number;
}) {
  const pct = Math.min((value / maxWidth) * 100, 100);
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-muted-foreground w-20 text-right shrink-0">
        {label}
      </span>
      <div className="flex-1 h-3 rounded-full bg-muted/40 relative overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ backgroundColor: color, width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 1.2, ease: "easeOut", delay: 0.3 }}
        />
      </div>
      <span
        className="text-xs font-mono font-semibold w-16 text-right"
        style={{ color }}
      >
        {displayValue}
      </span>
    </div>
  );
}

// ── Main ───────────────────────────────────────────────────────
export default function ObservabilityPage() {
  const t = useTranslations();
  const [obs, setObs] = useState<ObservabilitySummary | null>(null);
  const [isOffline, setIsOffline] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const data = await api.observabilitySummary();
      setObs(data);
      setIsOffline(false);
    } catch {
      setIsOffline(true);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, 15_000);
    return () => clearInterval(id);
  }, [fetchData]);

  const tiers = obs ? Object.entries(obs.llm.by_tier) : [];
  const maxCalls = Math.max(...tiers.map(([, s]) => s.calls), 1);

  return (
    <DashboardShell>
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="space-y-5 max-w-[1600px] mx-auto"
      >
        {/* ══════════ ROW 1: KPI Cards ══════════ */}
        <div className="grid grid-cols-12 gap-4">
          {/* Total LLM Calls */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(0,229,255,0.15)" }}
            className="col-span-3 glass-card neon-card p-5 flex flex-col justify-between"
            style={{ "--glow": NEON.cyan } as React.CSSProperties}
          >
            <div className="flex items-center gap-2">
              <Brain className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-medium text-muted-foreground">
                {t("observability.kpi.totalCalls")}
              </span>
            </div>
            <p
              className="text-3xl font-bold neon-value mt-3"
              style={{ "--glow": NEON.cyan } as React.CSSProperties}
            >
              {isOffline ? (
                <span className="text-muted-foreground">&mdash;</span>
              ) : (
                <AnimatedNumber value={obs?.llm.total_calls ?? 0} />
              )}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {obs?.llm.date ?? t("common.today")}
            </p>
          </motion.div>

          {/* Total Cost */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(180,74,255,0.15)" }}
            className="col-span-3 glass-card neon-card p-5 flex flex-col justify-between"
            style={{ "--glow": NEON.violet } as React.CSSProperties}
          >
            <div className="flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-violet-400" />
              <span className="text-xs font-medium text-muted-foreground">
                {t("observability.kpi.totalCost")}
              </span>
            </div>
            <p
              className="text-3xl font-bold neon-value mt-3"
              style={{ "--glow": NEON.violet } as React.CSSProperties}
            >
              {isOffline ? (
                <span className="text-muted-foreground">&mdash;</span>
              ) : (
                <AnimatedNumber
                  value={obs?.llm.total_cost_usd ?? 0}
                  prefix="$"
                  decimals={4}
                />
              )}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {t("observability.kpi.usdToday")}
            </p>
          </motion.div>

          {/* Avg Latency */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(10,254,126,0.15)" }}
            className="col-span-3 glass-card neon-card p-5 flex flex-col justify-between"
            style={{ "--glow": NEON.green } as React.CSSProperties}
          >
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-medium text-muted-foreground">
                {t("observability.kpi.avgLatency")}
              </span>
            </div>
            <p
              className="text-3xl font-bold neon-value mt-3"
              style={{ "--glow": NEON.green } as React.CSSProperties}
            >
              {isOffline || tiers.length === 0 ? (
                <span className="text-muted-foreground">&mdash;</span>
              ) : (
                <AnimatedNumber
                  value={Math.round(
                    tiers.reduce((s, [, tier]) => s + tier.last_latency_ms, 0) /
                      tiers.length,
                  )}
                  suffix="ms"
                />
              )}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {t("observability.kpi.acrossAllTiers")}
            </p>
          </motion.div>

          {/* Active Tiers */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(255,184,0,0.15)" }}
            className="col-span-3 glass-card neon-card p-5 flex flex-col justify-between"
            style={{ "--glow": NEON.amber } as React.CSSProperties}
          >
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-400" />
              <span className="text-xs font-medium text-muted-foreground">
                {t("observability.kpi.activeTiers")}
              </span>
            </div>
            <p
              className="text-3xl font-bold neon-value mt-3"
              style={{ "--glow": NEON.amber } as React.CSSProperties}
            >
              {isOffline ? (
                <span className="text-muted-foreground">&mdash;</span>
              ) : (
                <AnimatedNumber value={tiers.length} />
              )}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {tiers.map(([tierName]) => tierName).join(", ") ||
                t("common.none")}
            </p>
          </motion.div>
        </div>

        {/* ══════════ ROW 2: Tier Breakdown ══════════ */}
        <div className="grid grid-cols-12 gap-4">
          {/* Tier Call Distribution */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(59,130,246,0.12)" }}
            className="col-span-7 glass-card neon-card p-5"
            style={{ "--glow": NEON.blue } as React.CSSProperties}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <Activity className="w-4 h-4 text-blue-400" />
                {t("observability.tierDistribution.title")}
              </h3>
              <span className="text-[10px] text-muted-foreground">
                {t("observability.tierDistribution.activeCount", {
                  count: tiers.length,
                })}
              </span>
            </div>
            {isOffline ? (
              <div className="flex items-center justify-center h-[200px]">
                <p className="text-xs text-muted-foreground">
                  {t("observability.tierDistribution.connect")}
                </p>
              </div>
            ) : tiers.length === 0 ? (
              <div className="flex items-center justify-center h-[200px]">
                <p className="text-xs text-muted-foreground">
                  {t("observability.tierDistribution.empty")}
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {tiers.map(([tier, stats]) => {
                  const tc = TIER_COLORS[tier] ?? TIER_COLORS.balanced;
                  return (
                    <GlowBar
                      key={tier}
                      label={tier}
                      value={stats.calls}
                      displayValue={t("observability.tierDistribution.calls", {
                        count: stats.calls,
                      })}
                      color={tc.glow}
                      maxWidth={maxCalls}
                    />
                  );
                })}
              </div>
            )}
          </motion.div>

          {/* Tier Detail Cards */}
          <motion.div variants={itemVariants} className="col-span-5 space-y-3">
            {isOffline ? (
              <motion.div
                variants={itemVariants}
                className="glass-card neon-card p-5 flex items-center justify-center h-full"
                style={{ "--glow": NEON.violet } as React.CSSProperties}
              >
                <p className="text-xs text-muted-foreground">
                  {t("observability.tierDetail.connect")}
                </p>
              </motion.div>
            ) : (
              tiers.map(([tier, stats]) => {
                const tc = TIER_COLORS[tier] ?? TIER_COLORS.balanced;
                return (
                  <motion.div
                    key={tier}
                    variants={itemVariants}
                    whileHover={{ y: -2, boxShadow: `0 0 16px ${tc.glow}15` }}
                    className="glass-card neon-card p-4"
                    style={{ "--glow": tc.glow } as React.CSSProperties}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${tc.bg} ${tc.text}`}
                      >
                        {tier}
                      </span>
                      <span className="text-[10px] text-muted-foreground">
                        {t("observability.tierDistribution.calls", {
                          count: stats.calls,
                        })}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-xs">
                      <div>
                        <span className="text-muted-foreground text-[10px]">
                          {t("observability.tierDetail.latency")}
                        </span>
                        <br />
                        <strong
                          className="neon-value"
                          style={{ "--glow": tc.glow } as React.CSSProperties}
                        >
                          {stats.last_latency_ms}ms
                        </strong>
                      </div>
                      <div>
                        <span className="text-muted-foreground text-[10px]">
                          {t("observability.tierDetail.cost")}
                        </span>
                        <br />
                        <strong
                          className="neon-value"
                          style={
                            { "--glow": NEON.amber } as React.CSSProperties
                          }
                        >
                          ${stats.cost.toFixed(4)}
                        </strong>
                      </div>
                      <div>
                        <span className="text-muted-foreground text-[10px]">
                          {t("observability.tierDetail.costPerCall")}
                        </span>
                        <br />
                        <strong
                          className="neon-value"
                          style={{ "--glow": NEON.pink } as React.CSSProperties}
                        >
                          {stats.calls > 0
                            ? `$${(stats.cost / stats.calls).toFixed(5)}`
                            : "—"}
                        </strong>
                      </div>
                    </div>
                  </motion.div>
                );
              })
            )}
          </motion.div>
        </div>

        {/* ══════════ ROW 3: Memory & RAG Summary ══════════ */}
        <div className="grid grid-cols-12 gap-4">
          {/* Memory */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(180,74,255,0.12)" }}
            className="col-span-6 glass-card neon-card p-5"
            style={{ "--glow": NEON.violet } as React.CSSProperties}
          >
            <h3 className="text-sm font-semibold flex items-center gap-2 mb-4">
              <TrendingUp className="w-4 h-4 text-violet-400" />
              {t("observability.memory.title")}
            </h3>
            {isOffline || !obs ? (
              <div className="flex items-center justify-center h-[100px]">
                <p className="text-xs text-muted-foreground">
                  {t("observability.memory.connect")}
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-3 gap-6">
                <div className="flex flex-col items-center gap-1">
                  <span
                    className="text-2xl font-bold neon-value"
                    style={{ "--glow": NEON.violet } as React.CSSProperties}
                  >
                    <AnimatedNumber value={obs.memory.total} />
                  </span>
                  <span className="text-[10px] text-muted-foreground font-medium">
                    {t("observability.memory.totalItems")}
                  </span>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <span
                    className="text-2xl font-bold neon-value"
                    style={{ "--glow": NEON.cyan } as React.CSSProperties}
                  >
                    {obs.memory.backend}
                  </span>
                  <span className="text-[10px] text-muted-foreground font-medium">
                    {t("observability.memory.backend")}
                  </span>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <span
                    className="text-2xl font-bold neon-value"
                    style={{ "--glow": NEON.green } as React.CSSProperties}
                  >
                    <AnimatedNumber
                      value={
                        obs.memory.collections
                          ? Object.keys(obs.memory.collections).length
                          : 0
                      }
                    />
                  </span>
                  <span className="text-[10px] text-muted-foreground font-medium">
                    {t("observability.memory.collections")}
                  </span>
                </div>
              </div>
            )}
          </motion.div>

          {/* RAG Overview */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(10,254,126,0.12)" }}
            className="col-span-6 glass-card neon-card p-5"
            style={{ "--glow": NEON.green } as React.CSSProperties}
          >
            <h3 className="text-sm font-semibold flex items-center gap-2 mb-4">
              <Activity className="w-4 h-4 text-emerald-400" />
              {t("observability.rag.title")}
            </h3>
            {isOffline || !obs ? (
              <div className="flex items-center justify-center h-[100px]">
                <p className="text-xs text-muted-foreground">
                  {t("observability.rag.connect")}
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-3 gap-6">
                <div className="flex flex-col items-center gap-1">
                  <span
                    className={`text-2xl font-bold ${obs.rag.ok ? "text-emerald-400" : "text-rose-400"}`}
                  >
                    {obs.rag.ok ? t("common.healthy") : t("common.degraded")}
                  </span>
                  <span className="text-[10px] text-muted-foreground font-medium">
                    {t("observability.rag.status")}
                  </span>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <span
                    className="text-2xl font-bold neon-value"
                    style={{ "--glow": NEON.green } as React.CSSProperties}
                  >
                    <AnimatedNumber value={obs.rag.chunks} />
                  </span>
                  <span className="text-[10px] text-muted-foreground font-medium">
                    {t("observability.rag.chunks")}
                  </span>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <span
                    className="text-2xl font-bold neon-value"
                    style={{ "--glow": NEON.amber } as React.CSSProperties}
                  >
                    <AnimatedNumber value={obs.rag.cache} />
                  </span>
                  <span className="text-[10px] text-muted-foreground font-medium">
                    {t("observability.rag.cached")}
                  </span>
                </div>
              </div>
            )}
          </motion.div>
        </div>
      </motion.div>
    </DashboardShell>
  );
}
