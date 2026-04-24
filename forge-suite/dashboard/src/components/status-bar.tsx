"use client";

import { motion } from "framer-motion";
import { useTranslations } from "next-intl";
import { PRODUCTS } from "@/lib/products";
import type { ProductHealth } from "@/lib/use-health";

interface StatusBarProps {
  readonly healthMap: ReadonlyMap<string, ProductHealth>;
}

export function StatusBar({ healthMap }: StatusBarProps) {
  const t = useTranslations();

  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {t("hub.productHealth")}
      </h3>
      <div className="flex gap-2">
        {PRODUCTS.map((product, i) => {
          const health = healthMap.get(product.id);
          const isHealthy = health?.healthy ?? false;
          const Icon = product.icon;

          return (
            <motion.div
              key={product.id}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.06, duration: 0.3 }}
              className="flex-1"
            >
              <div
                className="glass-card p-3 flex flex-col items-center gap-2 text-center"
                style={{ "--glow": product.glowColor } as React.CSSProperties}
              >
                <Icon className={`h-4 w-4 ${product.color}`} />
                <span className="text-[10px] font-medium truncate w-full">
                  {product.name.replace("Forge", "")}
                </span>
                <div className="w-full h-1.5 rounded-full bg-muted overflow-hidden">
                  <motion.div
                    className="h-full rounded-full glow-bar"
                    style={{
                      backgroundColor: isHealthy ? "#0afe7e" : "#ff3b5c",
                    }}
                    initial={{ width: 0 }}
                    animate={{ width: isHealthy ? "100%" : "100%" }}
                    transition={{ delay: i * 0.1 + 0.3, duration: 0.6 }}
                  />
                </div>
                <span
                  className={`text-[9px] font-mono ${isHealthy ? "text-neon-green" : "text-destructive"}`}
                >
                  {isHealthy ? t("hub.onlineStatus") : t("hub.offlineStatus")}
                </span>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
