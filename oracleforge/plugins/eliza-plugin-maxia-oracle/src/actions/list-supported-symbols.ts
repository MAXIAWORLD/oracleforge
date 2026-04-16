import { DISCLAIMER, getClient } from "../client.js";
import type { Action, IAgentRuntime } from "../types.js";

export const listSupportedSymbolsAction: Action = {
  name: "LIST_SUPPORTED_SYMBOLS",
  similes: ["SYMBOLS", "LIST_SYMBOLS", "SUPPORTED_ASSETS"],
  description:
    "Return the union of all asset symbols supported by MAXIA Oracle, " +
    "grouped by upstream source (Pyth crypto/equity, Chainlink per chain, " +
    "RedStone, Pyth native Solana, price_oracle aggregator). No upstream " +
    "calls — cheap metadata read. " +
    DISCLAIMER,
  validate: async (runtime: IAgentRuntime) => {
    return Boolean(runtime.getSetting("MAXIA_ORACLE_API_KEY"));
  },
  handler: async (runtime, _message, _state, _options, callback) => {
    const client = getClient(runtime);
    const result = await client.listSymbols();
    const { total_symbols } = result.data;
    await callback?.({
      text: `MAXIA Oracle supports ${total_symbols} symbols. ` + DISCLAIMER,
      content: { symbols: result.data, disclaimer: result.disclaimer },
    });
    return true;
  },
};
