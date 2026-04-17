import { DISCLAIMER, extractSymbol, getClient } from "../client.js";
import type { Action, IAgentRuntime, Memory } from "../types.js";

export const getPriceHistoryAction: Action = {
  name: "GET_PRICE_HISTORY",
  similes: [
    "PRICE_HISTORY",
    "HISTORICAL_PRICE",
    "PAST_PRICES",
    "PRICE_CHART",
    "PRICE_TREND",
  ],
  description:
    "Return historical price snapshots for a symbol (V1.8). " +
    "Ranges: 24h, 7d, 30d. Intervals: 5m, 1h, 1d. Retention: 30 days. " +
    DISCLAIMER,
  validate: async (runtime: IAgentRuntime, message: Memory) => {
    if (!runtime.getSetting("MAXIA_ORACLE_API_KEY")) return false;
    const text = (message.content.text ?? "").toLowerCase();
    const hasKeyword =
      text.includes("history") ||
      text.includes("historical") ||
      text.includes("past") ||
      text.includes("chart") ||
      text.includes("trend");
    if (!hasKeyword) return false;
    return extractSymbol(message.content.text) !== null;
  },
  handler: async (runtime, message, _state, _options, callback) => {
    const symbol = extractSymbol(message.content.text);
    if (!symbol) {
      await callback?.({ text: "No asset ticker detected in the request." });
      return false;
    }
    const client = getClient(runtime);
    const result = await client.priceHistory(symbol);
    await callback?.({
      text:
        `Here is ${symbol} historical price data: ` +
        JSON.stringify(result.data) +
        ` ${DISCLAIMER}`,
      content: { price_history: result.data, disclaimer: result.disclaimer },
    });
    return true;
  },
  examples: [
    [
      {
        user: "user",
        content: { text: "Show me BTC price history" },
      },
      {
        user: "maxia",
        content: {
          text: "Here is BTC historical data... Data feed only. Not investment advice. No custody. No KYC.",
        },
      },
    ],
  ],
};
