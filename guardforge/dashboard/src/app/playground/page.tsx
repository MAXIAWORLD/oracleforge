"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useTranslations } from "next-intl";
import {
  Play,
  RotateCcw,
  Sparkles,
  Lock,
  Unlock,
  AlertTriangle,
  Activity,
  Info,
  Copy,
  Check,
} from "lucide-react";
import { DashboardShell } from "@/components/dashboard-shell";
import { api, type TokenizeResponse, type ScanEntity } from "@/lib/api";

const NEON = {
  cyan: "#00e5ff",
  violet: "#b44aff",
  pink: "#ff2d87",
  green: "#0afe7e",
  amber: "#ffb800",
} as const;

const SAMPLE_TEXT =
  "Bonjour, je suis M. Jean Dupont, mon SIRET est 12345678901234 et mon email jean@example.fr. Mon IBAN: FR7630006000011234567890189";

const RISK_CONFIG: Record<string, { color: string; bg: string }> = {
  critical: { color: NEON.pink, bg: `${NEON.pink}18` },
  high: { color: "#f97316", bg: "#f9731618" },
  medium: { color: NEON.cyan, bg: `${NEON.cyan}18` },
  low: { color: NEON.green, bg: `${NEON.green}18` },
};

function getRisk(level: string) {
  return RISK_CONFIG[level?.toLowerCase()] ?? RISK_CONFIG.medium;
}

/** Highlights [TOKEN_xxxx] patterns with neon cyan */
function TokenHighlight({ text }: { text: string }) {
  const parts = text.split(/(\[[A-Z_]+_[a-f0-9]+\])/g);
  return (
    <span>
      {parts.map((part, i) => {
        if (/^\[[A-Z_]+_[a-f0-9]+\]$/.test(part)) {
          return (
            <span
              key={i}
              className="font-bold rounded px-0.5"
              style={{ color: NEON.cyan, backgroundColor: `${NEON.cyan}18` }}
            >
              {part}
            </span>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </span>
  );
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

export default function PlaygroundPage() {
  const t = useTranslations("playground");
  const tRisk = useTranslations("risk");

  const [inputText, setInputText] = useState("");
  const [tokenizeResult, setTokenizeResult] = useState<TokenizeResponse | null>(null);
  const [restoredText, setRestoredText] = useState<string | null>(null);
  const [tokenizing, setTokenizing] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [isOffline, setIsOffline] = useState(false);

  const handleTokenize = async () => {
    if (!inputText.trim()) return;
    setTokenizing(true);
    setError("");
    setTokenizeResult(null);
    setRestoredText(null);
    setIsOffline(false);
    try {
      const result = await api.tokenize(inputText);
      setTokenizeResult(result);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Tokenization failed";
      if (msg.includes("fetch") || msg.includes("network") || msg.includes("offline")) {
        setIsOffline(true);
      }
      setError(msg);
    } finally {
      setTokenizing(false);
    }
  };

  const handleRestore = async () => {
    if (!tokenizeResult) return;
    setRestoring(true);
    setError("");
    try {
      const result = await api.detokenize(tokenizeResult.tokenized_text, tokenizeResult.session_id);
      setRestoredText(result.original_text);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Restore failed";
      setError(msg);
    } finally {
      setRestoring(false);
    }
  };

  const handleReset = () => {
    setInputText("");
    setTokenizeResult(null);
    setRestoredText(null);
    setError("");
    setIsOffline(false);
  };

  const handleCopyTokenized = async () => {
    if (!tokenizeResult?.tokenized_text) return;
    try {
      await navigator.clipboard.writeText(tokenizeResult.tokenized_text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard unavailable
    }
  };

  return (
    <DashboardShell>
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="space-y-5 max-w-[1200px] mx-auto"
      >
        {/* Title */}
        <motion.div variants={itemVariants}>
          <h1 className="text-xl font-bold tracking-tight">{t("title")}</h1>
          <p className="text-sm text-muted-foreground mt-1">{t("subtitle")}</p>
        </motion.div>

        {/* Backend offline empty state */}
        {isOffline && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-10 text-center"
            style={{ "--glow": NEON.amber } as React.CSSProperties}
          >
            <AlertTriangle className="w-10 h-10 text-amber-400 mx-auto mb-3" />
            <p className="text-sm font-semibold text-amber-400">{t("backend_offline")}</p>
            <p className="text-xs text-muted-foreground mt-1">
              {t("backend_offline_hint")}
            </p>
          </motion.div>
        )}

        {/* Input card */}
        <motion.div
          variants={itemVariants}
          className="glass-card neon-card p-6"
          style={{ "--glow": NEON.violet } as React.CSSProperties}
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-violet-400" />
              <h2 className="text-sm font-semibold">{t("input_label")}</h2>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setInputText(SAMPLE_TEXT)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-card border border-border text-muted-foreground hover:text-foreground hover:bg-accent transition-all"
              >
                {t("sample_btn")}
              </button>
              {(tokenizeResult || inputText) && (
                <button
                  onClick={handleReset}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-card border border-border text-muted-foreground hover:text-foreground hover:bg-accent transition-all"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  {t("reset_btn")}
                </button>
              )}
            </div>
          </div>

          <textarea
            className="w-full h-36 rounded-xl border border-border bg-background/50 dark:bg-[#0d1020]/60 px-4 py-3 text-sm font-mono resize-none focus:outline-none focus:ring-2 focus:ring-violet-500/40 transition-all placeholder:text-muted-foreground/50"
            placeholder={t("paste_placeholder")}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
          />

          <div className="flex justify-end mt-3">
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleTokenize}
              disabled={tokenizing || !inputText.trim()}
              className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-violet-500 to-purple-600 text-white text-sm font-semibold transition-all disabled:opacity-40 disabled:cursor-not-allowed hover:shadow-[0_0_20px_rgba(180,74,255,0.3)]"
            >
              {tokenizing ? (
                <span className="flex items-center gap-2">
                  <Activity className="w-4 h-4 animate-spin" />
                  {t("tokenizing")}
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <Play className="w-4 h-4" />
                  {t("tokenize_btn")}
                </span>
              )}
            </motion.button>
          </div>
        </motion.div>

        {/* Error */}
        {error && !isOffline && (
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

        {/* Results: 2 columns */}
        <AnimatePresence>
          {tokenizeResult && (
            <motion.div
              key="result-cols"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ type: "spring", stiffness: 300, damping: 24 }}
              className="grid grid-cols-1 md:grid-cols-2 gap-5"
            >
              {/* Left: tokenized */}
              <div
                className="glass-card neon-card p-5"
                style={{ "--glow": NEON.cyan } as React.CSSProperties}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Lock className="w-4 h-4 text-cyan-400" />
                    <h3 className="text-sm font-semibold">{t("tokenized_label")}</h3>
                    <span className="px-2 py-0.5 rounded-full text-[9px] font-bold bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 uppercase tracking-wider">
                      {t("safe_badge")}
                    </span>
                  </div>
                  <button
                    onClick={handleCopyTokenized}
                    className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-medium bg-card border border-border text-muted-foreground hover:text-foreground transition-all"
                  >
                    {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    {copied ? t("copied_btn") : t("copy_btn")}
                  </button>
                </div>
                <div className="rounded-xl border border-border bg-background/50 dark:bg-[#0d1020]/60 p-3 font-mono text-sm leading-relaxed min-h-[100px]">
                  <TokenHighlight text={tokenizeResult.tokenized_text} />
                </div>
                <div className="flex items-center justify-between mt-2">
                  <span className="text-[10px] text-muted-foreground font-mono">
                    session: {tokenizeResult.session_id.slice(0, 18)}…
                  </span>
                  <span className="text-[10px] text-muted-foreground">
                    {tokenizeResult.token_count} token{tokenizeResult.token_count !== 1 ? "s" : ""}
                  </span>
                </div>
              </div>

              {/* Right: restored */}
              <div
                className="glass-card neon-card p-5"
                style={{ "--glow": restoredText ? NEON.green : NEON.amber } as React.CSSProperties}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Unlock className="w-4 h-4" style={{ color: restoredText ? NEON.green : "#6b7194" }} />
                    <h3 className="text-sm font-semibold">{t("restored_label")}</h3>
                  </div>
                </div>

                {restoredText ? (
                  <div className="rounded-xl border border-border bg-background/50 dark:bg-[#0d1020]/60 p-3 font-mono text-sm leading-relaxed min-h-[100px]"
                    style={{ color: NEON.green }}
                  >
                    {restoredText}
                  </div>
                ) : (
                  <div className="rounded-xl border border-dashed border-border bg-background/30 p-3 min-h-[100px] flex flex-col items-center justify-center gap-3">
                    <div className="text-center">
                      <Lock className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
                      <p className="text-xs text-muted-foreground">
                        {t("click_restore")}
                      </p>
                    </div>
                    <motion.button
                      whileHover={{ scale: 1.03 }}
                      whileTap={{ scale: 0.97 }}
                      onClick={handleRestore}
                      disabled={restoring}
                      className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-500 to-green-600 text-white text-xs font-semibold disabled:opacity-40 disabled:cursor-not-allowed hover:shadow-[0_0_16px_rgba(10,254,126,0.25)]"
                    >
                      {restoring ? (
                        <>
                          <Activity className="w-3.5 h-3.5 animate-spin" />
                          {t("restoring")}
                        </>
                      ) : (
                        <>
                          <Unlock className="w-3.5 h-3.5" />
                          {t("restore_btn")}
                        </>
                      )}
                    </motion.button>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Entities detected */}
        {tokenizeResult && tokenizeResult.entities.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card neon-card p-5"
            style={{ "--glow": NEON.amber } as React.CSSProperties}
          >
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
              {tokenizeResult.entities.length} {t("entities_detected")}
            </p>
            <div className="flex flex-wrap gap-2">
              {tokenizeResult.entities.map((entity: ScanEntity, i: number) => {
                const riskCfg = getRisk(entity.risk_level);
                return (
                  <div
                    key={i}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-semibold"
                    style={{
                      color: riskCfg.color,
                      borderColor: `${riskCfg.color}40`,
                      backgroundColor: riskCfg.bg,
                    }}
                  >
                    <span>{entity.type}</span>
                    <span className="opacity-60">·</span>
                    <span className="uppercase text-[9px] tracking-wider">
                      {tRisk(entity.risk_level as Parameters<typeof tRisk>[0])}
                    </span>
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}

        {/* Why this matters explainer */}
        <motion.div
          variants={itemVariants}
          className="glass-card neon-card p-5"
          style={{ "--glow": NEON.cyan } as React.CSSProperties}
        >
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center shrink-0 mt-0.5">
              <Info className="w-4 h-4 text-cyan-400" />
            </div>
            <div>
              <h3 className="text-sm font-semibold mb-1">{t("why_matters")}</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {t("explainer_body")}
              </p>
              <div className="flex items-center gap-6 mt-3">
                {[
                  { step: "1", label: t("step_1"), color: NEON.violet },
                  { step: "2", label: t("step_2"), color: NEON.cyan },
                  { step: "3", label: t("step_3"), color: NEON.green },
                ].map(({ step, label, color }) => (
                  <div key={step} className="flex items-center gap-1.5">
                    <span
                      className="w-5 h-5 rounded-full text-[10px] font-bold flex items-center justify-center"
                      style={{ backgroundColor: `${color}25`, color }}
                    >
                      {step}
                    </span>
                    <span className="text-xs text-muted-foreground">{label}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </DashboardShell>
  );
}
