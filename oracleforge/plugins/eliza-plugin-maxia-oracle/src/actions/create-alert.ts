import { DISCLAIMER, extractSymbol, getClient } from "../client.js";
import type { Action, IAgentRuntime, Memory } from "../types.js";

/**
 * Extract a dollar/number threshold from free-form text.
 * Accepts patterns like "$50000", "50000", "50k", "50,000".
 */
function extractThreshold(text: string): number | null {
  const cleaned = text.replace(/,/g, "");
  const patterns = [
    /\$([0-9]+(?:\.[0-9]+)?)\s*k\b/i,
    /([0-9]+(?:\.[0-9]+)?)\s*k\b/i,
    /\$([0-9]+(?:\.[0-9]+)?)/,
    /\b([0-9]{4,}(?:\.[0-9]+)?)\b/,
  ];
  for (const pattern of patterns) {
    const match = cleaned.match(pattern);
    if (match) {
      const value = parseFloat(match[1]);
      return pattern.source.includes("k") ? value * 1000 : value;
    }
  }
  return null;
}

/**
 * Extract "above" or "below" condition from text.
 */
function extractCondition(text: string): "above" | "below" | null {
  const lower = text.toLowerCase();
  if (
    lower.includes("above") ||
    lower.includes("over") ||
    lower.includes("higher") ||
    lower.includes("exceeds") ||
    lower.includes("goes up")
  ) {
    return "above";
  }
  if (
    lower.includes("below") ||
    lower.includes("under") ||
    lower.includes("lower") ||
    lower.includes("drops") ||
    lower.includes("falls")
  ) {
    return "below";
  }
  return null;
}

/**
 * Extract a callback URL from text. Accepts http:// and https:// URLs.
 */
function extractCallbackUrl(text: string): string | null {
  const match = text.match(/https?:\/\/[^\s"'>]+/);
  return match ? match[0] : null;
}

export const createAlertAction: Action = {
  name: "CREATE_PRICE_ALERT",
  similes: [
    "SET_ALERT",
    "ADD_ALERT",
    "PRICE_ALERT",
    "NOTIFY_PRICE",
    "ALERT_WHEN",
  ],
  description:
    "V1.9 — Create a one-shot price alert with a webhook callback. " +
    "Fires once when the asset price crosses the threshold in the specified " +
    "direction (above/below). Requires: symbol, condition, threshold, " +
    "callback URL. " +
    DISCLAIMER,
  validate: async (runtime: IAgentRuntime, message: Memory) => {
    if (!runtime.getSetting("MAXIA_ORACLE_API_KEY")) return false;
    const text = (message.content.text ?? "").toLowerCase();
    const hasKeyword =
      text.includes("alert") ||
      text.includes("notify") ||
      text.includes("notification") ||
      text.includes("warn") ||
      text.includes("ping") ||
      text.includes("webhook");
    if (!hasKeyword) return false;
    return extractSymbol(message.content.text) !== null;
  },
  handler: async (runtime, message, _state, _options, callback) => {
    const text = message.content.text ?? "";

    const symbol = extractSymbol(text);
    if (!symbol) {
      await callback?.({ text: "No asset ticker detected in the request." });
      return false;
    }

    const condition = extractCondition(text);
    if (!condition) {
      await callback?.({
        text: `Could not determine alert condition for ${symbol}. ` +
          "Please specify 'above' or 'below' (e.g. 'alert me when BTC goes above $80000').",
      });
      return false;
    }

    const threshold = extractThreshold(text);
    if (threshold === null) {
      await callback?.({
        text: `Could not extract a numeric threshold for ${symbol}. ` +
          "Please include a price value (e.g. '$80000' or '80k').",
      });
      return false;
    }

    const callbackUrl = extractCallbackUrl(text);
    if (!callbackUrl) {
      await callback?.({
        text: `No callback URL found. ` +
          "Please include an https:// webhook URL where the alert will be delivered.",
      });
      return false;
    }

    const client = getClient(runtime);
    const result = await client.createAlert(
      symbol,
      condition,
      threshold,
      callbackUrl,
    );

    const { id, active } = result.data;
    await callback?.({
      text:
        `Alert created (id=${id}): notify when ${symbol} goes ${condition} ` +
        `$${threshold.toLocaleString()}. Active: ${active}. ` +
        DISCLAIMER,
      content: { alert: result.data, disclaimer: result.disclaimer },
    });
    return true;
  },
  examples: [
    [
      {
        user: "user",
        content: {
          text: "Create an alert when BTC goes above $80000, webhook https://my.app/hook",
        },
      },
      {
        user: "maxia",
        content: {
          text: "Alert created (id=1): notify when BTC goes above $80,000. Active: true. Data feed only.",
        },
      },
    ],
    [
      {
        user: "user",
        content: {
          text: "Notify me when ETH drops below $2000, callback https://my.app/alerts",
        },
      },
      {
        user: "maxia",
        content: {
          text: "Alert created (id=2): notify when ETH goes below $2,000. Active: true. Data feed only.",
        },
      },
    ],
  ],
};
