import { DISCLAIMER, extractSymbol, getClient } from "../client.js";
import type { Action, IAgentRuntime, Memory } from "../types.js";

const SUPPORTED_CHAINS = ["base", "ethereum"] as const;
const DEFAULT_CHAIN = "ethereum";
const DEFAULT_WINDOW_S = 1800;

function extractChain(text: string | undefined): "base" | "ethereum" {
  if (!text) return DEFAULT_CHAIN;
  const lower = text.toLowerCase();
  for (const chain of SUPPORTED_CHAINS) {
    if (lower.includes(chain)) return chain;
  }
  return DEFAULT_CHAIN;
}

function extractWindow(text: string | undefined): number {
  if (!text) return DEFAULT_WINDOW_S;
  // Match "30 minutes", "1 hour", "3600 seconds" etc. -- keep it loose.
  const lower = text.toLowerCase();
  const minuteMatch = lower.match(/(\d+)\s*(?:minute|min)/);
  if (minuteMatch) {
    const mins = Number(minuteMatch[1]);
    if (mins >= 1 && mins <= 1440) return mins * 60;
  }
  const hourMatch = lower.match(/(\d+)\s*(?:hour|hr)/);
  if (hourMatch) {
    const hrs = Number(hourMatch[1]);
    if (hrs >= 1 && hrs <= 24) return hrs * 3600;
  }
  const secondMatch = lower.match(/(\d+)\s*(?:second|sec)/);
  if (secondMatch) {
    const secs = Number(secondMatch[1]);
    if (secs >= 60 && secs <= 86400) return secs;
  }
  return DEFAULT_WINDOW_S;
}

export const getTwapOnchainAction: Action = {
  name: "GET_TWAP_ONCHAIN",
  similes: [
    "TWAP",
    "UNISWAP_TWAP",
    "UNISWAP_V3_TWAP",
    "TIME_WEIGHTED_PRICE",
    "ONCHAIN_TWAP",
  ],
  description:
    "V1.5 — Fetch a Uniswap v3 time-weighted average price (TWAP) read " +
    "directly from a curated high-liquidity pool on Base or Ethereum mainnet. " +
    "Default 30-minute window, configurable from 60 s to 24 h. " +
    "Coverage: ETH on base/ethereum, BTC on ethereum. " +
    DISCLAIMER,
  validate: async (runtime: IAgentRuntime, message: Memory) => {
    if (!runtime.getSetting("MAXIA_ORACLE_API_KEY")) return false;
    return extractSymbol(message.content.text) !== null;
  },
  handler: async (runtime, message, _state, _options, callback) => {
    const symbol = extractSymbol(message.content.text);
    if (!symbol) {
      await callback?.({ text: "No asset ticker detected." });
      return false;
    }
    const chain = extractChain(message.content.text);
    const windowS = extractWindow(message.content.text);

    const client = getClient(runtime);
    const result = await client.twap(symbol, chain, windowS);
    const { price, window_s, pool, fee_bps } = result.data;
    await callback?.({
      text:
        `Uniswap v3 TWAP ${symbol} on ${chain}: $${price} ` +
        `(window ${window_s}s, pool ${pool}, fee ${fee_bps} bps). ` +
        DISCLAIMER,
      content: {
        uniswap_twap: result.data,
        disclaimer: result.disclaimer,
      },
    });
    return true;
  },
};
