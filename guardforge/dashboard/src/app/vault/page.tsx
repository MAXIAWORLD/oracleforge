"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { useTranslations } from "next-intl";
import {
  ShieldCheck,
  Lock,
  Activity,
  AlertTriangle,
  KeyRound,
  Trash2,
  Plus,
  Database,
  ShieldAlert,
} from "lucide-react";
import { DashboardShell } from "@/components/dashboard-shell";

const NEON = {
  cyan: "#00e5ff",
  violet: "#b44aff",
  pink: "#ff2d87",
  green: "#0afe7e",
  amber: "#ffb800",
  blue: "#3b82f6",
} as const;

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8004";

interface HealthData {
  vault_entries: number;
  policies_loaded: number;
  version: string;
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

export default function VaultPage() {
  const t = useTranslations("vault");

  const [isOnline, setIsOnline] = useState(false);
  const [healthData, setHealthData] = useState<HealthData | null>(null);

  // Vault key management
  const [vaultKeys, setVaultKeys] = useState<string[]>([]);
  const [keysLoading, setKeysLoading] = useState(false);
  const [keysError, setKeysError] = useState("");
  const [vaultAvailable, setVaultAvailable] = useState(false);

  // Store secret form
  const [storeKey, setStoreKey] = useState("");
  const [storeValue, setStoreValue] = useState("");
  const [storing, setStoring] = useState(false);
  const [storeError, setStoreError] = useState("");
  const [storeSuccess, setStoreSuccess] = useState("");

  // Delete state
  const [deleting, setDeleting] = useState<string | null>(null);

  const authHeaders = {
    "Content-Type": "application/json",
    "X-API-Key": process.env.NEXT_PUBLIC_API_KEY || "",
    Authorization: `Bearer ${process.env.NEXT_PUBLIC_SECRET_KEY || ""}`,
  };

  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (res.ok) {
        const data: HealthData = await res.json();
        setIsOnline(true);
        setHealthData(data);
      } else {
        setIsOnline(false);
      }
    } catch {
      setIsOnline(false);
    }
  }, []);

  const fetchVaultKeys = useCallback(async () => {
    setKeysLoading(true);
    setKeysError("");
    try {
      const res = await fetch(`${API_BASE}/api/vault/keys`, {
        headers: authHeaders,
      });
      if (res.status === 401) {
        setKeysError("Authentication required. Set NEXT_PUBLIC_SECRET_KEY in your .env file.");
        setVaultAvailable(false);
        return;
      }
      if (res.status === 503) {
        setKeysError("Vault is not available. Encryption key may not be configured.");
        setVaultAvailable(false);
        return;
      }
      if (!res.ok) {
        throw new Error(`Failed to fetch vault keys: ${res.statusText}`);
      }
      const data = await res.json();
      setVaultKeys(data.keys || []);
      setVaultAvailable(true);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Failed to load vault keys";
      setKeysError(message);
      setVaultAvailable(false);
    } finally {
      setKeysLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    checkHealth();
    fetchVaultKeys();
  }, [checkHealth, fetchVaultKeys]);

  const handleStore = async () => {
    if (!storeKey.trim() || !storeValue.trim()) return;
    setStoring(true);
    setStoreError("");
    setStoreSuccess("");
    try {
      const res = await fetch(`${API_BASE}/api/vault/store`, {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({ key: storeKey, value: storeValue }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || res.statusText);
      }
      setStoreSuccess(t("storeSuccessMessage", { key: storeKey }));
      setStoreKey("");
      setStoreValue("");
      fetchVaultKeys();
      setTimeout(() => setStoreSuccess(""), 3000);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Failed to store secret";
      setStoreError(message);
    } finally {
      setStoring(false);
    }
  };

  const handleDelete = async (key: string) => {
    setDeleting(key);
    try {
      const res = await fetch(`${API_BASE}/api/vault/delete/${encodeURIComponent(key)}`, {
        method: "DELETE",
        headers: authHeaders,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || res.statusText);
      }
      fetchVaultKeys();
    } catch {
      // Silently fail for now (toast in future)
    } finally {
      setDeleting(null);
    }
  };

  // isOnline used for conditional rendering
  void isOnline;

  return (
    <DashboardShell>
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="space-y-5 max-w-[1200px] mx-auto"
      >
        {/* Vault status */}
        <motion.div variants={itemVariants} className="grid grid-cols-3 gap-4">
          <motion.div
            whileHover={{ y: -4, boxShadow: `0 0 24px ${NEON.amber}25` }}
            className="glass-card neon-card p-5"
            style={{ "--glow": NEON.amber } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 mb-3">
              <Lock className="w-4 h-4 text-amber-400" />
              <span className="text-xs font-medium text-muted-foreground">{t("vaultStatus")}</span>
            </div>
            <p
              className="text-2xl font-bold neon-value"
              style={{ "--glow": vaultAvailable ? NEON.green : NEON.pink } as React.CSSProperties}
            >
              {keysLoading ? "..." : vaultAvailable ? t("available") : t("unavailable")}
            </p>
          </motion.div>

          <motion.div
            whileHover={{ y: -4, boxShadow: `0 0 24px ${NEON.cyan}25` }}
            className="glass-card neon-card p-5"
            style={{ "--glow": NEON.cyan } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 mb-3">
              <KeyRound className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-medium text-muted-foreground">{t("storedSecrets")}</span>
            </div>
            <p
              className="text-2xl font-bold neon-value tabular-nums"
              style={{ "--glow": NEON.cyan } as React.CSSProperties}
            >
              {keysLoading
                ? "..."
                : vaultAvailable
                  ? `${vaultKeys.length}`
                  : healthData
                    ? `${healthData.vault_entries}`
                    : "\u2014"}
            </p>
          </motion.div>

          <motion.div
            whileHover={{ y: -4, boxShadow: `0 0 24px ${NEON.violet}25` }}
            className="glass-card neon-card p-5"
            style={{ "--glow": NEON.violet } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 mb-3">
              <Database className="w-4 h-4 text-violet-400" />
              <span className="text-xs font-medium text-muted-foreground">{t("encryption")}</span>
            </div>
            <p className="text-sm font-semibold text-muted-foreground mt-1">
              AES-256 (Fernet)
            </p>
            <p className="text-[10px] text-muted-foreground/60 mt-1">
              {healthData ? `v${healthData.version}` : "\u2014"}
            </p>
          </motion.div>
        </motion.div>

        {/* Error / auth required */}
        {keysError && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-5"
            style={{ "--glow": NEON.pink } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 text-amber-400">
              <ShieldAlert className="w-5 h-5" />
              <span className="text-sm font-semibold">{t("vaultAccess")}</span>
            </div>
            <p className="text-sm text-muted-foreground mt-2">{keysError}</p>
            <div className="mt-3 rounded-xl border border-border bg-background/50 dark:bg-[#0d1020]/60 p-4">
              <p className="text-xs text-muted-foreground font-mono leading-relaxed">
                # Vault endpoints require Bearer auth:<br />
                # Set NEXT_PUBLIC_SECRET_KEY in your .env.local<br />
                # This must match the SECRET_KEY in backend .env<br /><br />
                NEXT_PUBLIC_SECRET_KEY=your-secret-key-here
              </p>
            </div>
          </motion.div>
        )}

        {/* Store secret form */}
        {vaultAvailable && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-5"
            style={{ "--glow": NEON.green } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 mb-4">
              <Plus className="w-5 h-5 text-emerald-400" />
              <h2 className="text-sm font-semibold">{t("storeSecret")}</h2>
              <span className="ml-auto text-[10px] text-muted-foreground font-mono">
                POST /api/vault/store
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label className="text-xs text-muted-foreground font-medium mb-1.5 block">
                  {t("keyLabel")}
                </label>
                <input
                  type="text"
                  value={storeKey}
                  onChange={(e) => setStoreKey(e.target.value)}
                  placeholder={t("keyPlaceholder")}
                  className="w-full rounded-xl border border-border bg-background/50 dark:bg-[#0d1020]/60 px-4 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-amber-500/40 transition-all placeholder:text-muted-foreground/50"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground font-medium mb-1.5 block">
                  {t("valueLabel")}
                </label>
                <input
                  type="password"
                  value={storeValue}
                  onChange={(e) => setStoreValue(e.target.value)}
                  placeholder={t("valuePlaceholder")}
                  className="w-full rounded-xl border border-border bg-background/50 dark:bg-[#0d1020]/60 px-4 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-amber-500/40 transition-all placeholder:text-muted-foreground/50"
                />
              </div>
            </div>

            {storeError && (
              <div className="flex items-center gap-2 text-red-400 mb-3">
                <AlertTriangle className="w-4 h-4" />
                <span className="text-xs">{storeError}</span>
              </div>
            )}
            {storeSuccess && (
              <div className="flex items-center gap-2 text-emerald-400 mb-3">
                <ShieldCheck className="w-4 h-4" />
                <span className="text-xs">{storeSuccess}</span>
              </div>
            )}

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleStore}
              disabled={storing || !storeKey.trim() || !storeValue.trim()}
              className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 text-white text-sm font-semibold transition-all disabled:opacity-40 disabled:cursor-not-allowed hover:shadow-[0_0_20px_rgba(245,158,11,0.3)]"
            >
              {storing ? (
                <span className="flex items-center gap-2">
                  <Activity className="w-4 h-4 animate-spin" />
                  {t("storing")}
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <Lock className="w-4 h-4" />
                  {t("encryptStore")}
                </span>
              )}
            </motion.button>
          </motion.div>
        )}

        {/* Vault keys list */}
        {vaultAvailable && (
          <motion.div
            variants={itemVariants}
            className="glass-card neon-card p-5"
            style={{ "--glow": NEON.cyan } as React.CSSProperties}
          >
            <div className="flex items-center gap-2 mb-4">
              <KeyRound className="w-5 h-5 text-cyan-400" />
              <h2 className="text-sm font-semibold">{t("storedKeys")}</h2>
              <span className="ml-auto text-[10px] text-muted-foreground font-mono">
                GET /api/vault/keys
              </span>
            </div>

            {keysLoading ? (
              <div className="flex items-center justify-center py-8">
                <Activity className="w-5 h-5 text-muted-foreground animate-spin" />
              </div>
            ) : vaultKeys.length === 0 ? (
              <div className="text-center py-8">
                <Lock className="w-8 h-8 text-muted-foreground/30 mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">{t("noSecretsStored")}</p>
                <p className="text-xs text-muted-foreground/60 mt-1">
                  {t("useFormAbove")}
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {vaultKeys.map((key, i) => (
                  <motion.div
                    key={key}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.04 }}
                    whileHover={{ x: 4 }}
                    className="flex items-center justify-between px-4 py-3 rounded-xl border border-border/50 bg-background/30 dark:bg-[#0d1020]/40 transition-colors hover:border-cyan-500/30"
                  >
                    <div className="flex items-center gap-3">
                      <KeyRound className="w-4 h-4 text-cyan-400" />
                      <span className="text-sm font-mono font-medium">{key}</span>
                    </div>
                    <motion.button
                      whileHover={{ scale: 1.1 }}
                      whileTap={{ scale: 0.9 }}
                      onClick={() => handleDelete(key)}
                      disabled={deleting === key}
                      className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium text-red-400 hover:bg-red-500/10 border border-transparent hover:border-red-500/20 transition-all disabled:opacity-40"
                    >
                      {deleting === key ? (
                        <Activity className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="w-3.5 h-3.5" />
                      )}
                      {t("delete")}
                    </motion.button>
                  </motion.div>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </motion.div>
    </DashboardShell>
  );
}
