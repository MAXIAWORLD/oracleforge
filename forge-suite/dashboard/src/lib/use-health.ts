"use client";

import { useState, useEffect, useCallback } from "react";
import { PRODUCTS, type ProductConfig } from "./products";

export interface ProductHealth {
  readonly productId: string;
  readonly healthy: boolean;
  readonly version: string | null;
  readonly metric: string | null;
  readonly cacheEnabled?: boolean;
  readonly lastChecked: number;
}

async function fetchHealth(product: ProductConfig): Promise<ProductHealth> {
  const now = Date.now();
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);

    const res = await fetch(`http://localhost:${product.backendPort}/health`, {
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (!res.ok) {
      return {
        productId: product.id,
        healthy: false,
        version: null,
        metric: null,
        lastChecked: now,
      };
    }

    const data = await res.json();
    const version = data.version ?? null;

    let metric: string | null = null;
    let cacheEnabled: boolean | undefined;

    if (product.id === "missionforge") {
      metric =
        data.missions_loaded != null ? String(data.missions_loaded) : null;
    } else if (product.id === "llmforge") {
      const providers = data.providers_configured ?? data.providers ?? null;
      cacheEnabled = data.cache_enabled ?? undefined;
      metric = providers != null ? String(providers) : null;
    } else {
      metric = data.status ?? "ok";
    }

    return {
      productId: product.id,
      healthy: true,
      version,
      metric,
      cacheEnabled,
      lastChecked: now,
    };
  } catch {
    return {
      productId: product.id,
      healthy: false,
      version: null,
      metric: null,
      lastChecked: now,
    };
  }
}

export function useHealthPolling(intervalMs: number = 30_000) {
  const [healthMap, setHealthMap] = useState<
    ReadonlyMap<string, ProductHealth>
  >(new Map());
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const results = await Promise.allSettled(PRODUCTS.map(fetchHealth));
    const nextMap = new Map<string, ProductHealth>();
    for (const result of results) {
      if (result.status === "fulfilled") {
        nextMap.set(result.value.productId, result.value);
      }
    }
    setHealthMap(nextMap);
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, intervalMs);
    return () => clearInterval(id);
  }, [refresh, intervalMs]);

  const healthyCount = Array.from(healthMap.values()).filter(
    (h) => h.healthy,
  ).length;
  const totalCount = PRODUCTS.length;
  const healthPercent =
    totalCount > 0 ? Math.round((healthyCount / totalCount) * 100) : 0;

  return {
    healthMap,
    loading,
    healthyCount,
    totalCount,
    healthPercent,
    refresh,
  } as const;
}
