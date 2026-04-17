/**
 * MAXIA Oracle SDK — TypeScript client.
 *
 * Usage:
 *
 *     import { MaxiaOracleClient } from "@maxia/oracle";
 *
 *     const client = new MaxiaOracleClient({ apiKey: "mxo_..." });
 *     const btc = await client.price("BTC");
 *     console.log(btc.data.price);
 *
 * 9 methods, full parity with the Python SDK and the MCP tool surface.
 *
 * Data feed only. Not investment advice. No custody. No KYC.
 */

import {
  MaxiaOracleAuthError,
  MaxiaOracleError,
  MaxiaOraclePaymentRequiredError,
  MaxiaOracleRateLimitError,
  MaxiaOracleTransportError,
  MaxiaOracleUpstreamError,
  MaxiaOracleValidationError,
} from "./errors.js";
import type {
  AlertDeletePayload,
  AlertListPayload,
  AlertPayload,
  BatchPricePayload,
  ChainlinkPayload,
  ConfidencePayload,
  HealthPayload,
  HistoryInterval,
  HistoryRange,
  MaxiaOracleClientOptions,
  MaxiaResponse,
  MetadataPayload,
  PriceContextPayload,
  PriceHistoryPayload,
  PricePayload,
  PythSolanaPayload,
  RedstonePayload,
  RegisteredKey,
  SourcesPayload,
  SymbolsPayload,
  UniswapChain,
  UniswapTwapPayload,
} from "./types.js";

export const DEFAULT_BASE_URL = "https://oracle.maxiaworld.app";
export const DEFAULT_TIMEOUT_MS = 15_000;
export const USER_AGENT = "maxia-oracle-typescript/0.8.0";

const SYMBOL_PATTERN = /^[A-Z0-9]{1,10}$/;
const MAX_BATCH_SYMBOLS = 50;

/**
 * EVM chains supported by the Chainlink on-chain reader (V1.1).
 * `base` is the default for strict backward compatibility with V1.0.
 */
export type ChainlinkChain = "base" | "ethereum" | "arbitrum";
const SUPPORTED_CHAINS: readonly ChainlinkChain[] = ["base", "ethereum", "arbitrum"];

/** V1.5 — EVM chains supported by the Uniswap v3 TWAP reader. */
const TWAP_SUPPORTED_CHAINS: readonly UniswapChain[] = ["base", "ethereum"];
const TWAP_MIN_WINDOW_S = 60;
const TWAP_MAX_WINDOW_S = 86_400;

export class MaxiaOracleClient {
  private readonly apiKey: string | undefined;
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly fetchImpl: typeof globalThis.fetch;

  constructor(options: MaxiaOracleClientOptions = {}) {
    this.apiKey = options.apiKey ?? process.env.MAXIA_ORACLE_API_KEY;
    const rawBase =
      options.baseUrl ??
      process.env.MAXIA_ORACLE_BASE_URL ??
      DEFAULT_BASE_URL;
    this.baseUrl = rawBase.replace(/\/+$/, "");
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.fetchImpl = options.fetch ?? globalThis.fetch;
    if (typeof this.fetchImpl !== "function") {
      throw new MaxiaOracleError(
        "no fetch implementation available — provide options.fetch or run on Node 18+",
      );
    }
  }

  // ── Public API ────────────────────────────────────────────────────────

  /**
   * Register a fresh free-tier API key.
   *
   * The raw key is in `response.data.api_key` — it is returned exactly
   * once, store it immediately. Daily quota is in
   * `response.data.daily_limit`. This endpoint is IP-throttled.
   */
  async register(): Promise<MaxiaResponse<RegisteredKey>> {
    return this.request<RegisteredKey>("POST", "/api/register", { auth: false });
  }

  /** Lightweight liveness probe. No authentication required. */
  async health(): Promise<MaxiaResponse<HealthPayload>> {
    return this.request<HealthPayload>("GET", "/health", { auth: false });
  }

  /**
   * Cross-validated multi-source live price for a single asset.
   *
   * @throws {MaxiaOracleValidationError} symbol format.
   * @throws {MaxiaOracleUpstreamError} every upstream source failed.
   * @throws {MaxiaOracleAuthError} missing or invalid API key.
   * @throws {MaxiaOracleRateLimitError} daily quota exhausted.
   */
  async price(symbol: string): Promise<MaxiaResponse<PricePayload>> {
    const cleaned = this.validateSymbol(symbol);
    return this.request<PricePayload>("GET", `/api/price/${cleaned}`);
  }

  /**
   * Up to 50 symbols in a single upstream Pyth Hermes batch call.
   */
  async pricesBatch(symbols: string[]): Promise<MaxiaResponse<BatchPricePayload>> {
    if (!Array.isArray(symbols)) {
      throw new MaxiaOracleValidationError("symbols must be an array of strings");
    }
    if (symbols.length === 0) {
      throw new MaxiaOracleValidationError("symbols must contain at least one entry");
    }
    if (symbols.length > MAX_BATCH_SYMBOLS) {
      throw new MaxiaOracleValidationError(
        `batch size exceeds ${MAX_BATCH_SYMBOLS} (got ${symbols.length})`,
      );
    }
    const cleaned = symbols.map((s) => this.validateSymbol(s));
    return this.request<BatchPricePayload>("POST", "/api/prices/batch", {
      json: { symbols: cleaned },
    });
  }

  /** List every configured upstream oracle source and its current status. */
  async sources(): Promise<MaxiaResponse<SourcesPayload>> {
    return this.request<SourcesPayload>("GET", "/api/sources");
  }

  /** Aggregator in-memory cache hit-rate and circuit-breaker state. */
  async cacheStats(): Promise<MaxiaResponse<Record<string, unknown>>> {
    return this.request<Record<string, unknown>>("GET", "/api/cache/stats");
  }

  /** Union of all supported asset symbols, grouped by upstream source. */
  async listSymbols(): Promise<MaxiaResponse<SymbolsPayload>> {
    return this.request<SymbolsPayload>("GET", "/api/symbols");
  }

  /**
   * Single-source price directly from a Chainlink on-chain feed.
   *
   * V1.1: accepts `chain` = `"base"` (default), `"ethereum"`, or
   * `"arbitrum"`. Bypasses Pyth and the aggregator. Independently
   * verifiable on-chain through the corresponding EVM RPC.
   *
   * Supported symbols per chain are in
   * `listSymbols().data.by_source.chainlink_<chain>`.
   */
  async chainlinkOnchain(
    symbol: string,
    chain: ChainlinkChain = "base",
  ): Promise<MaxiaResponse<ChainlinkPayload>> {
    const cleanedSymbol = this.validateSymbol(symbol);
    const cleanedChain = this.validateChain(chain);
    return this.request<ChainlinkPayload>(
      "GET",
      `/api/chainlink/${cleanedSymbol}`,
      { query: { chain: cleanedChain } },
    );
  }

  /**
   * V1.3 — Single-source RedStone REST price.
   *
   * RedStone is the 4th independent upstream in MAXIA Oracle. Coverage
   * is dynamic (400+ assets: crypto majors, long-tail, forex, equities).
   * Unknown symbols throw `MaxiaOracleUpstreamError` (404) rather than
   * being pre-rejected on a hardcoded allow-list.
   */
  async redstone(symbol: string): Promise<MaxiaResponse<RedstonePayload>> {
    const cleaned = this.validateSymbol(symbol);
    return this.request<RedstonePayload>("GET", `/api/redstone/${cleaned}`);
  }

  /**
   * V1.4 — Single-source Pyth on-chain read (Solana mainnet).
   *
   * Returns the Pyth Price Feed Account value for `symbol` on shard 0
   * of the Pyth Push Oracle program. Coverage is a curated list of
   * majors (BTC, ETH, SOL, USDT, USDC, WIF, BONK, PYTH, JTO, JUP, RAY,
   * EUR, GBP). Anything else throws `MaxiaOracleUpstreamError` (404).
   *
   * The reader rejects partial Wormhole verifications server-side, so a
   * successful response always carries a fully-verified update.
   */
  async pythSolana(symbol: string): Promise<MaxiaResponse<PythSolanaPayload>> {
    const cleaned = this.validateSymbol(symbol);
    return this.request<PythSolanaPayload>("GET", `/api/pyth/solana/${cleaned}`);
  }

  /**
   * V1.5 — Uniswap v3 time-weighted average price (TWAP) on-chain.
   *
   * Reads a curated high-liquidity Uniswap v3 pool on `chain`
   * (`"base"` or `"ethereum"`) and returns the TWAP computed from
   * `observe(uint32[])` over `windowSeconds`. Default window is 30
   * minutes; range is [60, 86400].
   *
   * Coverage: ETH on base + ethereum, BTC on ethereum. Extending the
   * list is a server-side change -- see `docs/v1.5_uniswap_twap.md`.
   */
  async twap(
    symbol: string,
    chain: UniswapChain = "ethereum",
    windowSeconds: number = 1800,
  ): Promise<MaxiaResponse<UniswapTwapPayload>> {
    const cleanedSymbol = this.validateSymbol(symbol);
    const cleanedChain = this.validateTwapChain(chain);
    const cleanedWindow = this.validateTwapWindow(windowSeconds);
    return this.request<UniswapTwapPayload>(
      "GET",
      `/api/twap/${cleanedSymbol}`,
      { query: { chain: cleanedChain, window: String(cleanedWindow) } },
    );
  }

  /**
   * V1.6 — Price + confidence score + anomaly flag + sources agreement.
   *
   * Agent-native one-call: everything an LLM agent needs to decide whether
   * to act on a price. Includes `confidence_score` (0-100), `anomaly` flag
   * with reasons, TWAP deviation, and source outliers.
   */
  async priceContext(symbol: string): Promise<MaxiaResponse<PriceContextPayload>> {
    const cleaned = this.validateSymbol(symbol);
    return this.request<PriceContextPayload>("GET", `/api/price/${cleaned}/context`);
  }

  /**
   * V1.7 — Asset metadata from CoinGecko (market cap, volume, supply).
   *
   * Coverage: ~80 crypto assets with CoinGecko mapping. Forex and
   * equity symbols are not covered. Unknown symbols throw
   * `MaxiaOracleUpstreamError` (404).
   */
  async metadata(symbol: string): Promise<MaxiaResponse<MetadataPayload>> {
    const cleaned = this.validateSymbol(symbol);
    return this.request<MetadataPayload>("GET", `/api/metadata/${cleaned}`);
  }

  /**
   * V1.8 — Historical price snapshots for a symbol.
   *
   * The background sampler captures prices every 5 minutes. Data is
   * downsampled to the requested interval via averaging. Retention is
   * 30 days.
   *
   * @param symbol - Asset ticker (e.g. "BTC").
   * @param range - Time range: "24h", "7d", or "30d". Defaults to "24h".
   * @param interval - Bucket interval: "5m", "1h", or "1d". Auto-selected if omitted.
   */
  async priceHistory(
    symbol: string,
    range: HistoryRange = "24h",
    interval?: HistoryInterval,
  ): Promise<MaxiaResponse<PriceHistoryPayload>> {
    const cleaned = this.validateSymbol(symbol);
    const query: Record<string, string> = { range };
    if (interval !== undefined) {
      query["interval"] = interval;
    }
    return this.request<PriceHistoryPayload>(
      "GET",
      `/api/price/${cleaned}/history`,
      { query },
    );
  }

  // ── V1.9 Alerts ─────────────────────────────────────────────────────────

  /** V1.9 — Create a one-shot price alert with a webhook callback. */
  async createAlert(
    symbol: string,
    condition: "above" | "below",
    threshold: number,
    callbackUrl: string,
  ): Promise<MaxiaResponse<AlertPayload>> {
    const cleaned = this.validateSymbol(symbol);
    return this.request<AlertPayload>("POST", "/api/alerts", {
      json: {
        symbol: cleaned,
        condition,
        threshold,
        callback_url: callbackUrl,
      },
    });
  }

  /** V1.9 — List all alerts for the authenticated key. */
  async listAlerts(): Promise<MaxiaResponse<AlertListPayload>> {
    return this.request<AlertListPayload>("GET", "/api/alerts");
  }

  /** V1.9 — Delete a price alert by id. */
  async deleteAlert(
    alertId: number,
  ): Promise<MaxiaResponse<AlertDeletePayload>> {
    return this.request<AlertDeletePayload>(
      "DELETE",
      `/api/alerts/${alertId}`,
    );
  }

  /**
   * Compact multi-source divergence for a symbol ("do the sources agree?").
   *
   * Built on top of `price()` — returns the symbol, the source count and
   * the divergence in percent, without the per-source price breakdown.
   */
  async confidence(symbol: string): Promise<MaxiaResponse<ConfidencePayload>> {
    const full = await this.price(symbol);
    return {
      data: {
        symbol: full.data.symbol,
        source_count: full.data.source_count ?? null,
        divergence_pct: full.data.divergence_pct ?? null,
      },
      disclaimer: full.disclaimer ?? "",
    };
  }

  // ── Internals ─────────────────────────────────────────────────────────

  private validateSymbol(symbol: string): string {
    if (typeof symbol !== "string") {
      throw new MaxiaOracleValidationError("symbol must be a string");
    }
    const cleaned = symbol.trim().toUpperCase();
    if (!SYMBOL_PATTERN.test(cleaned)) {
      throw new MaxiaOracleValidationError(
        `symbol must match ${SYMBOL_PATTERN.source}`,
      );
    }
    return cleaned;
  }

  private validateChain(chain: string): ChainlinkChain {
    if (typeof chain !== "string") {
      throw new MaxiaOracleValidationError("chain must be a string");
    }
    const cleaned = chain.trim().toLowerCase() as ChainlinkChain;
    if (!SUPPORTED_CHAINS.includes(cleaned)) {
      throw new MaxiaOracleValidationError(
        `chain must be one of ${SUPPORTED_CHAINS.join(", ")}, got ${chain}`,
      );
    }
    return cleaned;
  }

  private validateTwapChain(chain: string): UniswapChain {
    if (typeof chain !== "string") {
      throw new MaxiaOracleValidationError("chain must be a string");
    }
    const cleaned = chain.trim().toLowerCase() as UniswapChain;
    if (!TWAP_SUPPORTED_CHAINS.includes(cleaned)) {
      throw new MaxiaOracleValidationError(
        `chain must be one of ${TWAP_SUPPORTED_CHAINS.join(", ")} for twap(), got ${chain}`,
      );
    }
    return cleaned;
  }

  private validateTwapWindow(windowSeconds: number): number {
    if (!Number.isInteger(windowSeconds)) {
      throw new MaxiaOracleValidationError("windowSeconds must be an integer");
    }
    if (windowSeconds < TWAP_MIN_WINDOW_S || windowSeconds > TWAP_MAX_WINDOW_S) {
      throw new MaxiaOracleValidationError(
        `windowSeconds must be within [${TWAP_MIN_WINDOW_S}, ${TWAP_MAX_WINDOW_S}], got ${windowSeconds}`,
      );
    }
    return windowSeconds;
  }

  private buildHeaders(auth: boolean, hasBody: boolean): Record<string, string> {
    const headers: Record<string, string> = {
      "User-Agent": USER_AGENT,
      Accept: "application/json",
    };
    if (hasBody) {
      headers["Content-Type"] = "application/json";
    }
    if (auth) {
      if (!this.apiKey) {
        throw new MaxiaOracleAuthError(
          "API key required — pass options.apiKey or set MAXIA_ORACLE_API_KEY",
        );
      }
      headers["X-API-Key"] = this.apiKey;
    }
    return headers;
  }

  private async request<T>(
    method: "GET" | "POST" | "DELETE",
    path: string,
    options: {
      auth?: boolean;
      json?: unknown;
      query?: Record<string, string>;
    } = {},
  ): Promise<MaxiaResponse<T>> {
    const auth = options.auth !== false;
    const hasBody = options.json !== undefined;
    const headers = this.buildHeaders(auth, hasBody);
    const queryString = options.query
      ? "?" + new URLSearchParams(options.query).toString()
      : "";
    const url = `${this.baseUrl}${path}${queryString}`;

    for (let attempt = 0; attempt < 2; attempt++) {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

      let response: Response;
      try {
        response = await this.fetchImpl(url, {
          method,
          headers,
          body: hasBody ? JSON.stringify(options.json) : undefined,
          signal: controller.signal,
        });
      } catch (err) {
        clearTimeout(timeoutId);
        const msg = err instanceof Error ? err.message : String(err);
        throw new MaxiaOracleTransportError(
          `transport error on ${method} ${path}: ${msg}`,
        );
      }
      clearTimeout(timeoutId);

      let body: unknown;
      try {
        body = await response.json();
      } catch {
        throw new MaxiaOracleTransportError(
          `non-JSON response from ${method} ${path}: status=${response.status}`,
        );
      }

      if (response.ok) {
        return body as MaxiaResponse<T>;
      }

      if (response.status === 429 && attempt === 0) {
        const retryRaw = response.headers.get("retry-after");
        const waitS = Math.min(retryRaw ? Number(retryRaw) : 1, 60);
        await new Promise((resolve) => setTimeout(resolve, waitS * 1000));
        continue;
      }

      this.raiseTypedError(response.status, body, method, path);
    }

    throw new MaxiaOracleTransportError(`exhausted retries on ${method} ${path}`);
  }

  private raiseTypedError(
    status: number,
    body: unknown,
    method: string,
    path: string,
  ): never {
    const isObject = typeof body === "object" && body !== null;
    const envelope = isObject ? (body as Record<string, unknown>) : {};
    const messageRaw = envelope["error"];
    const message =
      typeof messageRaw === "string" && messageRaw.length > 0
        ? messageRaw
        : `HTTP ${status}`;

    if (status === 401) {
      throw new MaxiaOracleAuthError(message);
    }
    if (status === 402) {
      const acceptsRaw = envelope["accepts"];
      throw new MaxiaOraclePaymentRequiredError(
        message,
        Array.isArray(acceptsRaw) ? acceptsRaw : [],
      );
    }
    if (status === 404) {
      // Every 404 in the MAXIA Oracle REST surface corresponds to an
      // upstream-level "this symbol is not available here" answer
      // (`no live price available`, `symbol has no Chainlink feed on
      // requested chain`, `symbol not found on redstone`, `symbol not
      // supported on Pyth Solana shard 0`).
      throw new MaxiaOracleUpstreamError(message);
    }
    if (status === 400 || status === 422) {
      throw new MaxiaOracleValidationError(message);
    }
    if (status === 429) {
      const retryRaw = envelope["retry_after_seconds"];
      const limitRaw = envelope["limit"];
      throw new MaxiaOracleRateLimitError(message, {
        retryAfterSeconds: typeof retryRaw === "number" ? retryRaw : null,
        limit: typeof limitRaw === "number" ? limitRaw : null,
      });
    }
    throw new MaxiaOracleTransportError(
      `unexpected ${status} on ${method} ${path}: ${message}`,
    );
  }
}
