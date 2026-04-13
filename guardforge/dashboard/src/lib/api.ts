async function f<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    let detail: string | undefined;
    try {
      const body = await res.json();
      detail = body?.detail;
    } catch {
      // body wasn't JSON
    }
    throw new Error(detail || res.statusText);
  }
  return res.json();
}

export interface ScanEntity {
  type: string;
  value?: string;
  start: number;
  end: number;
  confidence: number;
  risk_level: "critical" | "high" | "medium" | "low";
}

export interface ScanResponse {
  original_length: number;
  pii_count: number;
  pii_types: string[];
  entities: ScanEntity[];
  anonymized_text: string | null;
  overall_risk: "critical" | "high" | "medium" | "low" | "none";
  risk_distribution: Record<string, number>;
  dry_run: boolean;
  policy_decision: {
    allowed: boolean;
    action: string;
    reason: string;
    policy: string;
  };
}

export interface TokenizeResponse {
  tokenized_text: string;
  session_id: string;
  token_count: number;
  entities: ScanEntity[];
}

export interface DetokenizeResponse {
  original_text: string;
}

export interface ReportSummary {
  period: { from: string; to: string };
  total_scans: number;
  total_pii_detected: number;
  pii_by_type: Record<string, number>;
  action_distribution: Record<string, number>;
  risk_distribution: Record<string, number>;
  top_policies: { name: string; count: number }[];
}

export interface TimelinePoint {
  date: string;
  scans: number;
  pii: number;
}

export interface ReportTimeline {
  period: { from: string; to: string };
  granularity: string;
  series: TimelinePoint[];
}

export const api = {
  health: () => f<{ status: string }>("/health"),
  scan: (text: string, policy?: string, dryRun?: boolean, strategy?: string) =>
    f<ScanResponse>("/api/scan", {
      method: "POST",
      body: JSON.stringify({ text, policy, dry_run: dryRun ?? false, strategy: strategy ?? "redact" }),
    }),
  tokenize: (text: string, policy?: string, session_id?: string) =>
    f<TokenizeResponse>("/api/tokenize", {
      method: "POST",
      body: JSON.stringify({ text, ...(policy ? { policy } : {}), ...(session_id ? { session_id } : {}) }),
    }),
  detokenize: (text: string, session_id: string) =>
    f<DetokenizeResponse>("/api/detokenize", {
      method: "POST",
      body: JSON.stringify({ text, session_id }),
    }),
  llmWrap: (text: string) => f<{ wrapped_text: string }>("/api/llm/wrap", { method: "POST", body: JSON.stringify({ text }) }),
  policies: () => f<{ policies: { name: string; action: string; description?: string }[] }>("/api/policies"),
  audit: (limit?: number) => f<{ entries: unknown[]; total: number }>(`/api/audit?limit=${limit || 50}`),
  reportSummary: (fromDate?: string, toDate?: string) => {
    const params = new URLSearchParams();
    if (fromDate) params.set("from_date", fromDate);
    if (toDate) params.set("to_date", toDate);
    const qs = params.toString();
    return f<ReportSummary>(`/api/reports/summary${qs ? `?${qs}` : ""}`);
  },
  reportTimeline: (fromDate?: string, toDate?: string, granularity: "day" | "hour" = "day") => {
    const params = new URLSearchParams({ granularity });
    if (fromDate) params.set("from_date", fromDate);
    if (toDate) params.set("to_date", toDate);
    return f<ReportTimeline>(`/api/reports/timeline?${params.toString()}`);
  },
};
