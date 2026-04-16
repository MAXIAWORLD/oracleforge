import { DISCLAIMER, extractSymbol, getClient } from "../client.js";
import type { Action, IAgentRuntime, Memory } from "../types.js";

export const getPythSolanaOnchainAction: Action = {
  name: "GET_PYTH_SOLANA_ONCHAIN",
  similes: [
    "PYTH_SOLANA",
    "PYTH_ONCHAIN_SOLANA",
    "PYTH_PRICE_FEED_ACCOUNT",
    "SOLANA_PYTH_READ",
  ],
  description:
    "V1.4 — Fetch a single-source Pyth price directly from a Solana mainnet " +
    "Price Feed Account (shard 0 sponsored feeds). Rejects partial Wormhole " +
    "verifications server-side. Coverage: BTC, ETH, SOL, USDT, USDC, WIF, " +
    "BONK, PYTH, JTO, JUP, RAY, EUR, GBP. " +
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
    const client = getClient(runtime);
    const result = await client.pythSolana(symbol);
    const { price, age_s, stale, price_account } = result.data;
    const staleNote = stale ? " (stale)" : "";
    await callback?.({
      text:
        `Pyth Solana on-chain ${symbol}: $${price} (age ${age_s}s${staleNote}, ` +
        `account ${price_account}). ` +
        DISCLAIMER,
      content: { pyth_solana: result.data, disclaimer: result.disclaimer },
    });
    return true;
  },
};
