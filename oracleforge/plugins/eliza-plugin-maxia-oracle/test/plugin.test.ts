/**
 * Smoke tests for eliza-plugin-maxia-oracle.
 *
 * No Eliza runtime and no MAXIA Oracle backend needed:
 *   - `runtime` is a bare object that satisfies the structural `IAgentRuntime`.
 *   - `MaxiaOracleClient` is swapped for a stub via `setClientForTests()`.
 */
import { describe, expect, it } from "vitest";

import {
  DISCLAIMER,
  extractSymbol,
  maxiaOracleActions,
  maxiaOraclePlugin,
  setClientForTests,
} from "../src/index.js";
import type { IAgentRuntime, Memory } from "../src/types.js";

interface RuntimeOpts {
  apiKey?: string | null;
}

function makeRuntime(opts: RuntimeOpts = { apiKey: "mxo_test_key" }): IAgentRuntime {
  const apiKey = opts.apiKey;
  return {
    getSetting: (key: string) =>
      key === "MAXIA_ORACLE_API_KEY" ? (apiKey ?? undefined) : undefined,
  };
}

function makeMessage(text: string): Memory {
  return { content: { text } };
}

describe("plugin shape", () => {
  it("exports 12 actions", () => {
    expect(maxiaOracleActions).toHaveLength(12);
    expect(maxiaOraclePlugin.actions).toHaveLength(12);
  });

  it("every action has name + description + validate + handler", () => {
    for (const action of maxiaOracleActions) {
      expect(action.name).toMatch(/^[A-Z_]+$/);
      expect(action.description.length).toBeGreaterThan(20);
      expect(typeof action.validate).toBe("function");
      expect(typeof action.handler).toBe("function");
    }
  });

  it("every description ends with the disclaimer", () => {
    for (const action of maxiaOracleActions) {
      expect(action.description).toContain(DISCLAIMER);
    }
  });

  it("action names are unique", () => {
    const names = maxiaOracleActions.map((a) => a.name);
    expect(new Set(names).size).toBe(names.length);
  });
});

describe("extractSymbol", () => {
  it("finds BTC in a natural question", () => {
    expect(extractSymbol("what's the price of BTC?")).toBe("BTC");
  });

  it("returns null if no ticker candidate", () => {
    expect(extractSymbol("just chatting, no ticker here")).toBeNull();
  });

  it("ignores common stopwords that match the ticker pattern", () => {
    expect(extractSymbol("the price please")).toBeNull();
  });

  it("returns null on undefined input", () => {
    expect(extractSymbol(undefined)).toBeNull();
  });
});

describe("GET_PRICE handler (stubbed client)", () => {
  const runtime = makeRuntime();

  it("validates when API key + symbol are present", async () => {
    const action = maxiaOracleActions.find((a) => a.name === "GET_PRICE")!;
    const ok = await action.validate(runtime, makeMessage("quote BTC"));
    expect(ok).toBe(true);
  });

  it("rejects when API key is missing", async () => {
    const action = maxiaOracleActions.find((a) => a.name === "GET_PRICE")!;
    const noKey = makeRuntime({ apiKey: null });
    const ok = await action.validate(noKey, makeMessage("quote BTC"));
    expect(ok).toBe(false);
  });

  it("handler forwards the extracted symbol and reports a price", async () => {
    const action = maxiaOracleActions.find((a) => a.name === "GET_PRICE")!;
    let called = "";
    const stub = {
      price: async (sym: string) => {
        called = sym;
        return {
          data: { symbol: sym, price: 74000, source_count: 4, divergence_pct: 0.02 },
          disclaimer: DISCLAIMER,
        };
      },
    };
    setClientForTests(runtime, stub as unknown as import("@maxia/oracle").MaxiaOracleClient);

    let captured = "";
    const ok = await action.handler(
      runtime,
      makeMessage("price of BTC?"),
      undefined,
      undefined,
      async ({ text }) => {
        captured = text;
      },
    );
    expect(ok).toBe(true);
    expect(called).toBe("BTC");
    expect(captured).toContain("BTC");
    expect(captured).toContain("$74000");
  });
});

describe("GET_REDSTONE_PRICE handler (stubbed client)", () => {
  const runtime = makeRuntime();

  it("handler forwards the symbol to client.redstone", async () => {
    const action = maxiaOracleActions.find((a) => a.name === "GET_REDSTONE_PRICE")!;
    let called = "";
    const stub = {
      redstone: async (sym: string) => {
        called = sym;
        return {
          data: { symbol: sym, price: 74200, age_s: 5 },
          disclaimer: DISCLAIMER,
        };
      },
    };
    setClientForTests(runtime, stub as unknown as import("@maxia/oracle").MaxiaOracleClient);

    let captured = "";
    await action.handler(
      runtime,
      makeMessage("redstone quote on ETH"),
      undefined,
      undefined,
      async ({ text }) => {
        captured = text;
      },
    );
    expect(called).toBe("ETH");
    expect(captured).toContain("RedStone");
    expect(captured).toContain("ETH");
  });
});

describe("GET_PYTH_SOLANA_ONCHAIN handler (stubbed client)", () => {
  const runtime = makeRuntime();

  it("handler forwards the symbol to client.pythSolana", async () => {
    const action = maxiaOracleActions.find(
      (a) => a.name === "GET_PYTH_SOLANA_ONCHAIN",
    )!;
    let called = "";
    const stub = {
      pythSolana: async (sym: string) => {
        called = sym;
        return {
          data: {
            symbol: sym,
            price: 75000,
            age_s: 5,
            stale: false,
            price_account: "4cSM2e6rvbGQUFiJbqytoVMi5GgghSMr8LwVrT9VPSPo",
          },
          disclaimer: DISCLAIMER,
        };
      },
    };
    setClientForTests(runtime, stub as unknown as import("@maxia/oracle").MaxiaOracleClient);

    let captured = "";
    await action.handler(
      runtime,
      makeMessage("pyth solana onchain quote on SOL"),
      undefined,
      undefined,
      async ({ text }) => {
        captured = text;
      },
    );
    expect(called).toBe("SOL");
    expect(captured).toContain("Pyth Solana on-chain");
    expect(captured).toContain("SOL");
    expect(captured).toContain("$75000");
  });

  it("handler marks stale feed explicitly", async () => {
    const action = maxiaOracleActions.find(
      (a) => a.name === "GET_PYTH_SOLANA_ONCHAIN",
    )!;
    const stub = {
      pythSolana: async (sym: string) => ({
        data: {
          symbol: sym,
          price: 1.35,
          age_s: 500,
          stale: true,
          price_account: "G25Tm7UkVruTJ7mcbCxFm45XGWwsH72nJKNGcHEQw1tU",
        },
        disclaimer: DISCLAIMER,
      }),
    };
    setClientForTests(runtime, stub as unknown as import("@maxia/oracle").MaxiaOracleClient);

    let captured = "";
    await action.handler(
      runtime,
      makeMessage("pyth solana GBP"),
      undefined,
      undefined,
      async ({ text }) => {
        captured = text;
      },
    );
    expect(captured).toContain("stale");
  });
});

describe("GET_TWAP_ONCHAIN handler (stubbed client)", () => {
  const runtime = makeRuntime();

  it("forwards symbol + default chain + default window", async () => {
    const action = maxiaOracleActions.find(
      (a) => a.name === "GET_TWAP_ONCHAIN",
    )!;
    const captured: { sym?: string; chain?: string; window?: number } = {};
    const stub = {
      twap: async (sym: string, chain: string, window: number) => {
        captured.sym = sym;
        captured.chain = chain;
        captured.window = window;
        return {
          data: {
            source: "uniswap_v3",
            symbol: sym,
            chain,
            price: 2341.0,
            avg_tick: 198735,
            window_s: window,
            tick_cumulatives: [1, 2],
            pool: "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
            fee_bps: 5,
            token0: "USDC",
            token1: "WETH",
          },
          disclaimer: DISCLAIMER,
        };
      },
    };
    setClientForTests(runtime, stub as unknown as import("@maxia/oracle").MaxiaOracleClient);

    let text = "";
    await action.handler(
      runtime,
      makeMessage("uniswap twap on ETH"),
      undefined,
      undefined,
      async ({ text: t }) => {
        text = t;
      },
    );
    expect(captured).toEqual({ sym: "ETH", chain: "ethereum", window: 1800 });
    expect(text).toContain("Uniswap v3 TWAP ETH");
    expect(text).toContain("ethereum");
    expect(text).toContain("$2341");
  });

  it("picks up a non-default chain + window from the prompt", async () => {
    const action = maxiaOracleActions.find(
      (a) => a.name === "GET_TWAP_ONCHAIN",
    )!;
    const captured: { chain?: string; window?: number } = {};
    const stub = {
      twap: async (sym: string, chain: string, window: number) => {
        captured.chain = chain;
        captured.window = window;
        return {
          data: {
            source: "uniswap_v3",
            symbol: sym,
            chain,
            price: 2341.0,
            avg_tick: 0,
            window_s: window,
            tick_cumulatives: [1, 2],
            pool: "0x",
            fee_bps: 5,
            token0: "WETH",
            token1: "USDC",
          },
          disclaimer: DISCLAIMER,
        };
      },
    };
    setClientForTests(runtime, stub as unknown as import("@maxia/oracle").MaxiaOracleClient);

    await action.handler(
      runtime,
      makeMessage("twap ETH on base over 1 hour"),
      undefined,
      undefined,
      async () => {},
    );
    expect(captured.chain).toBe("base");
    expect(captured.window).toBe(3600);
  });
});

