"use client";

import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ProductConfig } from "@/lib/products";
import type { ProductHealth } from "@/lib/use-health";

interface ProductCardProps {
  readonly product: ProductConfig;
  readonly health: ProductHealth | undefined;
  readonly index: number;
  readonly onOpen: (productId: string) => void;
}

export function ProductCard({
  product,
  health,
  index,
  onOpen,
}: ProductCardProps) {
  const t = useTranslations();
  const Icon = product.icon;
  const isHealthy = health?.healthy ?? false;
  const version = health?.version ?? "--";
  const metric = health?.metric ?? "--";
  const cacheEnabled = health?.cacheEnabled;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.4, ease: "easeOut" }}
    >
      <div
        className="glass-card neon-card p-5 h-full flex flex-col gap-4"
        style={{ "--glow": product.glowColor } as React.CSSProperties}
      >
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ backgroundColor: `${product.glowColor}15` }}
            >
              <Icon className={`h-5 w-5 ${product.color}`} />
            </div>
            <div>
              <h3 className="text-sm font-semibold">
                {t(`products.${product.id}.name`)}
              </h3>
              <p className="text-[11px] text-muted-foreground">
                {t(`products.${product.id}.description`)}
              </p>
            </div>
          </div>

          {/* Health Dot */}
          <div className="flex items-center gap-1.5">
            <div
              className={`w-2.5 h-2.5 rounded-full ${isHealthy ? "neon-pulse" : ""}`}
              style={
                {
                  backgroundColor: isHealthy ? "#0afe7e" : "#ff3b5c",
                  "--pulse-color": isHealthy ? "#0afe7e" : "#ff3b5c",
                } as React.CSSProperties
              }
            />
            <span
              className={`text-[10px] font-medium ${isHealthy ? "text-neon-green" : "text-destructive"}`}
            >
              {isHealthy ? t("hub.upStatus") : t("hub.downStatus")}
            </span>
          </div>
        </div>

        {/* Metrics */}
        <div className="flex-1 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-muted-foreground">
              {t("hub.version")}
            </span>
            <span className="text-xs font-mono font-medium">{version}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-muted-foreground">
              {t(`products.${product.id}.metricLabel`)}
            </span>
            <span
              className="text-xs font-mono font-semibold neon-value"
              style={{ "--glow": product.glowColor } as React.CSSProperties}
            >
              {metric}
            </span>
          </div>
          {product.id === "llmforge" && cacheEnabled !== undefined && (
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-muted-foreground">
                {t("common.cache")}
              </span>
              <span
                className={`text-xs font-mono font-medium ${cacheEnabled ? "text-neon-green" : "text-muted-foreground"}`}
              >
                {cacheEnabled ? t("common.enabled") : t("common.disabled")}
              </span>
            </div>
          )}
        </div>

        {/* Footer Button — opens in tab */}
        <button
          type="button"
          onClick={() => onOpen(product.id)}
          className="flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium transition-all duration-200 hover:bg-accent group border border-transparent hover:border-border"
          style={{ color: product.glowColor }}
        >
          {t("hub.openDashboard")}
          <ArrowRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5" />
        </button>
      </div>
    </motion.div>
  );
}
