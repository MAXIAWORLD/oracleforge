/**
 * Shared MaxiaOracleClient factory for Eliza actions.
 *
 * Each action resolves the client lazily from the runtime settings so the
 * same plugin instance can serve multiple characters with different API
 * keys or base URLs.
 */

import { MaxiaOracleClient } from "@maxia/oracle";

import type { IAgentRuntime } from "./types.js";

const SYMBOL_PATTERN = /\b[A-Z0-9]{2,10}\b/g;

// English tokens that match the ticker pattern but are never assets.
const ENGLISH_STOPWORDS: ReadonlySet<string> = new Set([
  "THE", "AND", "FOR", "PRICE", "PRICES", "IS", "WHAT", "HOW", "MUCH",
  "GIVE", "TELL", "ME", "LIST", "QUOTE", "PLEASE", "ALL", "ARE", "ON",
  "OFF", "OUR", "ITS", "YES", "NO", "TODAY", "NOW", "LIVE",
  "HERE", "THERE", "JUST", "CHATTING", "TICKER",
]);

// Oracle-protocol / infrastructure names. They happen to also be valid
// tickers (PYTH is a Pyth Network token, LINK is Chainlink's token, etc.)
// so we NEVER drop them unconditionally — we only de-prioritize them
// when the same prompt also mentions a non-protocol ticker.
const PROTOCOL_NAMES: ReadonlySet<string> = new Set([
  "PYTH", "REDSTONE", "CHAINLINK", "LINK", "HERMES", "ORACLE",
  "SOLANA", "ETHEREUM", "ARBITRUM", "OPTIMISM", "POLYGON", "BASE",
  "MAINNET", "ONCHAIN", "ON", "CHAIN",
]);

/**
 * Extract a ticker-shaped token from a free-form message.
 *
 * Strategy:
 *   1. Collect every `[A-Z0-9]{2,10}` token (2+ chars to avoid "A", "I").
 *   2. Drop English stopwords.
 *   3. Prefer non-protocol names — so "pyth solana SOL" returns "SOL"
 *      rather than "PYTH".
 *   4. If every remaining candidate is a protocol name (e.g. the user
 *      really does want a quote on PYTH itself), return the last one.
 *   5. Return `null` if no candidate survives.
 */
export function extractSymbol(text: string | undefined): string | null {
  if (!text) return null;
  const upper = text.toUpperCase();
  const matches = Array.from(upper.matchAll(SYMBOL_PATTERN)).map((m) => m[0]);
  const filtered = matches.filter((t) => !ENGLISH_STOPWORDS.has(t));
  if (filtered.length === 0) return null;

  const nonProtocol = filtered.filter((t) => !PROTOCOL_NAMES.has(t));
  if (nonProtocol.length > 0) {
    // Prefer the last non-protocol candidate — often the subject of the
    // sentence in natural prompts ("pyth quote on SOL").
    return nonProtocol[nonProtocol.length - 1];
  }
  return filtered[filtered.length - 1];
}

/**
 * Read settings from the runtime, falling back to `process.env` when a key
 * is absent. ElizaOS character definitions typically expose API keys via
 * `runtime.getSetting(...)`.
 */
function readSetting(runtime: IAgentRuntime, key: string): string | undefined {
  const fromRuntime = runtime.getSetting(key);
  if (fromRuntime) return fromRuntime;
  const fromEnv = process.env[key];
  if (fromEnv && fromEnv.length > 0) return fromEnv;
  return undefined;
}

const _clientCache = new WeakMap<IAgentRuntime, MaxiaOracleClient>();

export function getClient(runtime: IAgentRuntime): MaxiaOracleClient {
  const cached = _clientCache.get(runtime);
  if (cached) return cached;

  const apiKey = readSetting(runtime, "MAXIA_ORACLE_API_KEY");
  const baseUrl = readSetting(runtime, "MAXIA_ORACLE_BASE_URL");

  const client = new MaxiaOracleClient({
    apiKey,
    baseUrl,
  });
  _clientCache.set(runtime, client);
  return client;
}

/**
 * For tests — inject a pre-built client so the handler can be exercised
 * without a real HTTP surface.
 */
export function setClientForTests(
  runtime: IAgentRuntime,
  client: MaxiaOracleClient,
): void {
  _clientCache.set(runtime, client);
}

/**
 * Every action shares the same disclaimer suffix — single source of truth.
 */
export const DISCLAIMER =
  "Data feed only. Not investment advice. No custody. No KYC.";
