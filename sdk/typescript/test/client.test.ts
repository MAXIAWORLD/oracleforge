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

  it("chainlinkOnchain calls the right path", async () => {
    const client = makeClient(async (url) => {
      expect(url).toBe("http://test.invalid/api/chainlink/BTC");
      return jsonResponse(200, {
        data: {
          source: "chainlink_base",
          price: 74000.0,
          contract: "0xabc",
        },
        disclaimer: DISCLAIMER,
      });
    });
    const r = await client.chainlinkOnchain("BTC");
    expect(r.data.source).toBe("chainlink_base");
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
