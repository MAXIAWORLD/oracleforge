"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowLeft, Bot, Play } from "lucide-react";
import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DashboardShell,
  NEON,
  containerVariants,
  itemVariants,
} from "@/components/dashboard-shell";
import { api, type MissionDetail, type RunResponse } from "@/lib/api";

export default function MissionDetailPage() {
  const t = useTranslations();
  const params = useParams();
  const name =
    typeof params.name === "string" ? decodeURIComponent(params.name) : "";
  const [mission, setMission] = useState<MissionDetail | null>(null);
  const [runResult, setRunResult] = useState<RunResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!name) return;
    api
      .getMission(name)
      .then(setMission)
      .catch((e) => setError(e.message));
  }, [name]);

  const handleRun = async () => {
    setRunning(true);
    setRunResult(null);
    try {
      const result = await api.runMission(name);
      setRunResult(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("missions.errors.run"));
    } finally {
      setRunning(false);
    }
  };

  if (error) {
    return (
      <DashboardShell>
        <div
          className="glass-card neon-card p-6"
          style={{ "--glow": NEON.pink } as React.CSSProperties}
        >
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      </DashboardShell>
    );
  }

  if (!mission) {
    return (
      <DashboardShell>
        <div className="flex items-center justify-center h-64">
          <p className="text-muted-foreground text-sm">{t("common.loading")}</p>
        </div>
      </DashboardShell>
    );
  }

  return (
    <DashboardShell>
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="space-y-5 max-w-[1600px] mx-auto"
      >
        {/* Header */}
        <motion.div variants={itemVariants} className="flex items-center gap-4">
          <Link
            href="/missions"
            className="text-muted-foreground hover:text-foreground transition-colors"
            aria-label={t("missionDetail.backToMissions")}
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <Bot className="h-5 w-5 text-cyan-400" />
              <h2 className="text-xl font-bold">{mission.name}</h2>
            </div>
            <p className="text-sm text-muted-foreground mt-0.5">
              {mission.description}
            </p>
          </div>
          <Button
            onClick={handleRun}
            disabled={running}
            className="bg-primary hover:bg-primary/90"
          >
            <Play className="h-4 w-4 mr-2" />
            {running ? t("common.running") : t("common.runNow")}
          </Button>
        </motion.div>

        {/* Agent config card */}
        <motion.div
          variants={itemVariants}
          whileHover={{ y: -3, boxShadow: "0 0 20px rgba(180,74,255,0.12)" }}
          className="glass-card neon-card p-5"
          style={{ "--glow": NEON.violet } as React.CSSProperties}
        >
          <h3 className="text-xs font-medium text-muted-foreground mb-3 uppercase tracking-wider">
            {t("missionDetail.agentConfig")}
          </h3>
          <div className="flex items-center gap-3 mb-3">
            <span className="text-[11px] px-2.5 py-0.5 rounded-full font-medium bg-violet-500/15 text-violet-400">
              {mission.agent.llm_tier}
            </span>
            {mission.schedule && (
              <Badge
                variant="outline"
                className="font-mono text-xs border-border"
              >
                {mission.schedule}
              </Badge>
            )}
          </div>
          <div className="p-3 rounded-lg bg-muted/30 border border-border">
            <p className="text-sm text-foreground leading-relaxed">
              {mission.agent.system_prompt}
            </p>
          </div>
        </motion.div>

        {/* Steps card */}
        <motion.div
          variants={itemVariants}
          whileHover={{ y: -3, boxShadow: "0 0 20px rgba(0,229,255,0.12)" }}
          className="glass-card neon-card p-5"
          style={{ "--glow": NEON.cyan } as React.CSSProperties}
        >
          <h3 className="text-xs font-medium text-muted-foreground mb-4 uppercase tracking-wider">
            {t("missionDetail.steps", { count: mission.steps.length })}
          </h3>
          <div className="space-y-3">
            {mission.steps.map((step, i) => (
              <div key={i}>
                {i > 0 && <div className="border-t border-border/50 mb-3" />}
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 w-7 h-7 rounded-full bg-cyan-500/15 text-cyan-400 flex items-center justify-center text-xs font-bold">
                    {i + 1}
                  </div>
                  <div className="flex-1">
                    <span className="text-[11px] px-2.5 py-0.5 rounded-full font-medium bg-blue-500/15 text-blue-400 mb-1 inline-block">
                      {String(step.action)}
                    </span>
                    <pre className="text-xs p-2 rounded-lg mt-1 overflow-x-auto bg-muted/30 border border-border text-muted-foreground">
                      {JSON.stringify(
                        Object.fromEntries(
                          Object.entries(step).filter(
                            ([k, v]) =>
                              k !== "action" &&
                              v !== null &&
                              v !== 500 &&
                              v !== 6 &&
                              v !== "POST",
                          ),
                        ),
                        null,
                        2,
                      )}
                    </pre>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </motion.div>

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
              {t("missionDetail.execution")}{" "}
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
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm mb-3">
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
              <div className="p-3 rounded-lg bg-muted/30 border border-border text-xs font-mono space-y-1">
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
