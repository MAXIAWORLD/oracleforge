"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bot, Play, RefreshCw, Rocket } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, type MissionSummary, type RunResponse } from "@/lib/api";

export default function MissionsPage() {
  const [missions, setMissions] = useState<MissionSummary[]>([]);
  const [runResult, setRunResult] = useState<RunResponse | null>(null);
  const [running, setRunning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const data = await api.listMissions();
      setMissions(data.missions);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleRun = async (name: string) => {
    setRunning(name);
    setRunResult(null);
    try {
      const result = await api.runMission(name);
      setRunResult(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Run failed");
    } finally {
      setRunning(null);
    }
  };

  const handleReload = async () => {
    try {
      await api.reloadMissions();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reload failed");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Rocket className="h-6 w-6" />
            Missions
          </h1>
          <p className="text-gray-500 text-sm">
            {missions.length} missions loaded
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleReload}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Reload
        </Button>
      </div>

      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-4">
            <p className="text-red-600 text-sm">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Mission cards */}
      <div className="grid gap-4">
        {missions.map((m) => (
          <Card key={m.name} className="hover:shadow-md transition-shadow">
            <CardContent className="pt-6">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <Link
                    href={`/missions/${encodeURIComponent(m.name)}`}
                    className="flex items-center gap-2 hover:underline"
                  >
                    <Bot className="h-5 w-5 text-blue-500" />
                    <h3 className="font-semibold text-lg">{m.name}</h3>
                  </Link>
                  <p className="text-gray-500 text-sm mt-1">
                    {m.description || "No description"}
                  </p>
                  <div className="flex items-center gap-3 mt-3">
                    <Badge variant="secondary">{m.agent_tier}</Badge>
                    <span className="text-sm text-gray-400">
                      {m.steps_count} steps
                    </span>
                    {m.schedule && (
                      <Badge variant="outline" className="font-mono text-xs">
                        {m.schedule}
                      </Badge>
                    )}
                  </div>
                </div>
                <Button
                  size="sm"
                  onClick={() => handleRun(m.name)}
                  disabled={running === m.name}
                >
                  <Play className="h-4 w-4 mr-1" />
                  {running === m.name ? "Running..." : "Run"}
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Run result */}
      {runResult && (
        <Card
          className={
            runResult.status === "success"
              ? "border-green-200 bg-green-50"
              : "border-red-200 bg-red-50"
          }
        >
          <CardHeader>
            <CardTitle className="text-sm">
              Run: {runResult.mission_name} — {runResult.status}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-gray-500">Steps:</span>{" "}
                {runResult.steps_completed}/{runResult.total_steps}
              </div>
              <div>
                <span className="text-gray-500">Duration:</span>{" "}
                {runResult.duration_ms}ms
              </div>
              <div>
                <span className="text-gray-500">Tokens:</span>{" "}
                {runResult.tokens_used}
              </div>
              <div>
                <span className="text-gray-500">Cost:</span> $
                {runResult.cost_usd.toFixed(4)}
              </div>
            </div>
            {runResult.logs.length > 0 && (
              <div className="mt-3 p-3 bg-white rounded border text-xs font-mono space-y-1">
                {runResult.logs.map((log, i) => (
                  <div key={i} className="text-gray-600">
                    {log}
                  </div>
                ))}
              </div>
            )}
            {runResult.error_message && (
              <p className="mt-2 text-red-600 text-sm">
                {runResult.error_message}
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
