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
  };
  /** V1.3 — human-readable notes for dynamic-coverage sources. */
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

