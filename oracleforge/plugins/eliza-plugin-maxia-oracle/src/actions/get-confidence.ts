import { DISCLAIMER, extractSymbol, getClient } from "../client.js";
import type { Action, IAgentRuntime, Memory } from "../types.js";

export const getConfidenceAction: Action = {
  name: "GET_CONFIDENCE",
  similes: ["PRICE_CONFIDENCE", "DIVERGENCE", "SOURCES_AGREE"],
  description:
    "Return the multi-source divergence for a symbol as a compact metric " +
    "('do the sources agree?') without the per-source price breakdown. " +
    DISCLAIMER,
  validate: async (runtime: IAgentRuntime, message: Memory) => {
    if (!runtime.getSetting("MAXIA_ORACLE_API_KEY")) return false;
    return extractSymbol(message.content.text) !== null;
  },
  handler: async (runtime, message, _state, _options, callback) => {
    const symbol = extractSymbol(message.content.text);
    if (!symbol) {
      await callback?.({ text: "No asset ticker detected in the request." });
      return false;
    }
    const client = getClient(runtime);
    const result = await client.confidence(symbol);
    const { source_count, divergence_pct } = result.data;
    await callback?.({
      text:
        `${symbol}: ${source_count ?? "?"} sources, divergence ` +
        `${divergence_pct ?? "?"}%. ` + DISCLAIMER,
      content: { confidence: result.data, disclaimer: result.disclaimer },
    });
    return true;
  },
};
