"use client";

import { motion } from "framer-motion";
import { ArrowRight, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { PRODUCTS } from "@/lib/products";

interface QuickActionsProps {
  readonly onRefresh: () => void;
  readonly onOpen: (productId: string) => void;
}

export function QuickActions({ onRefresh, onOpen }: QuickActionsProps) {
  const t = useTranslations();

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {t("hub.quickActions")}
        </h3>
        <button
          type="button"
          onClick={onRefresh}
          className="flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
        >
          <RefreshCw className="h-3 w-3" />
          {t("hub.refreshAll")}
        </button>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
        {PRODUCTS.map((product, i) => {
          const Icon = product.icon;
          return (
            <motion.button
              key={product.id}
              type="button"
              onClick={() => onOpen(product.id)}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05, duration: 0.3 }}
              className="glass-card neon-card p-3 flex items-center gap-2.5 group hover:cursor-pointer text-left"
              style={{ "--glow": product.glowColor } as React.CSSProperties}
            >
              <Icon className={`h-4 w-4 ${product.color} shrink-0`} />
              <span className="text-xs font-medium truncate">
                {t(`products.${product.id}.name`)}
              </span>
              <ArrowRight className="h-3 w-3 ml-auto opacity-0 group-hover:opacity-60 transition-opacity shrink-0" />
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}
