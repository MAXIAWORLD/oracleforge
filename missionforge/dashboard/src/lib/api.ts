/**
 * MissionForge — Type-safe API client for the FastAPI backend.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

// ── Types ───────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  version: string;
  missions_loaded: number;
}

export interface MissionSummary {
  name: string;
  description: string;
  schedule: string | null;
  steps_count: number;
  agent_tier: string;
}

export interface MissionDetail {
  name: string;
  description: string;
  schedule: string | null;
  agent: { system_prompt: string; llm_tier: string };
  steps: Record<string, unknown>[];
}

export interface RunResponse {
  mission_name: string;
  run_id: string;
  status: "success" | "failed" | "running";
  steps_completed: number;
  total_steps: number;
  tokens_used: number;
  cost_usd: number;
  error_message: string | null;
  logs: string[];
  duration_ms: number;
}

export interface ChatResponse {
  reply: string;
  latency_ms: number;
  tier_used: string;
  rag_context_used: boolean;
  tokens_estimated: number;
}

export interface LLMModel {
  id: string;
  name: string;
  provider?: string;
  model?: string;
  description?: string;
  pricing_per_1k_tokens?: { input: number; output: number };
}

export interface TierStats {
  calls: number;
  cost: number;
  last_latency_ms: number;
}

export interface ObservabilitySummary {
  missions: { total: number; scheduled: number; manual: number };
  llm: {
    date: string;
    total_calls: number;
    total_cost_usd: number;
    by_tier: Record<string, TierStats>;
  };
  rag: { ok: boolean; chunks: number; cache: number };
  memory: { backend: string; total: number; collections?: Record<string, number> };
}

// ── Fetch helper ────────────────────────────────────────────────

const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `API error ${res.status}`);
  }
  return res.json();
}

// ── API functions ───────────────────────────────────────────────

export const api = {
  // Health
  health: () => apiFetch<HealthResponse>("/health"),

  // Missions
  listMissions: () =>
    apiFetch<{ missions: MissionSummary[]; total: number }>("/api/missions"),

  getMission: (name: string) =>
    apiFetch<MissionDetail>(`/api/missions/${encodeURIComponent(name)}`),

  runMission: (name: string) =>
    apiFetch<RunResponse>(`/api/missions/${encodeURIComponent(name)}/run`, {
      method: "POST",
    }),

  reloadMissions: () =>
    apiFetch<{ loaded: number; missions: string[] }>("/api/missions/reload", {
      method: "POST",
    }),

  // Chat
  chat: (message: string, missionName?: string) =>
    apiFetch<ChatResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify({
        message,
        mission_name: missionName || null,
        use_rag: true,
      }),
    }),

  // LLM
  listModels: () => apiFetch<{ models: LLMModel[] }>("/api/llm/models"),

  llmUsage: () =>
    apiFetch<{
      date: string;
      total_calls: number;
      total_cost_usd: number;
      by_tier: Record<string, TierStats>;
    }>("/api/llm/usage"),

  // Observability
  observabilitySummary: () =>
    apiFetch<ObservabilitySummary>("/api/observability/summary"),

  tierBreakdown: () =>
    apiFetch<{
      date: string;
      total_calls: number;
      total_cost_usd: number;
      tiers: Record<string, TierStats>;
    }>("/api/observability/tiers"),

  // RAG
  ragStats: () => apiFetch<{ ok: boolean; chunks: number; cache: number }>("/api/rag/stats"),
};
