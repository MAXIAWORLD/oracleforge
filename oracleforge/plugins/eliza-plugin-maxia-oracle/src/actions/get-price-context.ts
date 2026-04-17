import { DISCLAIMER, extractSymbol, getClient } from "../client.js";
import type { Action, IAgentRuntime, Memory } from "../types.js";

export const getPriceContextAction: Action = {
  name: "GET_PRICE_CONTEXT",
  similes: [
    "PRICE_CONTEXT",
    "CONFIDENCE_SCORE",
    "ANOMALY_CHECK",
    "FULL_PRICE_ANALYSIS",
  ],
  description:
    "V1.6 — Return price + confidence score (0-100) + anomaly flag + sources " +
    "agreement in one call. Agent-native: everything an LLM agent needs to " +
    "decide whether to act on a price. Includes TWAP deviation and source " +
    "outliers. " +
    DISCLAIMER,
  examples: [
    [
      {
        user: "user1",
        content: { text: "Get the full context for BTC price" },
      },
    ],
  ],
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
    const result = await client.priceContext(symbol);
    const {
      price,
      confidence_score,
      anomaly,
      sources_agreement,
      source_count,
    } = result.data;
    const anomalyNote = anomaly ? " ⚠ anomaly detected" : "";
    await callback?.({
      text:
        `${symbol}: $${price}, confidence ${confidence_score}/100, ` +
        `${source_count} sources (${sources_agreement})${anomalyNote}. ` +
        DISCLAIMER,
      content: { price_context: result.data, disclaimer: result.disclaimer },
    });
    return true;
  },
};
