import { DISCLAIMER, getClient } from "../client.js";
import type { Action, IAgentRuntime } from "../types.js";

export const healthCheckAction: Action = {
  name: "HEALTH_CHECK",
  similes: ["ORACLE_HEALTH", "LIVENESS_PROBE"],
  description:
    "Minimal liveness probe for the MAXIA Oracle backend. Does not touch " +
    "upstream sources — cheap enough to call every few seconds. " +
    DISCLAIMER,
  validate: async (_runtime: IAgentRuntime) => {
    // No API key needed for /health.
    return true;
  },
  handler: async (runtime, _message, _state, _options, callback) => {
    const client = getClient(runtime);
    const result = await client.health();
    await callback?.({
      text: `MAXIA Oracle health: ${result.data.status}. ` + DISCLAIMER,
      content: { health: result.data, disclaimer: result.disclaimer },
    });
    return true;
  },
};
