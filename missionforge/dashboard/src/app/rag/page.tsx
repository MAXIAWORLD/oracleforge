"use client";

import { useEffect, useState, useCallback } from "react";
import { motion, useSpring, useTransform } from "framer-motion";
import {
  Database,
  CheckCircle,
  XCircle,
  HardDrive,
  Layers,
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

// ── GlowBar ──────────────────────────────────────────────────
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
export default function RagPage() {
  const t = useTranslations();
  const [obs, setObs] = useState<ObservabilitySummary | null>(null);
  const [ragStats, setRagStats] = useState<{
    ok: boolean;
    chunks: number;
    cache: number;
  } | null>(null);
  const [isOffline, setIsOffline] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [obsData, ragData] = await Promise.all([
        api.observabilitySummary(),
        api.ragStats(),
      ]);
      setObs(obsData);
      setRagStats(ragData);
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

  const chunks = ragStats?.chunks ?? obs?.rag.chunks ?? 0;
  const cached = ragStats?.cache ?? obs?.rag.cache ?? 0;
  const isHealthy = ragStats?.ok ?? obs?.rag.ok ?? false;
  const hitRate = chunks > 0 ? (cached / chunks) * 100 : 0;
  const memoryTotal = obs?.memory.total ?? 0;
  const collections = obs?.memory.collections ?? {};

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
          {/* Status */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(10,254,126,0.15)" }}
            className="col-span-3 glass-card neon-card p-5 flex flex-col justify-between"
            style={
              {
                "--glow": isHealthy ? NEON.green : NEON.pink,
              } as React.CSSProperties
            }
          >
            <div className="flex items-center gap-2">
              {isHealthy ? (
                <CheckCircle className="w-4 h-4 text-emerald-400" />
              ) : (
                <XCircle className="w-4 h-4 text-rose-400" />
              )}
              <span className="text-xs font-medium text-muted-foreground">
                {t("rag.kpi.status")}
              </span>
            </div>
            <p className="text-3xl font-bold mt-3">
              {isOffline ? (
                <span className="text-muted-foreground">&mdash;</span>
              ) : (
                <span
                  className={isHealthy ? "text-emerald-400" : "text-rose-400"}
                >
                  {isHealthy ? t("common.healthy") : t("common.degraded")}
                </span>
              )}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {t("rag.kpi.pipelineStatus")}
            </p>
          </motion.div>

          {/* Chunks */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(0,229,255,0.15)" }}
            className="col-span-3 glass-card neon-card p-5 flex flex-col justify-between"
            style={{ "--glow": NEON.cyan } as React.CSSProperties}
          >
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-medium text-muted-foreground">
                {t("rag.kpi.indexedChunks")}
              </span>
            </div>
            <p
              className="text-3xl font-bold neon-value mt-3"
              style={{ "--glow": NEON.cyan } as React.CSSProperties}
            >
              {isOffline ? (
                <span className="text-muted-foreground">&mdash;</span>
              ) : (
                <AnimatedNumber value={chunks} />
              )}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {t("rag.kpi.inVectorStore")}
            </p>
          </motion.div>

          {/* Cached */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(180,74,255,0.15)" }}
            className="col-span-3 glass-card neon-card p-5 flex flex-col justify-between"
            style={{ "--glow": NEON.violet } as React.CSSProperties}
          >
            <div className="flex items-center gap-2">
              <HardDrive className="w-4 h-4 text-violet-400" />
              <span className="text-xs font-medium text-muted-foreground">
                {t("rag.kpi.cachedEntries")}
              </span>
            </div>
            <p
              className="text-3xl font-bold neon-value mt-3"
              style={{ "--glow": NEON.violet } as React.CSSProperties}
            >
              {isOffline ? (
                <span className="text-muted-foreground">&mdash;</span>
              ) : (
                <AnimatedNumber value={cached} />
              )}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {t("rag.kpi.hitRate")}{" "}
              {isOffline ? "—" : `${hitRate.toFixed(1)}%`}
            </p>
          </motion.div>

          {/* Memory Total */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(255,184,0,0.15)" }}
            className="col-span-3 glass-card neon-card p-5 flex flex-col justify-between"
            style={{ "--glow": NEON.amber } as React.CSSProperties}
          >
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-amber-400" />
              <span className="text-xs font-medium text-muted-foreground">
                {t("rag.kpi.memoryItems")}
              </span>
            </div>
            <p
              className="text-3xl font-bold neon-value mt-3"
              style={{ "--glow": NEON.amber } as React.CSSProperties}
            >
              {isOffline ? (
                <span className="text-muted-foreground">&mdash;</span>
              ) : (
                <AnimatedNumber value={memoryTotal} />
              )}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {obs?.memory.backend ?? "—"} {t("rag.kpi.backendSuffix")}
            </p>
          </motion.div>
        </div>

        {/* ══════════ ROW 2: Cache Breakdown + Collections ══════════ */}
        <div className="grid grid-cols-12 gap-4">
          {/* Cache Breakdown */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(59,130,246,0.12)" }}
            className="col-span-7 glass-card neon-card p-5"
            style={{ "--glow": NEON.blue } as React.CSSProperties}
          >
            <h3 className="text-sm font-semibold flex items-center gap-2 mb-4">
              <Database className="w-4 h-4 text-blue-400" />
              {t("rag.cache.title")}
            </h3>
            {isOffline ? (
              <div className="flex items-center justify-center h-[140px]">
                <p className="text-xs text-muted-foreground">
                  {t("rag.cache.connect")}
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                <GlowBar
                  label={t("rag.cache.chunks")}
                  value={chunks}
                  displayValue={chunks.toLocaleString()}
                  color={NEON.cyan}
                  maxWidth={Math.max(chunks, cached, 1)}
                />
                <GlowBar
                  label={t("rag.cache.cached")}
                  value={cached}
                  displayValue={cached.toLocaleString()}
                  color={NEON.violet}
                  maxWidth={Math.max(chunks, cached, 1)}
                />
                <GlowBar
                  label={t("rag.cache.hitRate")}
                  value={hitRate}
                  displayValue={`${hitRate.toFixed(1)}%`}
                  color={NEON.green}
                  maxWidth={100}
                />
              </div>
            )}
          </motion.div>

          {/* Collections */}
          <motion.div
            variants={itemVariants}
            whileHover={{ y: -4, boxShadow: "0 0 24px rgba(180,74,255,0.12)" }}
            className="col-span-5 glass-card neon-card p-5"
            style={{ "--glow": NEON.violet } as React.CSSProperties}
          >
            <h3 className="text-sm font-semibold flex items-center gap-2 mb-4">
              <Layers className="w-4 h-4 text-violet-400" />
              {t("rag.collections.title")}
            </h3>
            {isOffline || Object.keys(collections).length === 0 ? (
              <div className="flex items-center justify-center h-[140px]">
                <p className="text-xs text-muted-foreground">
                  {isOffline
                    ? t("rag.collections.connect")
                    : t("common.noCollections")}
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {Object.entries(collections).map(([collectionName, count]) => (
                  <div
                    key={collectionName}
                    className="flex items-center justify-between p-3 rounded-xl bg-muted/20 border border-border/50"
                  >
                    <span className="text-xs font-medium">
                      {collectionName}
                    </span>
                    <span
                      className="text-sm font-bold neon-value"
                      style={{ "--glow": NEON.violet } as React.CSSProperties}
                    >
                      {count}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        </div>
      </motion.div>
    </DashboardShell>
  );
}
