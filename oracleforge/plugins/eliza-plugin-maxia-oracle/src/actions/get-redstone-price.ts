import { DISCLAIMER, extractSymbol, getClient } from "../client.js";
import type { Action, IAgentRuntime, Memory } from "../types.js";

export const getRedstonePriceAction: Action = {
  name: "GET_REDSTONE_PRICE",
  similes: ["REDSTONE_PRICE", "REDSTONE", "REDSTONE_QUOTE"],
  description:
    "V1.3 — Fetch a single-source price from the RedStone public REST API. " +
    "RedStone is the 4th independent upstream in MAXIA Oracle, covering " +
    "400+ assets (crypto majors, long-tail, forex, equities). " +
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
    const result = await client.redstone(symbol);
    const { price, age_s } = result.data;
    await callback?.({
      text: `RedStone ${symbol}: $${price} (age ${age_s}s). ` + DISCLAIMER,
      content: { redstone: result.data, disclaimer: result.disclaimer },
    });
    return true;
  },
};
