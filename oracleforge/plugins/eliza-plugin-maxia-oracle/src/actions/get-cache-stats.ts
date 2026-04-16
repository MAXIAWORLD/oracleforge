import { DISCLAIMER, getClient } from "../client.js";
import type { Action, IAgentRuntime } from "../types.js";

export const getCacheStatsAction: Action = {
  name: "GET_CACHE_STATS",
  similes: ["CACHE_STATS", "ORACLE_METRICS"],
  description:
    "Return the aggregator in-memory cache hit rate and circuit-breaker " +
    "state. Debug tool for agents that want to introspect their own " +
    "latency amplification. " +
    DISCLAIMER,
  validate: async (runtime: IAgentRuntime) => {
    return Boolean(runtime.getSetting("MAXIA_ORACLE_API_KEY"));
  },
  handler: async (runtime, _message, _state, _options, callback) => {
    const client = getClient(runtime);
    const result = await client.cacheStats();
    await callback?.({
      text: "Oracle cache + circuit breaker stats. " + DISCLAIMER,
      content: { stats: result.data, disclaimer: result.disclaimer },
    });
    return true;
  },
};
