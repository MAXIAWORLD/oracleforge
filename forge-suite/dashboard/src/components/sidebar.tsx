"use client";

import { LayoutDashboard, Flame } from "lucide-react";
import { useTranslations } from "next-intl";
import { PRODUCTS } from "@/lib/products";

interface SidebarProps {
  readonly activeTab: string;
  readonly onSelectTab: (tab: string) => void;
}

export function Sidebar({ activeTab, onSelectTab }: SidebarProps) {
  const t = useTranslations();

  return (
    <aside className="w-[200px] min-h-screen border-r border-border bg-card/50 dark:bg-[rgba(7,10,20,0.8)] flex flex-col shrink-0">
      {/* Logo */}
      <div className="p-5 border-b border-border">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-neon-cyan via-neon-violet to-neon-pink flex items-center justify-center">
            <Flame className="h-4 w-4 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight">
              {t("brand.name")}
            </h1>
            <p className="text-[10px] text-muted-foreground">
              {t("brand.tagline")}
            </p>
          </div>
        </div>
      </div>

      {/* Main Nav */}
      <nav className="flex-1 p-3 space-y-1">
        <p className="text-[10px] uppercase tracking-widest text-muted-foreground px-2 mb-2">
          {t("nav.navigation")}
        </p>
        <button
          type="button"
          onClick={() => onSelectTab("overview")}
          className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all duration-200 ${
            activeTab === "overview"
              ? "bg-primary/10 text-primary dark:bg-primary/15 dark:text-neon-cyan"
              : "text-muted-foreground hover:text-foreground hover:bg-accent"
          }`}
        >
          <LayoutDashboard className="h-4 w-4" />
          {t("nav.overview")}
        </button>

        {/* Product Links — switch tabs */}
        <div className="mt-6">
          <p className="text-[10px] uppercase tracking-widest text-muted-foreground px-2 mb-2">
            {t("nav.products")}
          </p>
          {PRODUCTS.map((product) => {
            const Icon = product.icon;
            const isActive = activeTab === product.id;
            return (
              <button
                key={product.id}
                type="button"
                onClick={() => onSelectTab(product.id)}
                className={`w-full flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-xs transition-all duration-200 ${
                  isActive
                    ? "bg-primary/10 text-primary dark:bg-primary/15"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent"
                }`}
                style={isActive ? { color: product.glowColor } : undefined}
              >
                <Icon
                  className={`h-3.5 w-3.5 ${isActive ? "" : product.color}`}
                />
                <span className="flex-1 truncate text-left">
                  {t(`products.${product.id}.name`)}
                </span>
              </button>
            );
          })}
        </div>
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-border">
        <p className="text-[10px] text-muted-foreground text-center">v1.0.0</p>
      </div>
    </aside>
  );
}
