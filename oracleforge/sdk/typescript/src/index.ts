/**
 * MAXIA Oracle — TypeScript SDK.
 *
 * Data feed only. Not investment advice. No custody. No KYC.
 *
 * @example
 *   import { MaxiaOracleClient } from "@maxia/oracle";
 *
 *   const client = new MaxiaOracleClient({ apiKey: "mxo_..." });
 *   const btc = await client.price("BTC");
 *   console.log(btc.data.price);
 */

export {
  DEFAULT_BASE_URL,
  DEFAULT_TIMEOUT_MS,
  MaxiaOracleClient,
  USER_AGENT,
} from "./client.js";

export type { ChainlinkChain } from "./client.js";
export type { UniswapChain } from "./types.js";

export {
  MaxiaOracleAuthError,
  MaxiaOracleError,
  MaxiaOraclePaymentRequiredError,
  MaxiaOracleRateLimitError,
  MaxiaOracleTransportError,
  MaxiaOracleUpstreamError,
  MaxiaOracleValidationError,
} from "./errors.js";

export type {
  AlertDeletePayload,
  AlertListEntry,
  AlertListPayload,
  AlertPayload,
  BatchPricePayload,
  ChainlinkPayload,
  ConfidencePayload,
  HealthPayload,
  HistoryInterval,
  HistoryRange,
  MaxiaOracleClientOptions,
  MaxiaResponse,
  MetadataPayload,
  PriceHistoryDatapoint,
  PriceHistoryPayload,
  PricePayload,
  PriceSource,
  PythSolanaPayload,
  UniswapTwapPayload,
  RedstonePayload,
  RegisteredKey,
  SourcesPayload,
  SymbolsPayload,
} from "./types.js";
