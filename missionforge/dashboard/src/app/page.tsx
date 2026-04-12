"use client";

import { useEffect, useState } from "react";
import {
  Bot,
  Cpu,
  Database,
  DollarSign,
  Rocket,
  Zap,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api, type ObservabilitySummary, type MissionSummary } from "@/lib/api";

function KpiCard({
  title,
  value,
  subtitle,
  icon: Icon,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ElementType;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-gray-500">
          {title}
        </CardTitle>
        <Icon className="h-4 w-4 text-gray-400" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {subtitle && (
          <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
        )}
      </CardContent>
    </Card>
  );
}

export default function OverviewPage() {
  const [summary, setSummary] = useState<ObservabilitySummary | null>(null);
  const [missions, setMissions] = useState<MissionSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [s, m] = await Promise.all([
          api.observabilitySummary(),
          api.listMissions(),
        ]);
        setSummary(s);
        setMissions(m.missions);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load data");
      }
    };
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  if (error) {
    return (
      <div className="p-8">
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <p className="text-red-600">Backend unavailable: {error}</p>
            <p className="text-sm text-red-400 mt-2">
              Start the backend:{" "}
              <code className="bg-red-100 px-1 rounded">
                cd backend && uvicorn main:app --port 8001
              </code>
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const llm = summary?.llm;
  const tierData = llm?.by_tier
    ? Object.entries(llm.by_tier).filter(([, v]) => v.calls > 0)
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-gray-500 text-sm">MissionForge overview</p>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          title="Missions"
          value={summary?.missions.total ?? "-"}
          subtitle={`${summary?.missions.scheduled ?? 0} scheduled`}
          icon={Rocket}
        />
        <KpiCard
          title="LLM Calls Today"
          value={llm?.total_calls ?? 0}
          subtitle={`$${(llm?.total_cost_usd ?? 0).toFixed(4)} cost`}
          icon={Zap}
        />
        <KpiCard
          title="RAG Chunks"
          value={summary?.rag.chunks ?? 0}
          subtitle={summary?.rag.ok ? "Healthy" : "Unavailable"}
          icon={Database}
        />
        <KpiCard
          title="Memory Items"
          value={summary?.memory.total ?? 0}
          subtitle={summary?.memory.backend ?? "disabled"}
          icon={Cpu}
        />
      </div>

      {/* Missions list */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Missions</CardTitle>
        </CardHeader>
        <CardContent>
          {missions.length === 0 ? (
            <p className="text-gray-400 text-sm">
              No missions loaded. Add YAML files to the missions directory.
            </p>
          ) : (
            <div className="space-y-3">
              {missions.map((m) => (
                <div
                  key={m.name}
                  className="flex items-center justify-between p-3 rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <Bot className="h-4 w-4 text-blue-500" />
                      <span className="font-medium">{m.name}</span>
                      <Badge variant="secondary" className="text-xs">
                        {m.agent_tier}
                      </Badge>
                    </div>
                    <p className="text-sm text-gray-500 mt-1">
                      {m.description}
                    </p>
                  </div>
                  <div className="text-right text-sm text-gray-400">
                    {m.schedule ? (
                      <span className="font-mono">{m.schedule}</span>
                    ) : (
                      <span>Manual</span>
                    )}
                    <div>{m.steps_count} steps</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Tier usage */}
      {tierData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <DollarSign className="h-4 w-4" />
              LLM Tier Usage
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {tierData.map(([tier, stats]) => (
                <div
                  key={tier}
                  className="flex items-center justify-between p-2 rounded bg-gray-50"
                >
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">{tier}</Badge>
                    <span className="text-sm">{stats.calls} calls</span>
                  </div>
                  <div className="text-sm text-gray-500">
                    ${stats.cost.toFixed(4)} | {stats.last_latency_ms}ms
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
