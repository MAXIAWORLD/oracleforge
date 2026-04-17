/**
 * MAXIA Oracle SDK — response and option types.
 *
 * These types mirror the shapes returned by the MAXIA Oracle REST API
 * and the 8 MCP tools. The generic `MaxiaResponse<T>` wraps the server's
 * `{data, disclaimer}` envelope so consumers always see the disclaimer
 * alongside the payload.
 *
 * Data feed only. Not investment advice. No custody. No KYC.
 */

export interface MaxiaResponse<T> {
  data: T;
  disclaimer: string;
}

export interface MaxiaOracleClientOptions {
  /** API key produced by POST /api/register. Falls back to MAXIA_ORACLE_API_KEY env var. */
  apiKey?: string;
  /** Override the backend base URL. Default: https://oracle.maxiaworld.app */
  baseUrl?: string;
  /** Per-request timeout in milliseconds. Default: 15000. */
  timeoutMs?: number;
  /** Inject a fetch implementation (for tests or non-Node runtimes). Default: global fetch. */
  fetch?: typeof globalThis.fetch;
}

export interface RegisteredKey {
  api_key: string;
  tier: string;
  daily_limit: number;
}

export interface HealthPayload {
  status: string;
  env: string;
  uptime_s: number;
}

export interface PriceSource {
  name: string;
  price: number;
  age_s?: number;
  [key: string]: unknown;
}

export interface PricePayload {
  symbol: string;
  price: number;
  sources: PriceSource[];
  source_count: number;
  divergence_pct: number;
}

export interface BatchPricePayload {
  count: number;
  requested: number;
  prices: Record<string, unknown>;
}

export interface SourcesPayload {
  sources: Array<Record<string, unknown>>;
}

export interface SymbolsPayload {
  total_symbols: number;
  all_symbols: string[];
  by_source: {
    pyth_crypto: string[];
    pyth_equity: string[];
    chainlink_base: string[];
    chainlink_ethereum?: string[];
    chainlink_arbitrum?: string[];
    price_oracle: string[];
    /** V1.3 — RedStone has dynamic coverage, always empty here. */
    redstone?: string[];
    /** V1.4 — Pyth on-chain Solana feeds (shard 0 sponsored). */
    pyth_solana?: string[];
    /** V1.5 — Uniswap v3 TWAP pools, per chain. */
    uniswap_v3_base?: string[];
    uniswap_v3_ethereum?: string[];
  };
  /** V1.3 / V1.4 — human-readable notes for dynamic / curated sources. */
  coverage_notes?: Record<string, string>;
}

export interface ChainlinkPayload {
  price: number;
  source: string;
  contract: string;
  decimals?: number;
  round_id?: number;
  updated_at?: number;
  age_s?: number;
  stale?: boolean;
}

export interface ConfidencePayload {
  symbol: string;
  source_count: number | null;
  divergence_pct: number | null;
}

/**
 * V1.3 — RedStone REST public oracle single-source payload.
 */
export interface RedstonePayload {
  price: number;
  publish_time: number;
  age_s: number;
  stale: boolean;
  source: "redstone";
  symbol: string;
  provider: string;
}

/**
 * V1.4 — Pyth native Solana on-chain single-source payload.
 *
 * Emitted by `GET /api/pyth/solana/{symbol}`. Mirrors
 * `services/oracle/pyth_solana_oracle.get_pyth_solana_price` on the
 * backend: the decoded Anchor `PriceUpdateV2` fields with a computed
 * human-readable price + staleness summary.
 */
export interface PythSolanaPayload {
  price: number;
  conf: number;
  confidence_pct: number;
  publish_time: number;
  age_s: number;
  stale: boolean;
  source: "pyth_solana";
  symbol: string;
  price_account: string;
  posted_slot: number;
  exponent: number;
  feed_id: string;
}

/**
 * V1.5 — Uniswap v3 time-weighted average price (TWAP) single-source payload.
 *
 * Emitted by `GET /api/twap/{symbol}?chain=...&window=...`. Mirrors
 * `services/oracle/uniswap_v3_oracle.get_twap_price` on the backend:
 * the tick cumulatives read from `observe()` plus the computed human
 * price and the pool metadata.
 */
export interface UniswapTwapPayload {
  price: number;
  avg_tick: number;
  window_s: number;
  tick_cumulatives: [number, number];
  chain: "base" | "ethereum";
  pool: string;
  fee_bps: number;
  token0: string;
  token1: string;
  source: "uniswap_v3";
  symbol: string;
}

/** V1.5 — EVM chains supported by the Uniswap v3 TWAP reader. */
export type UniswapChain = "base" | "ethereum";

/**
 * V1.6 — Agent Intelligence Layer: price context with confidence,
 * anomaly detection, and sources agreement.
 */
export interface PriceContextPayload {
  symbol: string;
  price: number;
  confidence_score: number;
  anomaly: boolean;
  anomaly_reasons: string[];
  sources_agreement: "strong" | "good" | "moderate" | "weak" | "single_source";
  source_count: number;
  divergence_pct: number;
  freshest_age_s: number | null;
  twap_5min: number;
  twap_deviation_pct: number;
  source_outliers: Array<{ source: string; deviation_pct: number }>;
  sources: PriceSource[];
}

/**
 * V1.8 — Historical price snapshots.
 */
export interface PriceHistoryDatapoint {
  timestamp: number;
  price: number;
  samples: number;
}

export type HistoryRange = "24h" | "7d" | "30d";
export type HistoryInterval = "5m" | "1h" | "1d";

export interface PriceHistoryPayload {
  symbol: string;
  range: HistoryRange;
  interval: HistoryInterval;
  datapoints: PriceHistoryDatapoint[];
  count: number;
  oldest_available: number | null;
}

/**
 * V1.9 — Price alert payload.
 */
export interface AlertPayload {
  id: number;
  symbol: string;
  condition: "above" | "below";
  threshold: number;
  active: boolean;
}

export interface AlertListEntry {
  id: number;
  symbol: string;
  condition: "above" | "below";
  threshold: number;
  callback_url: string;
  active: boolean;
  created_at: number;
  triggered_at: number | null;
}

export interface AlertListPayload {
  alerts: AlertListEntry[];
  count: number;
}

export interface AlertDeletePayload {
  deleted: boolean;
  id: number;
}

/**
 * V1.7 — Asset metadata from CoinGecko (market cap, volume, supply).
 */
export interface MetadataPayload {
  symbol: string;
  name: string;
  market_cap_usd: number | null;
  volume_24h_usd: number | null;
  price_change_24h_pct: number | null;
  circulating_supply: number | null;
  total_supply: number | null;
  max_supply: number | null;
  market_cap_rank: number | null;
  ath_usd: number | null;
  atl_usd: number | null;
  last_updated: string | null;
  source: "coingecko";
}

