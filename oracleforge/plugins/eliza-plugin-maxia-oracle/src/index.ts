/**
 * eliza-plugin-maxia-oracle — ElizaOS plugin for the MAXIA Oracle price feed.
 *
 * Data feed only. Not investment advice. No custody. No KYC.
 *
 * @example
 *   import { maxiaOraclePlugin } from "eliza-plugin-maxia-oracle";
 *
 *   const character = {
 *     ...,
 *     plugins: [maxiaOraclePlugin],
 *     settings: { secrets: { MAXIA_ORACLE_API_KEY: "mxo_..." } },
 *   };
 */

import { getCacheStatsAction } from "./actions/get-cache-stats.js";
import { getChainlinkOnchainAction } from "./actions/get-chainlink-onchain.js";
import { getConfidenceAction } from "./actions/get-confidence.js";
import { getPriceAction } from "./actions/get-price.js";
import { getPricesBatchAction } from "./actions/get-prices-batch.js";
import { getPythSolanaOnchainAction } from "./actions/get-pyth-solana-onchain.js";
import { getRedstonePriceAction } from "./actions/get-redstone-price.js";
import { getSourcesStatusAction } from "./actions/get-sources-status.js";
import { healthCheckAction } from "./actions/health-check.js";
import { listSupportedSymbolsAction } from "./actions/list-supported-symbols.js";
import type { Action, Plugin } from "./types.js";

export const PLUGIN_VERSION = "0.2.0";

export const maxiaOracleActions: readonly Action[] = [
  getPriceAction,
  getPricesBatchAction,
  getSourcesStatusAction,
  getCacheStatsAction,
  getConfidenceAction,
  listSupportedSymbolsAction,
  getChainlinkOnchainAction,
  getRedstonePriceAction,
  getPythSolanaOnchainAction,
  healthCheckAction,
] as const;

export const maxiaOraclePlugin: Plugin = {
  name: "maxia-oracle",
  description:
    "Multi-source crypto + equity price feed for AI agents — Pyth Hermes, " +
    "Chainlink (Base/Ethereum/Arbitrum), RedStone and a 4-way aggregator. " +
    "Data feed only. Not investment advice. No custody. No KYC.",
  actions: [...maxiaOracleActions],
};

export default maxiaOraclePlugin;

export { getClient, setClientForTests, extractSymbol, DISCLAIMER } from "./client.js";
export type { Action, ActionExample, HandlerCallback, IAgentRuntime, Memory, Plugin, State } from "./types.js";
