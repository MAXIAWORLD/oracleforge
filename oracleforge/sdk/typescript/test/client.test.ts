/**
 * MaxiaOracleClient tests using a fake fetch implementation.
 *
 * No backend process needed. Each test supplies its own fetch stub via
 * the client's `fetch` option — zero mocking libraries, zero network.
 */
import { describe, expect, it } from "vitest";

import {
  MaxiaOracleAuthError,
  MaxiaOracleClient,
  MaxiaOracleRateLimitError,
  MaxiaOracleTransportError,
  MaxiaOracleUpstreamError,
  MaxiaOracleValidationError,
} from "../src/index.js";

const DISCLAIMER = "Data feed only. Not investment advice. No custody. No KYC.";

type FetchStub = (url: string, init: RequestInit) => Promise<Response>;

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function makeClient(
  handler: FetchStub,
  opts: { apiKey?: string | undefined } = { apiKey: "mxo_fake_test_key" },
): MaxiaOracleClient {
  const fetchImpl: typeof globalThis.fetch = async (input, init) => {
    const url = typeof input === "string" ? input : input.toString();
    return handler(url, init ?? {});
  };
  return new MaxiaOracleClient({
    apiKey: opts.apiKey,
    baseUrl: "http://test.invalid",
    fetch: fetchImpl,
  });
}

describe("register / health (no auth)", () => {
  it("register returns the new api key", async () => {
    const client = makeClient(async (url, init) => {
      expect(init.method).toBe("POST");
      expect(url).toBe("http://test.invalid/api/register");
      expect((init.headers as Record<string, string>)["X-API-Key"]).toBeUndefined();
      return jsonResponse(201, {
        data: { api_key: "mxo_new_key", tier: "free", daily_limit: 100 },
        disclaimer: DISCLAIMER,
      });
    }, { apiKey: undefined });
    const r = await client.register();
    expect(r.data.api_key).toBe("mxo_new_key");
    expect(r.data.daily_limit).toBe(100);
  });

  it("health does not send the api key", async () => {
    const client = makeClient(async (url, init) => {
      expect(url).toBe("http://test.invalid/health");
      expect((init.headers as Record<string, string>)["X-API-Key"]).toBeUndefined();
      return jsonResponse(200, {
        data: { status: "ok", env: "dev", uptime_s: 1.5 },
        disclaimer: DISCLAIMER,
      });
    }, { apiKey: undefined });
    const r = await client.health();
    expect(r.data.status).toBe("ok");
  });
});

describe("price", () => {
  it("sends X-API-Key and parses response", async () => {
    const client = makeClient(async (url, init) => {
      expect(url).toBe("http://test.invalid/api/price/BTC");
      expect((init.headers as Record<string, string>)["X-API-Key"]).toBe("mxo_fake_test_key");
      return jsonResponse(200, {
        data: {
          symbol: "BTC",
          price: 74000.5,
          sources: [{ name: "pyth", price: 74000.5 }],
          source_count: 1,
          divergence_pct: 0.0,
        },
        disclaimer: DISCLAIMER,
      });
    });
    const r = await client.price("btc");
    expect(r.data.symbol).toBe("BTC");
    expect(r.data.price).toBe(74000.5);
  });

  it("rejects bad symbol locally", async () => {
    const client = makeClient(async () => {
      throw new Error("should not reach fetch");
    });
    await expect(client.price("not-a-symbol")).rejects.toThrow(
      MaxiaOracleValidationError,
    );
  });

  it("upstream error raises typed exception", async () => {
    const client = makeClient(async () =>
      jsonResponse(404, { error: "no live price available", symbol: "FAKE" }),
    );
    await expect(client.price("FAKE")).rejects.toThrow(MaxiaOracleUpstreamError);
  });

  it("auth error raises typed exception", async () => {
    const client = makeClient(async () =>
      jsonResponse(401, { error: "invalid or inactive API key" }),
    );
    await expect(client.price("BTC")).rejects.toThrow(MaxiaOracleAuthError);
  });

  it("rate limit error exposes retryAfterSeconds", async () => {
    const client = makeClient(async () =>
      jsonResponse(429, {
        error: "rate limit exceeded",
        limit: 100,
        retry_after_seconds: 3600,
      }),
    );
    try {
      await client.price("BTC");
      expect.fail("should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(MaxiaOracleRateLimitError);
      const rl = err as MaxiaOracleRateLimitError;
      expect(rl.retryAfterSeconds).toBe(3600);
      expect(rl.limit).toBe(100);
    }
  });

  it("missing api key raises auth error locally", async () => {
    const client = makeClient(async () => {
      throw new Error("should not reach fetch");
    }, { apiKey: undefined });
    await expect(client.price("BTC")).rejects.toThrow(MaxiaOracleAuthError);
  });
});

describe("pricesBatch", () => {
  it("validates inputs locally", async () => {
    const client = makeClient(async () => {
      throw new Error("should not reach fetch");
    });
    await expect(client.pricesBatch([])).rejects.toThrow(MaxiaOracleValidationError);
    await expect(client.pricesBatch("BTC" as unknown as string[])).rejects.toThrow(
      MaxiaOracleValidationError,
    );
    const tooMany = Array.from({ length: 51 }, (_, i) => `SYM${i}`);
    await expect(client.pricesBatch(tooMany)).rejects.toThrow(MaxiaOracleValidationError);
  });

  it("sends uppercased symbols", async () => {
    let seenBody: unknown;
    const client = makeClient(async (_url, init) => {
      seenBody = JSON.parse(init.body as string);
      return jsonResponse(200, {
        data: { requested: 2, count: 2, prices: { BTC: 1, ETH: 2 } },
        disclaimer: DISCLAIMER,
      });
    });
    await client.pricesBatch(["btc", "eth"]);
    expect(seenBody).toEqual({ symbols: ["BTC", "ETH"] });
  });
});

describe("metadata endpoints", () => {
  it("sources returns list", async () => {
    const client = makeClient(async (url) => {
      expect(url).toBe("http://test.invalid/api/sources");
      return jsonResponse(200, {
        data: { sources: [{ name: "pyth_hermes" }] },
        disclaimer: DISCLAIMER,
      });
    });
    const r = await client.sources();
    expect(r.data.sources[0]!.name).toBe("pyth_hermes");
  });

  it("cacheStats returns metrics", async () => {
    const client = makeClient(async (url) => {
      expect(url).toBe("http://test.invalid/api/cache/stats");
      return jsonResponse(200, {
        data: { hit_rate: 0.8 },
        disclaimer: DISCLAIMER,
      });
    });
    const r = await client.cacheStats();
    expect(r.data.hit_rate).toBe(0.8);
  });

  it("listSymbols returns grouped output", async () => {
    const client = makeClient(async (url) => {
      expect(url).toBe("http://test.invalid/api/symbols");
      return jsonResponse(200, {
        data: {
          total_symbols: 3,
          all_symbols: ["BTC", "ETH", "SOL"],
          by_source: {
            pyth_crypto: ["BTC", "ETH", "SOL"],
            pyth_equity: [],
            chainlink_base: [],
            price_oracle: [],
          },
        },
        disclaimer: DISCLAIMER,
      });
    });
    const r = await client.listSymbols();
    expect(r.data.total_symbols).toBe(3);
    expect(r.data.all_symbols).toContain("BTC");
  });

  it("chainlinkOnchain calls the right path with default chain=base", async () => {
    const client = makeClient(async (url) => {
      expect(url).toBe("http://test.invalid/api/chainlink/BTC?chain=base");
      return jsonResponse(200, {
        data: {
          source: "chainlink_base",
          price: 74000.0,
          contract: "0xabc",
          chain: "base",
        },
        disclaimer: DISCLAIMER,
      });
    });
    const r = await client.chainlinkOnchain("BTC");
    expect(r.data.source).toBe("chainlink_base");
  });

  it("chainlinkOnchain forwards chain=ethereum to the backend", async () => {
    const client = makeClient(async (url) => {
      expect(url).toBe("http://test.invalid/api/chainlink/BTC?chain=ethereum");
      return jsonResponse(200, {
        data: {
          source: "chainlink_ethereum",
          price: 73900.0,
          contract: "0xeth",
          chain: "ethereum",
        },
        disclaimer: DISCLAIMER,
      });
    });
    const r = await client.chainlinkOnchain("BTC", "ethereum");
    expect(r.data.source).toBe("chainlink_ethereum");
  });

  it("chainlinkOnchain rejects unsupported chain at validation time", async () => {
    const client = makeClient(async () =>
      jsonResponse(200, { data: {}, disclaimer: DISCLAIMER }),
    );
    // @ts-expect-error — deliberately passing an invalid chain literal.
    await expect(client.chainlinkOnchain("BTC", "solana")).rejects.toThrow(
      /chain must be one of/,
    );
  });
});

describe("redstone (V1.3)", () => {
  it("hits /api/redstone/{symbol}", async () => {
    const client = makeClient(async (url) => {
      expect(url).toBe("http://test.invalid/api/redstone/BTC");
      return jsonResponse(200, {
        data: {
          source: "redstone",
          symbol: "BTC",
          price: 74200.1,
          publish_time: 1_700_000_000,
          age_s: 4,
          stale: false,
          provider: "redstone-primary-prod",
        },
        disclaimer: DISCLAIMER,
      });
    });
    const r = await client.redstone("BTC");
    expect(r.data.source).toBe("redstone");
    expect(r.data.price).toBe(74200.1);
  });
});

describe("twap (V1.5)", () => {
  it("hits /api/twap/{symbol} with chain + window query params", async () => {
    let capturedUrl = "";
    const client = makeClient(async (url) => {
      capturedUrl = url;
      return jsonResponse(200, {
        data: {
          source: "uniswap_v3",
          symbol: "ETH",
          chain: "ethereum",
          price: 2341.0,
          avg_tick: 198735,
          window_s: 3600,
          tick_cumulatives: [1, 2],
          pool: "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
          fee_bps: 5,
          token0: "USDC",
          token1: "WETH",
        },
        disclaimer: DISCLAIMER,
      });
    });
    const r = await client.twap("ETH", "ethereum", 3600);
    expect(capturedUrl).toContain("/api/twap/ETH");
    expect(capturedUrl).toContain("chain=ethereum");
    expect(capturedUrl).toContain("window=3600");
    expect(r.data.source).toBe("uniswap_v3");
    expect(r.data.window_s).toBe(3600);
  });

  it("rejects invalid chain client-side", async () => {
    const client = makeClient(async () => {
      throw new Error("fetch should not be called");
    });
    await expect(client.twap("ETH", "solana" as never)).rejects.toThrow(
      MaxiaOracleValidationError,
    );
  });

  it("rejects window_s out of range client-side", async () => {
    const client = makeClient(async () => {
      throw new Error("fetch should not be called");
    });
    await expect(client.twap("ETH", "ethereum", 5)).rejects.toThrow(
      MaxiaOracleValidationError,
    );
    await expect(client.twap("ETH", "ethereum", 10 ** 9)).rejects.toThrow(
      MaxiaOracleValidationError,
    );
  });

  it("raises UpstreamError on 404 (pair not configured)", async () => {
    const client = makeClient(async () =>
      jsonResponse(404, {
        error: "no Uniswap v3 pool configured for this symbol on this chain",
        symbol: "BTC",
        chain: "base",
      }),
    );
    await expect(client.twap("BTC", "base")).rejects.toThrow(
      MaxiaOracleUpstreamError,
    );
  });
});

describe("pythSolana (V1.4)", () => {
  it("hits /api/pyth/solana/{symbol}", async () => {
    const client = makeClient(async (url) => {
      expect(url).toBe("http://test.invalid/api/pyth/solana/BTC");
      return jsonResponse(200, {
        data: {
          source: "pyth_solana",
          symbol: "BTC",
          price: 75000.0,
          conf: 12.3,
          confidence_pct: 0.02,
          publish_time: 1_776_000_000,
          age_s: 5,
          stale: false,
          price_account: "4cSM2e6rvbGQUFiJbqytoVMi5GgghSMr8LwVrT9VPSPo",
          posted_slot: 413_000_000,
          exponent: -8,
          feed_id: "e62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43",
        },
        disclaimer: DISCLAIMER,
      });
    });
    const r = await client.pythSolana("BTC");
    expect(r.data.source).toBe("pyth_solana");
    expect(r.data.price).toBe(75000.0);
    expect(r.data.price_account).toBe("4cSM2e6rvbGQUFiJbqytoVMi5GgghSMr8LwVrT9VPSPo");
  });

  it("raises UpstreamError on 404", async () => {
    const client = makeClient(async () =>
      jsonResponse(404, {
        error: "symbol not supported on Pyth Solana shard 0",
        symbol: "ZZZZ",
        supported: ["BTC", "ETH"],
      }),
    );
    await expect(client.pythSolana("ZZZZ")).rejects.toThrow(
      MaxiaOracleUpstreamError,
    );
  });

  it("rejects invalid symbol client-side", async () => {
    const client = makeClient(async () => {
      throw new Error("fetch should not be called");
    });
    await expect(client.pythSolana("bad-sym!")).rejects.toThrow(
      MaxiaOracleValidationError,
    );
  });
});

describe("confidence", () => {
  it("extracts divergence from the price call", async () => {
    const client = makeClient(async (url) => {
      expect(url).toBe("http://test.invalid/api/price/ETH");
      return jsonResponse(200, {
        data: {
          symbol: "ETH",
          price: 3500.0,
          sources: [{ name: "pyth", price: 3500.0 }],
          source_count: 2,
          divergence_pct: 0.12,
        },
        disclaimer: DISCLAIMER,
      });
    });
    const r = await client.confidence("eth");
    expect(r.data.symbol).toBe("ETH");
    expect(r.data.source_count).toBe(2);
    expect(r.data.divergence_pct).toBe(0.12);
  });
});

describe("priceContext (V1.6)", () => {
  it("hits /api/price/{symbol}/context and parses PriceContextPayload", async () => {
    const client = makeClient(async (url, init) => {
      expect(init.method).toBe("GET");
      expect(url).toBe("http://test.invalid/api/price/BTC/context");
      expect((init.headers as Record<string, string>)["X-API-Key"]).toBe("mxo_fake_test_key");
      return jsonResponse(200, {
        data: {
          symbol: "BTC",
          price: 74000.0,
          confidence_score: 92,
          anomaly: false,
          anomaly_reasons: [],
          sources_agreement: "strong",
          source_count: 3,
          divergence_pct: 0.05,
          freshest_age_s: 2,
          twap_5min: 73980.0,
          twap_deviation_pct: 0.027,
          source_outliers: [],
          sources: [{ name: "pyth", price: 74000.0 }],
        },
        disclaimer: DISCLAIMER,
      });
    });
    const r = await client.priceContext("BTC");
    expect(r.data.symbol).toBe("BTC");
    expect(r.data.confidence_score).toBe(92);
    expect(r.data.anomaly).toBe(false);
    expect(r.data.sources_agreement).toBe("strong");
    expect(r.data.twap_5min).toBe(73980.0);
  });

  it("normalises lowercase symbol before sending", async () => {
    let capturedUrl = "";
    const client = makeClient(async (url) => {
      capturedUrl = url;
      return jsonResponse(200, {
        data: {
          symbol: "ETH",
          price: 3500.0,
          confidence_score: 85,
          anomaly: false,
          anomaly_reasons: [],
          sources_agreement: "good",
          source_count: 2,
          divergence_pct: 0.1,
          freshest_age_s: 4,
          twap_5min: 3495.0,
          twap_deviation_pct: 0.14,
          source_outliers: [],
          sources: [],
        },
        disclaimer: DISCLAIMER,
      });
    });
    await client.priceContext("eth");
    expect(capturedUrl).toBe("http://test.invalid/api/price/ETH/context");
  });

  it("rejects bad symbol locally", async () => {
    const client = makeClient(async () => {
      throw new Error("should not reach fetch");
    });
    await expect(client.priceContext("bad-sym!")).rejects.toThrow(
      MaxiaOracleValidationError,
    );
  });
});

describe("metadata (V1.7)", () => {
  it("hits /api/metadata/{symbol} and parses MetadataPayload", async () => {
    const client = makeClient(async (url, init) => {
      expect(init.method).toBe("GET");
      expect(url).toBe("http://test.invalid/api/metadata/BTC");
      return jsonResponse(200, {
        data: {
          symbol: "BTC",
          name: "Bitcoin",
          market_cap_usd: 1_400_000_000_000,
          volume_24h_usd: 35_000_000_000,
          price_change_24h_pct: 1.5,
          circulating_supply: 19_700_000,
          total_supply: 21_000_000,
          max_supply: 21_000_000,
          market_cap_rank: 1,
          ath_usd: 109_000.0,
          atl_usd: 67.81,
          last_updated: "2026-04-17T10:00:00Z",
          source: "coingecko",
        },
        disclaimer: DISCLAIMER,
      });
    });
    const r = await client.metadata("BTC");
    expect(r.data.symbol).toBe("BTC");
    expect(r.data.name).toBe("Bitcoin");
    expect(r.data.market_cap_rank).toBe(1);
    expect(r.data.source).toBe("coingecko");
  });

  it("normalises lowercase symbol", async () => {
    let capturedUrl = "";
    const client = makeClient(async (url) => {
      capturedUrl = url;
      return jsonResponse(200, {
        data: {
          symbol: "SOL",
          name: "Solana",
          market_cap_usd: null,
          volume_24h_usd: null,
          price_change_24h_pct: null,
          circulating_supply: null,
          total_supply: null,
          max_supply: null,
          market_cap_rank: null,
          ath_usd: null,
          atl_usd: null,
          last_updated: null,
          source: "coingecko",
        },
        disclaimer: DISCLAIMER,
      });
    });
    await client.metadata("sol");
    expect(capturedUrl).toBe("http://test.invalid/api/metadata/SOL");
  });

  it("raises UpstreamError on 404 (symbol not in CoinGecko)", async () => {
    const client = makeClient(async () =>
      jsonResponse(404, { error: "symbol not found in CoinGecko mapping", symbol: "FOREX" }),
    );
    await expect(client.metadata("FOREX")).rejects.toThrow(MaxiaOracleUpstreamError);
  });

  it("rejects bad symbol locally", async () => {
    const client = makeClient(async () => {
      throw new Error("should not reach fetch");
    });
    await expect(client.metadata("not-valid!")).rejects.toThrow(
      MaxiaOracleValidationError,
    );
  });
});

describe("priceHistory (V1.8)", () => {
  it("hits /api/price/{symbol}/history with default range=24h", async () => {
    let capturedUrl = "";
    const client = makeClient(async (url) => {
      capturedUrl = url;
      return jsonResponse(200, {
        data: {
          symbol: "BTC",
          range: "24h",
          interval: "5m",
          datapoints: [
            { timestamp: 1_713_000_000, price: 73900.0, samples: 1 },
            { timestamp: 1_713_000_300, price: 74000.0, samples: 1 },
          ],
          count: 2,
          oldest_available: 1_713_000_000,
        },
        disclaimer: DISCLAIMER,
      });
    });
    const r = await client.priceHistory("BTC");
    expect(capturedUrl).toContain("/api/price/BTC/history");
    expect(capturedUrl).toContain("range=24h");
    expect(capturedUrl).not.toContain("interval=");
    expect(r.data.symbol).toBe("BTC");
    expect(r.data.range).toBe("24h");
    expect(r.data.datapoints).toHaveLength(2);
    expect(r.data.count).toBe(2);
  });

  it("forwards explicit range and interval as query params", async () => {
    let capturedUrl = "";
    const client = makeClient(async (url) => {
      capturedUrl = url;
      return jsonResponse(200, {
        data: {
          symbol: "ETH",
          range: "7d",
          interval: "1h",
          datapoints: [],
          count: 0,
          oldest_available: null,
        },
        disclaimer: DISCLAIMER,
      });
    });
    await client.priceHistory("eth", "7d", "1h");
    expect(capturedUrl).toContain("/api/price/ETH/history");
    expect(capturedUrl).toContain("range=7d");
    expect(capturedUrl).toContain("interval=1h");
  });

  it("supports 30d range with 1d interval", async () => {
    let capturedUrl = "";
    const client = makeClient(async (url) => {
      capturedUrl = url;
      return jsonResponse(200, {
        data: {
          symbol: "SOL",
          range: "30d",
          interval: "1d",
          datapoints: [],
          count: 0,
          oldest_available: null,
        },
        disclaimer: DISCLAIMER,
      });
    });
    await client.priceHistory("SOL", "30d", "1d");
    expect(capturedUrl).toContain("range=30d");
    expect(capturedUrl).toContain("interval=1d");
  });

  it("rejects bad symbol locally", async () => {
    const client = makeClient(async () => {
      throw new Error("should not reach fetch");
    });
    await expect(client.priceHistory("bad sym")).rejects.toThrow(
      MaxiaOracleValidationError,
    );
  });
});

describe("createAlert (V1.9)", () => {
  it("POSTs to /api/alerts with correct JSON body", async () => {
    let seenBody: unknown;
    const client = makeClient(async (url, init) => {
      expect(init.method).toBe("POST");
      expect(url).toBe("http://test.invalid/api/alerts");
      seenBody = JSON.parse(init.body as string);
      return jsonResponse(201, {
        data: {
          id: 42,
          symbol: "BTC",
          condition: "above",
          threshold: 80000,
          active: true,
        },
        disclaimer: DISCLAIMER,
      });
    });
    const r = await client.createAlert("btc", "above", 80000, "https://example.com/hook");
    expect(seenBody).toEqual({
      symbol: "BTC",
      condition: "above",
      threshold: 80000,
      callback_url: "https://example.com/hook",
    });
    expect(r.data.id).toBe(42);
    expect(r.data.symbol).toBe("BTC");
    expect(r.data.condition).toBe("above");
    expect(r.data.active).toBe(true);
  });

  it("normalises lowercase symbol in the request body", async () => {
    let seenBody: unknown;
    const client = makeClient(async (_url, init) => {
      seenBody = JSON.parse(init.body as string);
      return jsonResponse(201, {
        data: { id: 7, symbol: "ETH", condition: "below", threshold: 3000, active: true },
        disclaimer: DISCLAIMER,
      });
    });
    await client.createAlert("eth", "below", 3000, "https://example.com/hook");
    expect((seenBody as Record<string, unknown>)["symbol"]).toBe("ETH");
  });

  it("rejects bad symbol locally", async () => {
    const client = makeClient(async () => {
      throw new Error("should not reach fetch");
    });
    await expect(
      client.createAlert("bad!", "above", 80000, "https://example.com/hook"),
    ).rejects.toThrow(MaxiaOracleValidationError);
  });
});

describe("listAlerts (V1.9)", () => {
  it("GETs /api/alerts and parses AlertListPayload", async () => {
    const client = makeClient(async (url, init) => {
      expect(init.method).toBe("GET");
      expect(url).toBe("http://test.invalid/api/alerts");
      expect((init.headers as Record<string, string>)["X-API-Key"]).toBe("mxo_fake_test_key");
      return jsonResponse(200, {
        data: {
          alerts: [
            {
              id: 1,
              symbol: "BTC",
              condition: "above",
              threshold: 80000,
              callback_url: "https://example.com/hook",
              active: true,
              created_at: 1_713_000_000,
              triggered_at: null,
            },
          ],
          count: 1,
        },
        disclaimer: DISCLAIMER,
      });
    });
    const r = await client.listAlerts();
    expect(r.data.count).toBe(1);
    expect(r.data.alerts).toHaveLength(1);
    expect(r.data.alerts[0]!.symbol).toBe("BTC");
    expect(r.data.alerts[0]!.active).toBe(true);
    expect(r.data.alerts[0]!.triggered_at).toBeNull();
  });

  it("returns empty list when no alerts are registered", async () => {
    const client = makeClient(async () =>
      jsonResponse(200, {
        data: { alerts: [], count: 0 },
        disclaimer: DISCLAIMER,
      }),
    );
    const r = await client.listAlerts();
    expect(r.data.alerts).toHaveLength(0);
    expect(r.data.count).toBe(0);
  });

  it("raises AuthError when api key is missing", async () => {
    const client = makeClient(async () => {
      throw new Error("should not reach fetch");
    }, { apiKey: undefined });
    await expect(client.listAlerts()).rejects.toThrow(MaxiaOracleAuthError);
  });
});

describe("deleteAlert (V1.9)", () => {
  it("sends DELETE to /api/alerts/{alertId}", async () => {
    const client = makeClient(async (url, init) => {
      expect(init.method).toBe("DELETE");
      expect(url).toBe("http://test.invalid/api/alerts/42");
      expect((init.headers as Record<string, string>)["X-API-Key"]).toBe("mxo_fake_test_key");
      return jsonResponse(200, {
        data: { deleted: true, id: 42 },
        disclaimer: DISCLAIMER,
      });
    });
    const r = await client.deleteAlert(42);
    expect(r.data.deleted).toBe(true);
    expect(r.data.id).toBe(42);
  });

  it("raises UpstreamError on 404 (alert not found)", async () => {
    const client = makeClient(async () =>
      jsonResponse(404, { error: "alert not found", id: 999 }),
    );
    await expect(client.deleteAlert(999)).rejects.toThrow(MaxiaOracleUpstreamError);
  });

  it("raises AuthError when api key is missing", async () => {
    const client = makeClient(async () => {
      throw new Error("should not reach fetch");
    }, { apiKey: undefined });
    await expect(client.deleteAlert(1)).rejects.toThrow(MaxiaOracleAuthError);
  });
});

describe("transport errors", () => {
  it("connection failure raises transport error", async () => {
    const client = makeClient(async () => {
      throw new TypeError("fetch failed: ECONNREFUSED");
    });
    await expect(client.health()).rejects.toThrow(MaxiaOracleTransportError);
  });

  it("non-json response raises transport error", async () => {
    const client = makeClient(async () =>
      new Response("<html>not json</html>", {
        status: 200,
        headers: { "content-type": "text/html" },
      }),
    );
    await expect(client.health()).rejects.toThrow(MaxiaOracleTransportError);
  });
});
