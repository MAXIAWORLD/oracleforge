"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Bot, Play, RefreshCw, Rocket } from "lucide-react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DashboardShell,
  NEON,
  containerVariants,
  itemVariants,
} from "@/components/dashboard-shell";
import { api, type MissionSummary, type RunResponse } from "@/lib/api";

// ── Tier badge colors ────────────────────────────────────────────
const TIER_COLORS: Record<string, { bg: string; text: string }> = {
  fast: { bg: "bg-emerald-500/15", text: "text-emerald-400" },
  balanced: { bg: "bg-blue-500/15", text: "text-blue-400" },
  premium: { bg: "bg-violet-500/15", text: "text-violet-400" },
};

export default function MissionsPage() {
  const t = useTranslations();
  const [missions, setMissions] = useState<MissionSummary[]>([]);
  const [runResult, setRunResult] = useState<RunResponse | null>(null);
  const [running, setRunning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const data = await api.listMissions();
      setMissions(data.missions);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("missions.errors.load"));
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleRun = async (name: string) => {
    setRunning(name);
    setRunResult(null);
    try {
      const result = await api.runMission(name);
      setRunResult(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("missions.errors.run"));
    } finally {
      setRunning(null);
    }
  };

  const handleReload = async () => {
    try {
      await api.reloadMissions();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("missions.errors.reload"));
    }
  };

  return (
    <DashboardShell>
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="space-y-5 max-w-[1600px] mx-auto"
      >
        {/* Header row */}
        <motion.div
          variants={itemVariants}
          className="flex items-center justify-between"
        >
          <div className="flex items-center gap-3">
            <Rocket className="h-5 w-5 text-blue-400" />
            <div>
              <p className="text-sm font-semibold">
                {t("missions.loadedCount", { count: missions.length })}
              </p>
              <p className="text-xs text-muted-foreground">
                {t("missions.subtitle")}
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleReload}
            className="border-border hover:bg-accent"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            {t("common.reload")}
          </Button>
        </motion.div>

        {/* Error */}
        {error && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-4"
            style={{ "--glow": NEON.pink } as React.CSSProperties}
          >
            <p className="text-sm text-red-400">{error}</p>
          </motion.div>
        )}

        {/* Mission cards grid */}
        <div className="grid gap-4">
          {missions.map((m) => {
            const tier = TIER_COLORS[m.agent_tier] || TIER_COLORS.balanced;
            return (
              <motion.div
                key={m.name}
                variants={itemVariants}
                whileHover={{
                  y: -3,
                  boxShadow: "0 0 20px rgba(59,130,246,0.12)",
                }}
                className="glass-card neon-card p-5"
                style={{ "--glow": NEON.blue } as React.CSSProperties}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <Link
                      href={`/missions/${encodeURIComponent(m.name)}`}
                      className="flex items-center gap-2 hover:opacity-80 transition-opacity no-underline"
                    >
                      <Bot className="h-5 w-5 text-cyan-400" />
                      <h3 className="font-semibold text-base text-foreground">
                        {m.name}
                      </h3>
                    </Link>
                    <p className="text-sm text-muted-foreground mt-1">
                      {m.description || t("common.noDescription")}
                    </p>
                    <div className="flex items-center gap-3 mt-3">
                      <span
                        className={`text-[11px] px-2.5 py-0.5 rounded-full font-medium ${tier.bg} ${tier.text}`}
                      >
                        {m.agent_tier}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {t("missions.stepsCount", { count: m.steps_count })}
                      </span>
                      {m.schedule && (
                        <Badge
                          variant="outline"
                          className="font-mono text-xs border-border"
                        >
                          {m.schedule}
                        </Badge>
                      )}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    onClick={() => handleRun(m.name)}
                    disabled={running === m.name}
                    className="bg-primary hover:bg-primary/90"
                  >
                    <Play className="h-4 w-4 mr-1" />
                    {running === m.name ? t("common.running") : t("common.run")}
                  </Button>
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Run result */}
        {runResult && (
          <motion.div
            variants={itemVariants}
            initial="hidden"
            animate="show"
            className="glass-card neon-card p-5"
            style={
              {
                "--glow":
                  runResult.status === "success" ? NEON.green : NEON.pink,
              } as React.CSSProperties
            }
          >
            <h4 className="text-sm font-semibold mb-3">
              {t("missions.run.title")}{" "}
              <span className="text-foreground">{runResult.mission_name}</span>{" "}
              —{" "}
              <span
                className={
                  runResult.status === "success"
                    ? "text-emerald-400"
                    : "text-red-400"
                }
              >
                {runResult.status === "success"
                  ? t("common.success")
                  : runResult.status === "failed"
                    ? t("common.failed")
                    : runResult.status}
              </span>
            </h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground text-xs">
                  {t("missions.run.steps")}
                </span>
                <p className="font-semibold">
                  {runResult.steps_completed}/{runResult.total_steps}
                </p>
              </div>
              <div>
                <span className="text-muted-foreground text-xs">
                  {t("missions.run.duration")}
                </span>
                <p className="font-semibold">{runResult.duration_ms}ms</p>
              </div>
              <div>
                <span className="text-muted-foreground text-xs">
                  {t("missions.run.tokens")}
                </span>
                <p className="font-semibold">{runResult.tokens_used}</p>
              </div>
              <div>
                <span className="text-muted-foreground text-xs">
                  {t("missions.run.cost")}
                </span>
                <p className="font-semibold">
                  ${runResult.cost_usd.toFixed(4)}
                </p>
              </div>
            </div>
            {runResult.logs.length > 0 && (
              <div className="mt-3 p-3 rounded-lg bg-muted/30 border border-border text-xs font-mono space-y-1">
                {runResult.logs.map((log, i) => (
                  <div key={i} className="text-muted-foreground">
                    {log}
                  </div>
                ))}
              </div>
            )}
            {runResult.error_message && (
              <p className="mt-2 text-red-400 text-sm">
                {runResult.error_message}
              </p>
            )}
          </motion.div>
        )}
      </motion.div>
    </DashboardShell>
  );
}
