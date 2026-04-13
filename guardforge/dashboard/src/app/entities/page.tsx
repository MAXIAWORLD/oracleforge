"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { useTranslations } from "next-intl";
import {
  Tag,
  Plus,
  Trash2,
  AlertTriangle,
  Activity,
  CheckCircle2,
} from "lucide-react";
import { DashboardShell } from "@/components/dashboard-shell";

const NEON = {
  cyan: "#00e5ff",
  violet: "#b44aff",
  pink: "#ff2d87",
  green: "#0afe7e",
  amber: "#ffb800",
} as const;

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8004";

interface CustomEntity {
  id: number;
  name: string;
  pattern: string;
  risk_level: "critical" | "high" | "medium" | "low";
  confidence: number;
  description: string;
  enabled: boolean;
  created_at: string | null;
  updated_at: string | null;
}

const RISK_COLORS: Record<string, string> = {
  critical: NEON.pink,
  high: "#f97316",
  medium: NEON.cyan,
  low: NEON.green,
};

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: {
    opacity: 1,
    y: 0,
    transition: { type: "spring" as const, stiffness: 300, damping: 24 },
  },
};

function authHeaders(): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-API-Key": process.env.NEXT_PUBLIC_API_KEY || "",
  };
}

export default function EntitiesPage() {
  const t = useTranslations("entities");

  const [entities, setEntities] = useState<CustomEntity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Form state
  const [name, setName] = useState("");
  const [pattern, setPattern] = useState("");
  const [riskLevel, setRiskLevel] = useState<"critical" | "high" | "medium" | "low">("medium");
  const [confidence, setConfidence] = useState(0.85);
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fetchEntities = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/entities`, { headers: authHeaders() });
      if (!res.ok) throw new Error(`Failed to fetch entities: ${res.statusText}`);
      const data = await res.json();
      setEntities(data.entities || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load entities");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEntities();
  }, [fetchEntities]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const res = await fetch(`${API_BASE}/api/entities`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          name: name.trim(),
          pattern: pattern.trim(),
          risk_level: riskLevel,
          confidence,
          description: description.trim(),
          enabled: true,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || res.statusText);
      }
      setSuccess(t("created_success"));
      setName("");
      setPattern("");
      setDescription("");
      setRiskLevel("medium");
      setConfidence(0.85);
      fetchEntities();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Create failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (entityName: string) => {
    if (!confirm(t("confirm_delete", { name: entityName }))) return;
    setError("");
    setSuccess("");
    try {
      const res = await fetch(`${API_BASE}/api/entities/${entityName}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error(`Delete failed: ${res.statusText}`);
      setSuccess(t("deleted_success"));
      fetchEntities();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  };

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
          style={{ "--glow": NEON.amber } as React.CSSProperties}
        >
          <div className="flex items-center gap-3 mb-2">
            <Tag className="w-6 h-6 text-amber-400" />
            <h1 className="text-xl font-bold">{t("title")}</h1>
          </div>
          <p className="text-sm text-muted-foreground max-w-3xl">{t("subtitle")}</p>
        </motion.div>

        {/* Success / Error messages */}
        {success && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-4"
            style={{ "--glow": NEON.green } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 text-emerald-400">
              <CheckCircle2 className="w-5 h-5" />
              <span className="text-sm font-semibold">{success}</span>
            </div>
          </motion.div>
        )}
        {error && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-4"
            style={{ "--glow": NEON.pink } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 text-red-400">
              <AlertTriangle className="w-5 h-5" />
              <span className="text-sm font-semibold">{error}</span>
            </div>
          </motion.div>
        )}

        {/* Create form */}
        <motion.div
          variants={itemVariants}
          className="glass-card neon-card p-5"
          style={{ "--glow": NEON.violet } as React.CSSProperties}
        >
          <div className="flex items-center gap-2 mb-4">
            <Plus className="w-5 h-5 text-violet-400" />
            <h2 className="text-sm font-semibold">{t("create_title")}</h2>
          </div>
          <form onSubmit={handleCreate} className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">
                  {t("field_name")}
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="internal_ticket_id"
                  pattern="[a-z][a-z0-9_]{2,63}"
                  className="w-full px-3 py-2 rounded-lg text-sm font-mono bg-background/50 dark:bg-[#0d1020]/60 border border-border focus:outline-none focus:ring-2 focus:ring-violet-500/40"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">
                  {t("field_pattern")}
                </label>
                <input
                  type="text"
                  required
                  value={pattern}
                  onChange={(e) => setPattern(e.target.value)}
                  placeholder="TICKET-[0-9]{6}"
                  className="w-full px-3 py-2 rounded-lg text-sm font-mono bg-background/50 dark:bg-[#0d1020]/60 border border-border focus:outline-none focus:ring-2 focus:ring-violet-500/40"
                />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">
                  {t("field_risk")}
                </label>
                <select
                  value={riskLevel}
                  onChange={(e) => setRiskLevel(e.target.value as "critical" | "high" | "medium" | "low")}
                  className="w-full px-3 py-2 rounded-lg text-sm bg-background/50 dark:bg-[#0d1020]/60 border border-border focus:outline-none focus:ring-2 focus:ring-violet-500/40"
                >
                  <option value="critical">critical</option>
                  <option value="high">high</option>
                  <option value="medium">medium</option>
                  <option value="low">low</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">
                  {t("field_confidence")} ({confidence.toFixed(2)})
                </label>
                <input
                  type="range"
                  min="0.5"
                  max="1.0"
                  step="0.05"
                  value={confidence}
                  onChange={(e) => setConfidence(parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">
                  {t("field_description")}
                </label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder={t("field_description_placeholder")}
                  className="w-full px-3 py-2 rounded-lg text-sm bg-background/50 dark:bg-[#0d1020]/60 border border-border focus:outline-none focus:ring-2 focus:ring-violet-500/40"
                />
              </div>
            </div>
            <motion.button
              type="submit"
              disabled={submitting || !name || !pattern}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white text-sm font-semibold disabled:opacity-40 hover:shadow-[0_0_20px_rgba(180,74,255,0.3)]"
            >
              {submitting ? (
                <span className="flex items-center gap-2">
                  <Activity className="w-4 h-4 animate-spin" />
                  {t("creating")}
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <Plus className="w-4 h-4" />
                  {t("create_btn")}
                </span>
              )}
            </motion.button>
          </form>
        </motion.div>

        {/* Loading */}
        {loading && (
          <motion.div variants={itemVariants} className="flex items-center justify-center py-8">
            <Activity className="w-6 h-6 text-muted-foreground animate-spin" />
          </motion.div>
        )}

        {/* Empty state */}
        {!loading && entities.length === 0 && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-12"
            style={{ "--glow": NEON.cyan } as React.CSSProperties}
          >
            <div className="text-center">
              <Tag className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">{t("empty_state")}</p>
            </div>
          </motion.div>
        )}

        {/* List */}
        {!loading && entities.length > 0 && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-5"
            style={{ "--glow": NEON.cyan } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 mb-4">
              <Tag className="w-5 h-5 text-cyan-400" />
              <h2 className="text-sm font-semibold">{t("list_title")}</h2>
              <span className="text-[10px] text-muted-foreground font-mono ml-2">
                GET /api/entities
              </span>
              <span className="ml-auto text-xs text-muted-foreground tabular-nums">
                {entities.length}
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/50">
                    <th className="text-left py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("col_name")}
                    </th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("col_pattern")}
                    </th>
                    <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("col_risk")}
                    </th>
                    <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("col_confidence")}
                    </th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("col_description")}
                    </th>
                    <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("col_actions")}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/30">
                  {entities.map((entity, i) => {
                    const color = RISK_COLORS[entity.risk_level] ?? NEON.cyan;
                    return (
                      <motion.tr
                        key={entity.id}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.03 }}
                        className="hover:bg-accent/30 transition-colors"
                      >
                        <td className="py-3 px-3 font-mono text-xs font-semibold">
                          {entity.name}
                        </td>
                        <td className="py-3 px-3">
                          <code className="text-[11px] text-muted-foreground bg-background/50 dark:bg-[#0d1020]/60 px-2 py-1 rounded">
                            {entity.pattern}
                          </code>
                        </td>
                        <td className="py-3 px-3 text-center">
                          <span
                            className="px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider"
                            style={{
                              color,
                              backgroundColor: `${color}15`,
                              borderWidth: "1px",
                              borderColor: `${color}30`,
                            }}
                          >
                            {entity.risk_level}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-center text-xs font-mono text-muted-foreground">
                          {entity.confidence.toFixed(2)}
                        </td>
                        <td className="py-3 px-3 text-xs text-muted-foreground">
                          {entity.description || "\u2014"}
                        </td>
                        <td className="py-3 px-3 text-center">
                          <motion.button
                            whileHover={{ scale: 1.1 }}
                            whileTap={{ scale: 0.9 }}
                            onClick={() => handleDelete(entity.name)}
                            className="text-pink-400 hover:text-pink-300 transition-colors"
                            aria-label={t("delete_aria")}
                          >
                            <Trash2 className="w-4 h-4" />
                          </motion.button>
                        </td>
                      </motion.tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </motion.div>
        )}
      </motion.div>
    </DashboardShell>
  );
}
