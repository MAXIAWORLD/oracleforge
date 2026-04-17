import { DISCLAIMER, extractSymbol, getClient } from "../client.js";
import type { Action, IAgentRuntime, Memory } from "../types.js";

export const getAssetMetadataAction: Action = {
  name: "GET_ASSET_METADATA",
  similes: [
    "ASSET_METADATA",
    "COIN_INFO",
    "MARKET_CAP",
    "COINGECKO_DATA",
    "COIN_STATS",
    "SUPPLY_INFO",
    "ATH",
    "ATL",
  ],
  description:
    "Fetch asset metadata from CoinGecko (market cap, volume, supply, rank, ATH/ATL). " +
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
    const result = await client.metadata(symbol);
    const {
      name,
      market_cap_usd,
      volume_24h_usd,
      price_change_24h_pct,
      circulating_supply,
      market_cap_rank,
      ath_usd,
      atl_usd,
    } = result.data;

    const fmt = (n: number | null, prefix = "$") =>
      n !== null ? `${prefix}${n.toLocaleString()}` : "N/A";
    const fmtPct = (n: number | null) =>
      n !== null ? `${n >= 0 ? "+" : ""}${n.toFixed(2)}%` : "N/A";

    await callback?.({
      text:
        `${symbol} (${name ?? symbol}): ` +
        `rank #${market_cap_rank ?? "N/A"}, ` +
        `market cap ${fmt(market_cap_usd)}, ` +
        `24h vol ${fmt(volume_24h_usd)}, ` +
        `24h change ${fmtPct(price_change_24h_pct)}, ` +
        `supply ${fmt(circulating_supply, "")}, ` +
        `ATH ${fmt(ath_usd)}, ATL ${fmt(atl_usd)}. ` +
        DISCLAIMER,
      content: { metadata: result.data, disclaimer: result.disclaimer },
    });
    return true;
  },
  examples: [
    [
      { user: "user", content: { text: "What's the market cap of BTC?" } },
      {
        user: "maxia",
        content: {
          text: "BTC (Bitcoin): rank #1, market cap $1,400,000,000,000, 24h vol $30,000,000,000, 24h change +1.20%, supply 19,700,000, ATH $73,738, ATL $67. Data feed only.",
        },
      },
    ],
    [
      { user: "user", content: { text: "Give me CoinGecko data for ETH" } },
      {
        user: "maxia",
        content: {
          text: "ETH (Ethereum): rank #2, market cap $300,000,000,000, 24h vol $15,000,000,000, 24h change -0.45%, supply 120,000,000, ATH $4,891, ATL $0.43. Data feed only.",
        },
      },
    ],
  ],
};
