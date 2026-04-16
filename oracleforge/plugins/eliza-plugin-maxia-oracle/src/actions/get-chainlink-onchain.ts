import type { ChainlinkChain } from "@maxia/oracle";

import { DISCLAIMER, extractSymbol, getClient } from "../client.js";
import type { Action, IAgentRuntime, Memory } from "../types.js";

const CHAIN_PATTERN = /\b(base|ethereum|arbitrum)\b/i;

function extractChain(text: string | undefined): ChainlinkChain {
  if (!text) return "base";
  const match = text.match(CHAIN_PATTERN);
  if (!match) return "base";
  return match[1].toLowerCase() as ChainlinkChain;
}

export const getChainlinkOnchainAction: Action = {
  name: "GET_CHAINLINK_ONCHAIN",
  similes: ["CHAINLINK_PRICE", "ONCHAIN_PRICE", "CHAINLINK"],
  description:
    "Fetch a single-source price directly from a Chainlink on-chain feed " +
    "on Base, Ethereum or Arbitrum. Independently verifiable on-chain. " +
    "Useful to cross-check the multi-source median. " +
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
    const client = getClient(runtime);
    const result = await client.chainlinkOnchain(symbol, chain);
    const { price } = result.data;
    await callback?.({
      text:
        `Chainlink ${chain} ${symbol}: $${price}. ` + DISCLAIMER,
      content: { chainlink: result.data, disclaimer: result.disclaimer },
    });
    return true;
  },
};
