import { DISCLAIMER, getClient } from "../client.js";
import type { Action, IAgentRuntime, Memory } from "../types.js";

const BATCH_PATTERN = /\b[A-Z0-9]{1,10}\b/g;
const STOPWORDS = new Set([
  "THE", "AND", "FOR", "PRICE", "PRICES", "LIST", "QUOTE",
  "GIVE", "TELL", "ME", "BATCH", "ALL",
]);

function extractSymbols(text: string | undefined): string[] {
  if (!text) return [];
  const upper = text.toUpperCase();
  const matches = Array.from(upper.matchAll(BATCH_PATTERN)).map((m) => m[0]);
  const cleaned = matches.filter((s) => !STOPWORDS.has(s));
  // Deduplicate, preserve order.
  return Array.from(new Set(cleaned)).slice(0, 50);
}

export const getPricesBatchAction: Action = {
  name: "GET_PRICES_BATCH",
  similes: ["BATCH_PRICES", "MULTIPLE_PRICES", "PRICE_LIST"],
  description:
    "Return live prices for up to 50 asset tickers in a single upstream call. " +
    "Dramatically cheaper than issuing one get_price per symbol. " +
    DISCLAIMER,
  validate: async (runtime: IAgentRuntime, message: Memory) => {
    const apiKey = runtime.getSetting("MAXIA_ORACLE_API_KEY");
    if (!apiKey) return false;
    return extractSymbols(message.content.text).length >= 2;
  },
  handler: async (runtime, message, _state, _options, callback) => {
    const symbols = extractSymbols(message.content.text);
    if (symbols.length === 0) {
      await callback?.({ text: "No tickers detected for a batch request." });
      return false;
    }
    const client = getClient(runtime);
    const result = await client.pricesBatch(symbols);
    const { count, requested, prices } = result.data;
    await callback?.({
      text:
        `Batch: requested ${requested}, returned ${count}. ` + DISCLAIMER,
      content: { prices, disclaimer: result.disclaimer },
    });
    return true;
  },
  examples: [
    [
      { user: "user", content: { text: "give me prices for BTC ETH SOL" } },
      {
        user: "maxia",
        content: { text: "Batch: requested 3, returned 3. Data feed only." },
      },
    ],
  ],
};
