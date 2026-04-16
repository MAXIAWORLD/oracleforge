import { DISCLAIMER, getClient } from "../client.js";
import type { Action, IAgentRuntime } from "../types.js";

export const getSourcesStatusAction: Action = {
  name: "GET_SOURCES_STATUS",
  similes: ["SOURCES_STATUS", "ORACLE_STATUS", "UPSTREAM_STATUS"],
  description:
    "Probe each upstream oracle source (Pyth, Chainlink, RedStone, " +
    "aggregator) and report up/down status. Liveness probe only — does " +
    "not validate correctness of returned prices. " +
    DISCLAIMER,
  validate: async (runtime: IAgentRuntime) => {
    return Boolean(runtime.getSetting("MAXIA_ORACLE_API_KEY"));
  },
  handler: async (runtime, _message, _state, _options, callback) => {
    const client = getClient(runtime);
    const result = await client.sources();
    await callback?.({
      text: "MAXIA Oracle sources inventory. " + DISCLAIMER,
      content: { sources: result.data, disclaimer: result.disclaimer },
    });
    return true;
  },
  examples: [
    [
      { user: "user", content: { text: "are the oracle sources up?" } },
      {
        user: "maxia",
        content: { text: "MAXIA Oracle sources inventory. Data feed only." },
      },
    ],
  ],
};
