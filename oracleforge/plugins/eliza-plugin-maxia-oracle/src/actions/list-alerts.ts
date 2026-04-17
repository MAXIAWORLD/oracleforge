import { DISCLAIMER, getClient } from "../client.js";
import type { Action, IAgentRuntime, Memory } from "../types.js";

export const listAlertsAction: Action = {
  name: "LIST_PRICE_ALERTS",
  similes: [
    "GET_ALERTS",
    "SHOW_ALERTS",
    "MY_ALERTS",
    "ALL_ALERTS",
    "VIEW_ALERTS",
  ],
  description:
    "V1.9 — List all active and triggered price alerts for the current API key. " +
    "Returns id, symbol, condition, threshold, callback URL, status and " +
    "triggered timestamp. " +
    DISCLAIMER,
  validate: async (runtime: IAgentRuntime, message: Memory) => {
    if (!runtime.getSetting("MAXIA_ORACLE_API_KEY")) return false;
    const text = (message.content.text ?? "").toLowerCase();
    return (
      text.includes("alert") ||
      text.includes("alerts") ||
      text.includes("notification") ||
      text.includes("notifications")
    );
  },
  handler: async (runtime, _message, _state, _options, callback) => {
    const client = getClient(runtime);
    const result = await client.listAlerts();
    const { alerts, count } = result.data;

    if (count === 0) {
      await callback?.({
        text: "No price alerts found for your API key. " + DISCLAIMER,
        content: { alerts: [], count: 0, disclaimer: result.disclaimer },
      });
      return true;
    }

    const summary = alerts
      .map(
        (a) =>
          `#${a.id} ${a.symbol} ${a.condition} $${a.threshold.toLocaleString()} ` +
          `[${a.active ? "active" : "triggered"}]`,
      )
      .join(", ");

    await callback?.({
      text: `${count} alert(s): ${summary}. ` + DISCLAIMER,
      content: { alerts: result.data, disclaimer: result.disclaimer },
    });
    return true;
  },
  examples: [
    [
      { user: "user", content: { text: "List my price alerts" } },
      {
        user: "maxia",
        content: {
          text: "2 alert(s): #1 BTC above $80,000 [active], #2 ETH below $2,000 [triggered]. Data feed only.",
        },
      },
    ],
    [
      { user: "user", content: { text: "Show all alerts" } },
      {
        user: "maxia",
        content: { text: "No price alerts found for your API key. Data feed only." },
      },
    ],
  ],
};
