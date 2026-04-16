import { DISCLAIMER, extractSymbol, getClient } from "../client.js";
import type { Action, IAgentRuntime, Memory } from "../types.js";

export const getPriceAction: Action = {
  name: "GET_PRICE",
  similes: ["FETCH_PRICE", "PRICE_QUOTE", "PRICE_CHECK", "QUOTE"],
  description:
    "Return a cross-validated multi-source live price for a single asset. " +
    "Queries Pyth, Chainlink, RedStone and the aggregator in parallel, " +
    "computes the median and the inter-source divergence in percent. " +
    DISCLAIMER,
  validate: async (runtime: IAgentRuntime, message: Memory) => {
    const apiKey = runtime.getSetting("MAXIA_ORACLE_API_KEY");
    if (!apiKey) return false;
    return extractSymbol(message.content.text) !== null;
  },
  handler: async (runtime, message, _state, _options, callback) => {
    const symbol = extractSymbol(message.content.text);
    if (!symbol) {
      await callback?.({ text: "No asset ticker detected in the request." });
      return false;
    }
    const client = getClient(runtime);
    const result = await client.price(symbol);
    const { price, source_count, divergence_pct } = result.data;
    await callback?.({
      text:
        `${symbol}: $${price} ` +
        `(${source_count} sources, divergence ${divergence_pct}%). ` +
        DISCLAIMER,
      content: { result: result.data, disclaimer: result.disclaimer },
    });
    return true;
  },
  examples: [
    [
      { user: "user", content: { text: "What's BTC price?" } },
      {
        user: "maxia",
        content: {
          text: "BTC: $74,123 (4 sources agree within 0.02%). Data feed only.",
        },
      },
    ],
    [
      { user: "user", content: { text: "quote ETH please" } },
      {
        user: "maxia",
        content: { text: "ETH: $2,501 (3 sources, divergence 0.05%)." },
      },
    ],
  ],
};
