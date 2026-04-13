"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { useTranslations } from "next-intl";
import {
  Webhook as WebhookIcon,
  Plus,
  Trash2,
  Send,
  AlertTriangle,
  Activity,
  CheckCircle2,
  Lock,
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

interface WebhookRow {
  id: number;
  name: string;
  url: string;
  has_secret: boolean;
  min_risk_level: "critical" | "high" | "medium" | "low";
  enabled: boolean;
  created_at: string | null;
  last_triggered_at: string | null;
  failure_count: number;
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

export default function WebhooksPage() {
  const t = useTranslations("webhooks");

  const [webhooks, setWebhooks] = useState<WebhookRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [secret, setSecret] = useState("");
  const [minRisk, setMinRisk] = useState<"critical" | "high" | "medium" | "low">("critical");
  const [submitting, setSubmitting] = useState(false);

  const fetchWebhooks = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/webhooks`, { headers: authHeaders() });
      if (!res.ok) throw new Error(`Failed to fetch webhooks: ${res.statusText}`);
      const data = await res.json();
      setWebhooks(data.webhooks || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load webhooks");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWebhooks();
  }, [fetchWebhooks]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const res = await fetch(`${API_BASE}/api/webhooks`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          name: name.trim(),
          url: url.trim(),
          secret: secret.trim(),
          min_risk_level: minRisk,
          enabled: true,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || res.statusText);
      }
      setSuccess(t("created_success"));
      setName("");
      setUrl("");
      setSecret("");
      setMinRisk("critical");
      fetchWebhooks();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Create failed");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (webhook: WebhookRow) => {
    if (!confirm(t("confirm_delete", { name: webhook.name }))) return;
    setError("");
    setSuccess("");
    try {
      const res = await fetch(`${API_BASE}/api/webhooks/${webhook.id}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error(`Delete failed: ${res.statusText}`);
      setSuccess(t("deleted_success"));
      fetchWebhooks();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  };

  const handleTest = async (webhook: WebhookRow) => {
    setError("");
    setSuccess("");
    try {
      const res = await fetch(`${API_BASE}/api/webhooks/${webhook.id}/test`, {
        method: "POST",
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error(`Test failed: ${res.statusText}`);
      const data = await res.json();
      const ok = data.results?.[0]?.ok;
      const msg = data.results?.[0]?.message || "";
      if (ok) {
        setSuccess(`${t("test_success")}: ${msg}`);
      } else {
        setError(`${t("test_failed")}: ${msg}`);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Test failed");
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
          style={{ "--glow": NEON.violet } as React.CSSProperties}
        >
          <div className="flex items-center gap-3 mb-2">
            <WebhookIcon className="w-6 h-6 text-violet-400" />
            <h1 className="text-xl font-bold">{t("title")}</h1>
          </div>
          <p className="text-sm text-muted-foreground max-w-3xl">{t("subtitle")}</p>
        </motion.div>

        {/* Success / Error */}
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
                  placeholder="Slack security alerts"
                  className="w-full px-3 py-2 rounded-lg text-sm bg-background/50 dark:bg-[#0d1020]/60 border border-border focus:outline-none focus:ring-2 focus:ring-violet-500/40"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">
                  {t("field_url")}
                </label>
                <input
                  type="url"
                  required
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://hooks.slack.com/services/..."
                  className="w-full px-3 py-2 rounded-lg text-sm font-mono bg-background/50 dark:bg-[#0d1020]/60 border border-border focus:outline-none focus:ring-2 focus:ring-violet-500/40"
                />
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">
                  <Lock className="w-3 h-3 inline mr-1" />
                  {t("field_secret")}
                </label>
                <input
                  type="password"
                  value={secret}
                  onChange={(e) => setSecret(e.target.value)}
                  placeholder={t("field_secret_placeholder")}
                  className="w-full px-3 py-2 rounded-lg text-sm font-mono bg-background/50 dark:bg-[#0d1020]/60 border border-border focus:outline-none focus:ring-2 focus:ring-violet-500/40"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted-foreground mb-1">
                  {t("field_min_risk")}
                </label>
                <select
                  value={minRisk}
                  onChange={(e) => setMinRisk(e.target.value as "critical" | "high" | "medium" | "low")}
                  className="w-full px-3 py-2 rounded-lg text-sm bg-background/50 dark:bg-[#0d1020]/60 border border-border focus:outline-none focus:ring-2 focus:ring-violet-500/40"
                >
                  <option value="critical">critical</option>
                  <option value="high">high</option>
                  <option value="medium">medium</option>
                  <option value="low">low</option>
                </select>
              </div>
            </div>
            <motion.button
              type="submit"
              disabled={submitting || !name || !url}
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

        {loading && (
          <motion.div variants={itemVariants} className="flex items-center justify-center py-8">
            <Activity className="w-6 h-6 text-muted-foreground animate-spin" />
          </motion.div>
        )}

        {!loading && webhooks.length === 0 && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-12"
            style={{ "--glow": NEON.cyan } as React.CSSProperties}
          >
            <div className="text-center">
              <WebhookIcon className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">{t("empty_state")}</p>
            </div>
          </motion.div>
        )}

        {!loading && webhooks.length > 0 && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-5"
            style={{ "--glow": NEON.cyan } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 mb-4">
              <WebhookIcon className="w-5 h-5 text-cyan-400" />
              <h2 className="text-sm font-semibold">{t("list_title")}</h2>
              <span className="text-[10px] text-muted-foreground font-mono ml-2">
                GET /api/webhooks
              </span>
              <span className="ml-auto text-xs text-muted-foreground tabular-nums">
                {webhooks.length}
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
                      {t("col_url")}
                    </th>
                    <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("col_secret")}
                    </th>
                    <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("col_min_risk")}
                    </th>
                    <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("col_failures")}
                    </th>
                    <th className="text-center py-2 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      {t("col_actions")}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/30">
                  {webhooks.map((wh, i) => {
                    const color = RISK_COLORS[wh.min_risk_level] ?? NEON.cyan;
                    return (
                      <motion.tr
                        key={wh.id}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.03 }}
                        className="hover:bg-accent/30 transition-colors"
                      >
                        <td className="py-3 px-3 font-semibold text-xs">{wh.name}</td>
                        <td className="py-3 px-3">
                          <code className="text-[11px] text-muted-foreground bg-background/50 dark:bg-[#0d1020]/60 px-2 py-1 rounded truncate inline-block max-w-md">
                            {wh.url}
                          </code>
                        </td>
                        <td className="py-3 px-3 text-center">
                          {wh.has_secret ? (
                            <Lock className="w-3.5 h-3.5 inline text-emerald-400" />
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
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
                            {wh.min_risk_level}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-center text-xs font-mono text-muted-foreground">
                          {wh.failure_count > 0 ? (
                            <span className="text-amber-400">{wh.failure_count}</span>
                          ) : (
                            <span className="text-muted-foreground">0</span>
                          )}
                        </td>
                        <td className="py-3 px-3 text-center">
                          <div className="flex items-center justify-center gap-2">
                            <motion.button
                              whileHover={{ scale: 1.1 }}
                              whileTap={{ scale: 0.9 }}
                              onClick={() => handleTest(wh)}
                              className="text-cyan-400 hover:text-cyan-300 transition-colors"
                              aria-label={t("test_aria")}
                              title={t("test_aria")}
                            >
                              <Send className="w-4 h-4" />
                            </motion.button>
                            <motion.button
                              whileHover={{ scale: 1.1 }}
                              whileTap={{ scale: 0.9 }}
                              onClick={() => handleDelete(wh)}
                              className="text-pink-400 hover:text-pink-300 transition-colors"
                              aria-label={t("delete_aria")}
                              title={t("delete_aria")}
                            >
                              <Trash2 className="w-4 h-4" />
                            </motion.button>
                          </div>
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
