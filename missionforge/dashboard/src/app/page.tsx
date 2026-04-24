"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { motion, useSpring, useTransform } from "framer-motion";
import { Brain, Database, Layers, MemoryStick, CirclePlay } from "lucide-react";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import { useTranslations } from "next-intl";
import {
  DashboardShell,
  NEON,
  containerVariants,
  itemVariants,
} from "@/components/dashboard-shell";
import { api } from "@/lib/api";
import type { ObservabilitySummary, MissionSummary } from "@/lib/api";

// ── Tier badge colors ───────────────────────────────────────────
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

// ── Animated counter component ──────────────────────────────────
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

// ── Semicircle gauge SVG ────────────────────────────────────────
function SemiGauge({
  value,
  max,
  label,
  unit,
  color,
}: {
  value: number;
  max: number;
  label: string;
  unit: string;
  color: string;
}) {
  const pct = Math.min(value / max, 1);
  const radius = 52;
  const circumference = Math.PI * radius;
  const offset = circumference * (1 - pct);

  return (
    <div className="flex flex-col items-center gap-1">
      <svg
        width="120"
        height="70"
        viewBox="0 0 120 70"
        className="overflow-visible"
      >
        {/* Background arc */}
        <path
          d={`M 8 65 A ${radius} ${radius} 0 0 1 112 65`}
          fill="none"
          stroke="currentColor"
          strokeWidth="8"
          className="text-muted/30"
          strokeLinecap="round"
        />
        {/* Value arc */}
        <path
          d={`M 8 65 A ${radius} ${radius} 0 0 1 112 65`}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-1000"
          style={{
            transition: "stroke-dashoffset 1.2s cubic-bezier(0.4, 0, 0.2, 1)",
          }}
        />
        {/* Center value */}
        <text
          x="60"
          y="58"
          textAnchor="middle"
          className="fill-foreground text-lg font-bold"
          style={{ fontSize: "18px" }}
        >
          {Math.round(pct * 100)}%
        </text>
      </svg>
      <span className="text-xs text-muted-foreground font-medium">{label}</span>
      <span className="text-[10px] text-muted-foreground/60">{unit}</span>
    </div>
  );
}

// ── Donut center text component ─────────────────────────────────
function DonutCenter({ value, label }: { value: string; label: string }) {
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
      <span
        className="text-2xl font-bold neon-value"
        style={{ "--glow": NEON.cyan } as React.CSSProperties}
      >
        {value}
      </span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  );
}

// ── Horizontal progress bar with glow ───────────────────────────
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
        className="text-xs font-mono font-semibold w-14 text-right"
        style={{ color }}
      >
        {displayValue}
      </span>
    </div>
  );
}

// ── Offline placeholder ─────────────────────────────────────────
function OfflineDash() {
  return <span className="text-muted-foreground">&mdash;</span>;
}

// ── Main Page Component ─────────────────────────────────────────
export default function DashboardPage() {
  const t = useTranslations();
  const [isOffline, setIsOffline] = useState(true);
  const [obs, setObs] = useState<ObservabilitySummary | null>(null);
  const [missions, setMissions] = useState<MissionSummary[]>([]);

  // Data fetching
  const fetchData = useCallback(async () => {
    try {
      const [obsData, missData] = await Promise.all([
        api.observabilitySummary(),
        api.listMissions(),
      ]);
      setObs(obsData);
      setMissions(missData.missions || []);
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

  // Derived values — all conditional on obs being non-null
  const totalMissions = obs?.missions.total ?? 0;
  const totalCalls = obs?.llm.total_calls ?? 0;
  const totalCost = obs?.llm.total_cost_usd ?? 0;
  const ragChunks = obs?.rag.chunks ?? 0;
  const memoryTotal = obs?.memory.total ?? 0;

  // Health derived from real state
  const apiHealth = isOffline ? 0 : 100;
  const ragHealth = obs?.rag.ok ? 100 : 0;

  // Donut data — derived from obs
  const donutData = useMemo(
    () => [
      {
        name: t("common.scheduled"),
        value: obs?.missions.scheduled ?? 0,
        color: NEON.cyan,
      },
      {
        name: t("common.manual"),
        value: obs?.missions.manual ?? 0,
        color: NEON.violet,
      },
    ],
    [obs, t],
  );

  // Performance metrics — derived from obs
  const metrics = useMemo(() => {
    if (!obs) return [];
    const tiers = Object.values(obs.llm.by_tier);
    const avgLatency =
      tiers.length > 0
        ? Math.round(
            tiers.reduce((s, tier) => s + tier.last_latency_ms, 0) /
              tiers.length,
          )
        : 0;
    const costPerCall =
      totalCost > 0 && totalCalls > 0
        ? +((totalCost / totalCalls) * 1000).toFixed(2)
        : 0;
    const costPerCallDisplay =
      totalCalls > 0 ? `$${(totalCost / totalCalls).toFixed(5)}` : "—";

    return [
      {
        label: t("dashboard.performance.avgLatency"),
        value: avgLatency,
        displayValue: `${avgLatency}ms`,
        color: NEON.cyan,
        max: 2000,
      },
      {
        label: t("dashboard.performance.ragCache"),
        value: obs.rag.cache,
        displayValue: `${obs.rag.cache}`,
        color: NEON.green,
        max: obs.rag.chunks || 1,
      },
      {
        label: t("dashboard.performance.memoryItems"),
        value: obs.memory.total,
        displayValue: `${obs.memory.total}`,
        color: NEON.violet,
        max: 500,
      },
      {
        label: t("dashboard.performance.costPerCall"),
        value: costPerCall,
        displayValue: costPerCallDisplay,
        color: NEON.amber,
        max: 0.1,
      },
    ];
  }, [obs, totalCost, totalCalls, t]);

  // Mini metrics — derived from obs
  const miniMetrics = useMemo(
    () => [
      {
        label: t("dashboard.miniMetrics.queue"),
        value: 0,
        icon: Layers,
        color: NEON.cyan,
      },
      {
        label: t("dashboard.miniMetrics.memory"),
        value: memoryTotal,
        icon: MemoryStick,
        color: NEON.violet,
      },
      {
        label: t("dashboard.miniMetrics.active"),
        value: obs?.missions.scheduled ?? 0,
        icon: CirclePlay,
        color: NEON.green,
      },
      {
        label: t("dashboard.miniMetrics.tiers"),
        value: obs ? Object.keys(obs.llm.by_tier).length : 0,
        icon: Brain,
        color: NEON.amber,
      },
    ],
    [memoryTotal, obs, t],
  );

  return (
    <DashboardShell>
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="space-y-5 max-w-[1600px] mx-auto"
      >
        {/* ══════════ ROW 1: Donut + KPIs + Gauges ══════════ */}
        <div className="grid grid-cols-12 gap-4">
          {/* Big Donut */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(0,229,255,0.15)" }}
            className="col-span-3 glass-card neon-card p-5 flex flex-col items-center justify-center relative"
            style={{ "--glow": NEON.cyan } as React.CSSProperties}
          >
            <div className="relative w-full" style={{ height: 180 }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={donutData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={75}
                    paddingAngle={4}
                    dataKey="value"
                    stroke="none"
                  >
                    {donutData.map((entry, i) => (
                      <Cell key={`cell-${i}`} fill={entry.color} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <DonutCenter
                value={isOffline ? "—" : `${totalMissions}`}
                label={t("dashboard.donut.label")}
              />
            </div>
            <div className="flex gap-4 mt-2">
              {donutData.map((d) => (
                <div key={d.name} className="flex items-center gap-1.5">
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: d.color }}
                  />
                  <span className="text-[10px] text-muted-foreground">
                    {d.name} ({d.value})
                  </span>
                </div>
              ))}
            </div>
          </motion.div>

          {/* KPI: LLM Calls */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(180,74,255,0.15)" }}
            className="col-span-2 glass-card neon-card p-5 flex flex-col justify-between"
            style={{ "--glow": NEON.violet } as React.CSSProperties}
          >
            <div className="flex items-center gap-2">
              <Brain className="w-4 h-4 text-violet-400" />
              <span className="text-xs font-medium text-muted-foreground">
                {t("dashboard.kpi.llmCalls")}
              </span>
            </div>
            <div>
              <p
                className="text-3xl font-bold neon-value mt-3"
                style={{ "--glow": NEON.violet } as React.CSSProperties}
              >
                {isOffline ? (
                  <OfflineDash />
                ) : (
                  <AnimatedNumber value={totalCalls} />
                )}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {t("dashboard.kpi.costLabel")}{" "}
                <span className="text-violet-400 font-semibold">
                  {isOffline ? "—" : `$${totalCost.toFixed(4)}`}
                </span>
              </p>
            </div>
          </motion.div>

          {/* KPI: Total Cost */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(255,184,0,0.15)" }}
            className="col-span-2 glass-card neon-card p-5 flex flex-col justify-between"
            style={{ "--glow": NEON.amber } as React.CSSProperties}
          >
            <div className="flex items-center gap-2">
              <span className="text-amber-400 text-sm font-bold">$</span>
              <span className="text-xs font-medium text-muted-foreground">
                {t("dashboard.kpi.totalCost")}
              </span>
            </div>
            <div>
              <p
                className="text-3xl font-bold neon-value mt-3"
                style={{ "--glow": NEON.amber } as React.CSSProperties}
              >
                {isOffline ? (
                  <OfflineDash />
                ) : (
                  <AnimatedNumber value={totalCost} prefix="$" decimals={4} />
                )}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {t("dashboard.kpi.todaysSpend")}
              </p>
            </div>
          </motion.div>

          {/* KPI: RAG Chunks */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(10,254,126,0.15)" }}
            className="col-span-2 glass-card neon-card p-5 flex flex-col justify-between"
            style={{ "--glow": NEON.green } as React.CSSProperties}
          >
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-medium text-muted-foreground">
                {t("dashboard.kpi.ragChunks")}
              </span>
            </div>
            <div>
              <p
                className="text-3xl font-bold neon-value mt-3"
                style={{ "--glow": NEON.green } as React.CSSProperties}
              >
                {isOffline ? (
                  <OfflineDash />
                ) : (
                  <AnimatedNumber value={ragChunks} />
                )}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {t("dashboard.kpi.statusLabel")}{" "}
                <span className="text-emerald-400 font-semibold">
                  {isOffline
                    ? "—"
                    : obs?.rag.ok
                      ? t("common.healthy")
                      : t("common.degraded")}
                </span>
              </p>
            </div>
          </motion.div>

          {/* Semicircle Gauge: API Health */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(0,229,255,0.15)" }}
            className="col-span-2 glass-card neon-card p-5 flex items-center justify-center"
            style={{ "--glow": NEON.cyan } as React.CSSProperties}
          >
            <SemiGauge
              value={apiHealth}
              max={100}
              label={t("dashboard.kpi.apiHealth")}
              unit={
                isOffline
                  ? t("dashboard.kpi.offlineUnit")
                  : t("dashboard.kpi.callsPerDay", { count: totalCalls })
              }
              color={NEON.cyan}
            />
          </motion.div>

          {/* Semicircle Gauge: RAG Health */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(180,74,255,0.15)" }}
            className="col-span-1 glass-card neon-card p-5 flex items-center justify-center"
            style={{ "--glow": NEON.violet } as React.CSSProperties}
          >
            <SemiGauge
              value={ragHealth}
              max={100}
              label={t("dashboard.kpi.ragPipeline")}
              unit={
                isOffline
                  ? t("dashboard.kpi.offlineUnit")
                  : t("dashboard.kpi.chunksUnit", { count: ragChunks })
              }
              color={NEON.violet}
            />
          </motion.div>
        </div>

        {/* ══════════ ROW 2: Tier Breakdown + Performance Metrics ══════════ */}
        <div className="grid grid-cols-12 gap-4">
          {/* LLM Tier Breakdown */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(59,130,246,0.12)" }}
            className="col-span-7 glass-card neon-card p-5"
            style={{ "--glow": NEON.blue } as React.CSSProperties}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold">
                {t("dashboard.tierBreakdown.title")}
              </h3>
            </div>
            {isOffline || !obs ? (
              <div className="flex items-center justify-center h-[220px]">
                <p className="text-xs text-muted-foreground">
                  {t("common.dataAvailable")}
                </p>
              </div>
            ) : (
              <div style={{ height: 220 }}>
                <div className="space-y-4 pt-4">
                  {Object.entries(obs.llm.by_tier).map(([tier, stats]) => {
                    const tc = TIER_COLORS[tier] || TIER_COLORS.balanced;
                    const maxCalls = Math.max(
                      ...Object.values(obs.llm.by_tier).map(
                        (tierStats) => tierStats.calls,
                      ),
                      1,
                    );
                    return (
                      <GlowBar
                        key={tier}
                        label={tier}
                        value={stats.calls}
                        displayValue={t("dashboard.tierBreakdown.calls", {
                          count: stats.calls,
                        })}
                        color={tc.glow}
                        maxWidth={maxCalls}
                      />
                    );
                  })}
                  {Object.keys(obs.llm.by_tier).length === 0 && (
                    <p className="text-xs text-muted-foreground text-center pt-8">
                      {t("dashboard.tierBreakdown.empty")}
                    </p>
                  )}
                </div>
              </div>
            )}
          </motion.div>

          {/* Performance Metrics */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(255,184,0,0.12)" }}
            className="col-span-5 glass-card neon-card p-5"
            style={{ "--glow": NEON.amber } as React.CSSProperties}
          >
            <h3 className="text-sm font-semibold mb-5">
              {t("dashboard.performance.title")}
            </h3>
            {isOffline || metrics.length === 0 ? (
              <div className="flex items-center justify-center h-[200px]">
                <p className="text-xs text-muted-foreground">
                  {t("common.dataAvailable")}
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {metrics.map((m) => (
                  <GlowBar
                    key={m.label}
                    label={m.label}
                    value={m.value}
                    displayValue={m.displayValue}
                    color={m.color}
                    maxWidth={m.max}
                  />
                ))}
              </div>
            )}
          </motion.div>
        </div>

        {/* ══════════ ROW 3: Mission Summary + Mini Metrics + Missions Table ══════════ */}
        <div className="grid grid-cols-12 gap-4">
          {/* Mission Summary */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(59,130,246,0.12)" }}
            className="col-span-3 glass-card neon-card p-5"
            style={{ "--glow": NEON.blue } as React.CSSProperties}
          >
            <h3 className="text-sm font-semibold mb-4">
              {t("dashboard.missionsSummary.title")}
            </h3>
            {isOffline || !obs ? (
              <div className="flex items-center justify-center h-[200px]">
                <p className="text-xs text-muted-foreground">
                  {t("common.dataAvailable")}
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-[200px] gap-3">
                <p
                  className="text-3xl font-bold neon-value"
                  style={{ "--glow": NEON.cyan } as React.CSSProperties}
                >
                  <AnimatedNumber value={totalMissions} />
                </p>
                <p className="text-xs text-muted-foreground">
                  {t("dashboard.missionsSummary.totalLoaded")}
                </p>
                <div className="flex gap-4 mt-2">
                  <div className="text-center">
                    <p className="text-lg font-bold text-cyan-400">
                      {obs.missions.scheduled}
                    </p>
                    <p className="text-[10px] text-muted-foreground">
                      {t("common.scheduled")}
                    </p>
                  </div>
                  <div className="text-center">
                    <p className="text-lg font-bold text-violet-400">
                      {obs.missions.manual}
                    </p>
                    <p className="text-[10px] text-muted-foreground">
                      {t("common.manual")}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </motion.div>

          {/* Mini Metrics Grid */}
          <motion.div
            variants={itemVariants}
            className="col-span-3 grid grid-cols-2 gap-3"
          >
            {miniMetrics.map((m) => (
              <motion.div
                key={m.label}
                variants={itemVariants}
                whileHover={{ y: -4, boxShadow: `0 0 20px ${m.color}20` }}
                className="glass-card neon-card p-4 flex flex-col items-center justify-center gap-2"
                style={{ "--glow": m.color } as React.CSSProperties}
              >
                <m.icon className="w-5 h-5" style={{ color: m.color }} />
                <span
                  className="text-2xl font-bold neon-value"
                  style={{ "--glow": m.color } as React.CSSProperties}
                >
                  <AnimatedNumber value={m.value} />
                </span>
                <span className="text-[10px] text-muted-foreground font-medium">
                  {m.label}
                </span>
              </motion.div>
            ))}
          </motion.div>

          {/* Missions Table */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(0,229,255,0.10)" }}
            className="col-span-6 glass-card neon-card p-5"
            style={{ "--glow": NEON.cyan } as React.CSSProperties}
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold">
                {t("dashboard.missionsTable.title")}
              </h3>
              <span className="text-[10px] text-muted-foreground">
                {missions.length} {t("dashboard.missionsTable.totalSuffix")}
              </span>
            </div>
            {missions.length === 0 ? (
              <div className="flex items-center justify-center h-[200px]">
                <p className="text-xs text-muted-foreground">
                  {isOffline
                    ? t("common.dataAvailable")
                    : t("common.noMissions")}
                </p>
              </div>
            ) : (
              <div className="overflow-y-auto max-h-[210px] scrollbar-thin">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-[10px] text-muted-foreground font-medium text-left pb-2 pr-2">
                        {t("dashboard.missionsTable.headers.status")}
                      </th>
                      <th className="text-[10px] text-muted-foreground font-medium text-left pb-2 pr-2">
                        {t("dashboard.missionsTable.headers.name")}
                      </th>
                      <th className="text-[10px] text-muted-foreground font-medium text-left pb-2 pr-2">
                        {t("dashboard.missionsTable.headers.tier")}
                      </th>
                      <th className="text-[10px] text-muted-foreground font-medium text-left pb-2 pr-2">
                        {t("dashboard.missionsTable.headers.steps")}
                      </th>
                      <th className="text-[10px] text-muted-foreground font-medium text-left pb-2">
                        {t("dashboard.missionsTable.headers.schedule")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {missions.map((m) => {
                      const tier =
                        TIER_COLORS[m.agent_tier] || TIER_COLORS.balanced;
                      return (
                        <tr
                          key={m.name}
                          className="border-b border-border/50 hover:bg-accent/30 transition-colors"
                        >
                          <td className="py-2 pr-2">
                            <span
                              className={`w-2 h-2 rounded-full inline-block ${
                                m.schedule
                                  ? "bg-emerald-400"
                                  : "bg-muted-foreground/40"
                              }`}
                            />
                          </td>
                          <td className="py-2 pr-2">
                            <span className="text-xs font-medium">
                              {m.name}
                            </span>
                          </td>
                          <td className="py-2 pr-2">
                            <span
                              className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${tier.bg} ${tier.text}`}
                            >
                              {m.agent_tier}
                            </span>
                          </td>
                          <td className="py-2 pr-2">
                            <span className="text-xs text-muted-foreground">
                              {m.steps_count}
                            </span>
                          </td>
                          <td className="py-2">
                            <span className="text-[10px] font-mono text-muted-foreground">
                              {m.schedule || t("common.manual")}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </motion.div>
        </div>
      </motion.div>
    </DashboardShell>
  );
}
