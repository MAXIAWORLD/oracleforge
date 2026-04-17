import { DISCLAIMER, getClient } from "../client.js";
import type { Action, IAgentRuntime, Memory } from "../types.js";

/**
 * Extract a numeric alert id from free-form text.
 * Accepts patterns like "alert #3", "alert id 3", "id=3", "delete 3".
 */
function extractAlertId(text: string): number | null {
  const patterns = [
    /alert\s+#(\d+)/i,
    /alert\s+id\s*[=:]?\s*(\d+)/i,
    /id\s*[=:]\s*(\d+)/i,
    /#(\d+)/,
    /\bdelete\s+(\d+)\b/i,
    /\bremove\s+(\d+)\b/i,
    /\bcancel\s+(\d+)\b/i,
    /\b(\d+)\b/,
  ];
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) {
      const id = parseInt(match[1], 10);
      if (!isNaN(id) && id > 0) return id;
    }
  }
  return null;
}

export const deleteAlertAction: Action = {
  name: "DELETE_PRICE_ALERT",
  similes: [
    "REMOVE_ALERT",
    "CANCEL_ALERT",
    "DISABLE_ALERT",
    "STOP_ALERT",
    "DELETE_ALERT",
  ],
  description:
    "V1.9 — Delete a price alert by its numeric id. " +
    "Accepts natural language like 'delete alert #3' or 'cancel alert id 5'. " +
    DISCLAIMER,
  validate: async (runtime: IAgentRuntime, message: Memory) => {
    if (!runtime.getSetting("MAXIA_ORACLE_API_KEY")) return false;
    const text = (message.content.text ?? "").toLowerCase();
    const hasKeyword =
      text.includes("delete") ||
      text.includes("remove") ||
      text.includes("cancel") ||
      text.includes("disable") ||
      text.includes("stop");
    if (!hasKeyword) return false;
    return (
      text.includes("alert") ||
      text.includes("notification") ||
      extractAlertId(message.content.text ?? "") !== null
    );
  },
  handler: async (runtime, message, _state, _options, callback) => {
    const text = message.content.text ?? "";
    const alertId = extractAlertId(text);

    if (alertId === null) {
      await callback?.({
        text:
          "Could not extract an alert id from the request. " +
          "Please specify the numeric id (e.g. 'delete alert #3').",
      });
      return false;
    }

    const client = getClient(runtime);
    const result = await client.deleteAlert(alertId);
    const { deleted, id } = result.data;

    if (!deleted) {
      await callback?.({
        text: `Alert #${id} could not be deleted (not found or already removed). ` + DISCLAIMER,
        content: { alert_delete: result.data, disclaimer: result.disclaimer },
      });
      return false;
    }

    await callback?.({
      text: `Alert #${id} deleted successfully. ` + DISCLAIMER,
      content: { alert_delete: result.data, disclaimer: result.disclaimer },
    });
    return true;
  },
  examples: [
    [
      { user: "user", content: { text: "Delete alert #3" } },
      {
        user: "maxia",
        content: { text: "Alert #3 deleted successfully. Data feed only." },
      },
    ],
    [
      { user: "user", content: { text: "Cancel alert id 7" } },
      {
        user: "maxia",
        content: { text: "Alert #7 deleted successfully. Data feed only." },
      },
    ],
  ],
};
