"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Activity, LayoutDashboard, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { Sidebar } from "@/components/sidebar";
import { ThemeToggle } from "@/components/theme-toggle";
import { LanguageSwitcher } from "@/components/language-switcher";
import { ProductCard } from "@/components/product-card";
import { HealthGauge } from "@/components/health-gauge";
import { StatusBar } from "@/components/status-bar";
import { QuickActions } from "@/components/quick-actions";
import { useHealthPolling } from "@/lib/use-health";
import { useClock } from "@/lib/use-clock";
import { PRODUCTS } from "@/lib/products";

export default function Home() {
  const {
    healthMap,
    loading,
    healthyCount,
    totalCount,
    healthPercent,
    refresh,
  } = useHealthPolling(30_000);
  const clock = useClock();
  const [activeTab, setActiveTab] = useState<string>("overview");
  // Track which product tabs have been opened so they stay mounted (instant switch)
  const [openedProducts, setOpenedProducts] = useState<Set<string>>(new Set());
  const t = useTranslations();

  const handleSelectTab = (tab: string) => {
    setActiveTab(tab);
    if (tab !== "overview") {
      setOpenedProducts((prev) => {
        if (prev.has(tab)) return prev;
        const next = new Set(prev);
        next.add(tab);
        return next;
      });
    }
  };

  const handleCloseTab = (productId: string) => {
    setOpenedProducts((prev) => {
      const next = new Set(prev);
      next.delete(productId);
      return next;
    });
    if (activeTab === productId) setActiveTab("overview");
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <Sidebar activeTab={activeTab} onSelectTab={handleSelectTab} />

      {/* Main Panel */}
      <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
        {/* Header */}
        <header className="h-16 shrink-0 flex items-center justify-between px-6 border-b border-border bg-card/30 dark:bg-transparent">
          <div className="flex items-center gap-4">
            <h1 className="text-lg font-bold tracking-tight">
              {t("brand.name")}
            </h1>
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-neon-green/10 border border-neon-green/20">
              <div
                className="w-1.5 h-1.5 rounded-full neon-pulse"
                style={
                  {
                    backgroundColor: "#0afe7e",
                    "--pulse-color": "#0afe7e",
                  } as React.CSSProperties
                }
              />
              <span className="text-[10px] font-semibold text-neon-green uppercase tracking-wider">
                {t("shell.live")}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Activity className="h-3.5 w-3.5" />
              <span className="text-xs font-mono">{clock}</span>
            </div>
            <LanguageSwitcher />
            <ThemeToggle />
          </div>
        </header>

        {/* Tabs Bar */}
        <div className="shrink-0 flex items-center gap-1 px-4 h-11 border-b border-border bg-card/20 dark:bg-[rgba(7,10,20,0.5)] overflow-x-auto scrollbar-thin">
          {/* Overview Tab */}
          <button
            type="button"
            onClick={() => handleSelectTab("overview")}
            className={`shrink-0 flex items-center gap-2 px-3 h-8 rounded-lg text-xs font-medium transition-all duration-200 ${
              activeTab === "overview"
                ? "bg-primary/10 text-primary dark:bg-primary/15 dark:text-neon-cyan border border-primary/20 dark:border-neon-cyan/30"
                : "text-muted-foreground hover:text-foreground hover:bg-accent"
            }`}
          >
            <LayoutDashboard className="h-3.5 w-3.5" />
            {t("nav.overview")}
          </button>

          {/* Product tabs — show only opened ones */}
          {PRODUCTS.filter((p) => openedProducts.has(p.id)).map((product) => {
            const Icon = product.icon;
            const isActive = activeTab === product.id;
            const health = healthMap.get(product.id);
            const isHealthy = health?.healthy ?? false;
            return (
              <div
                key={product.id}
                className={`shrink-0 flex items-center gap-1 h-8 rounded-lg transition-all duration-200 border ${
                  isActive
                    ? "bg-accent/60 border-border"
                    : "border-transparent hover:bg-accent/40"
                }`}
                style={
                  isActive
                    ? { borderColor: `${product.glowColor}40` }
                    : undefined
                }
              >
                <button
                  type="button"
                  onClick={() => setActiveTab(product.id)}
                  className="flex items-center gap-2 px-3 h-full text-xs font-medium"
                  style={isActive ? { color: product.glowColor } : undefined}
                >
                  <Icon
                    className={`h-3.5 w-3.5 ${isActive ? "" : product.color}`}
                  />
                  <span>{t(`products.${product.id}.name`)}</span>
                  <span
                    className="w-1.5 h-1.5 rounded-full"
                    style={{
                      backgroundColor: isHealthy ? "#0afe7e" : "#ff3b5c",
                    }}
                  />
                </button>
                <button
                  type="button"
                  onClick={() => handleCloseTab(product.id)}
                  className="h-full pr-2 pl-1 text-muted-foreground hover:text-foreground transition-colors"
                  aria-label={t("hub.closeTab", {
                    name: t(`products.${product.id}.name`),
                  })}
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            );
          })}
        </div>

        {/* Content Area */}
        <main className="flex-1 relative overflow-hidden">
          {/* Overview Panel */}
          <div
            className={`absolute inset-0 overflow-auto scrollbar-thin p-6 ${
              activeTab === "overview" ? "block" : "hidden"
            }`}
          >
            <div className="max-w-7xl mx-auto space-y-6">
              {/* Row 1: Product Health Cards */}
              <section>
                <div className="flex items-center gap-2 mb-4">
                  <h2 className="text-sm font-semibold">
                    {t("hub.productHealth")}
                  </h2>
                  {loading && (
                    <span className="text-[10px] text-muted-foreground animate-pulse">
                      {t("hub.checking")}
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {PRODUCTS.map((product, i) => (
                    <ProductCard
                      key={product.id}
                      product={product}
                      health={healthMap.get(product.id)}
                      index={i}
                      onOpen={handleSelectTab}
                    />
                  ))}
                </div>
              </section>

              {/* Row 2: Suite Overview */}
              <section>
                <h2 className="text-sm font-semibold mb-4">
                  {t("hub.suiteOverview")}
                </h2>
                <div className="glass-card p-6">
                  <div className="flex flex-col lg:flex-row items-center gap-8">
                    <HealthGauge
                      percent={healthPercent}
                      healthyCount={healthyCount}
                      totalCount={totalCount}
                    />
                    <div className="flex-1 grid grid-cols-3 gap-6">
                      <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.5 }}
                        className="text-center"
                      >
                        <p
                          className="text-3xl font-bold font-mono neon-value"
                          style={{ "--glow": "#0afe7e" } as React.CSSProperties}
                        >
                          {healthyCount}
                        </p>
                        <p className="text-[11px] text-muted-foreground mt-1">
                          {t("hub.healthy")}
                        </p>
                      </motion.div>
                      <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.6 }}
                        className="text-center"
                      >
                        <p
                          className="text-3xl font-bold font-mono neon-value"
                          style={{ "--glow": "#ff3b5c" } as React.CSSProperties}
                        >
                          {totalCount - healthyCount}
                        </p>
                        <p className="text-[11px] text-muted-foreground mt-1">
                          {t("hub.down")}
                        </p>
                      </motion.div>
                      <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.7 }}
                        className="text-center"
                      >
                        <p
                          className="text-3xl font-bold font-mono neon-value"
                          style={{ "--glow": "#3b82f6" } as React.CSSProperties}
                        >
                          {totalCount}
                        </p>
                        <p className="text-[11px] text-muted-foreground mt-1">
                          {t("hub.total")}
                        </p>
                      </motion.div>
                    </div>
                    <div className="flex-1 w-full lg:w-auto">
                      <StatusBar healthMap={healthMap} />
                    </div>
                  </div>
                </div>
              </section>

              {/* Row 3: Quick Actions */}
              <section>
                <QuickActions onRefresh={refresh} onOpen={handleSelectTab} />
              </section>
            </div>
          </div>

          {/* Product iframes — mounted once opened, kept mounted for instant switch */}
          {PRODUCTS.filter((p) => openedProducts.has(p.id)).map((product) => (
            <iframe
              key={product.id}
              src={`http://localhost:${product.dashboardPort}`}
              title={t(`products.${product.id}.name`)}
              className={`absolute inset-0 w-full h-full border-0 bg-background ${
                activeTab === product.id ? "block" : "hidden"
              }`}
            />
          ))}
        </main>
      </div>
    </div>
  );
}
