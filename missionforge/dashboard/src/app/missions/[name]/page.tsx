"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Bot, Play } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { api, type MissionDetail, type RunResponse } from "@/lib/api";

export default function MissionDetailPage() {
  const params = useParams();
  const name = typeof params.name === "string" ? decodeURIComponent(params.name) : "";
  const [mission, setMission] = useState<MissionDetail | null>(null);
  const [runResult, setRunResult] = useState<RunResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!name) return;
    api.getMission(name).then(setMission).catch((e) => setError(e.message));
  }, [name]);

  const handleRun = async () => {
    setRunning(true);
    setRunResult(null);
    try {
      const result = await api.runMission(name);
      setRunResult(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Run failed");
    } finally {
      setRunning(false);
    }
  };

  if (error) {
    return (
      <div className="p-8">
        <p className="text-red-600">{error}</p>
      </div>
    );
  }
  if (!mission) {
    return <div className="p-8 text-gray-400">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/missions" className="text-gray-400 hover:text-gray-600">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Bot className="h-6 w-6 text-blue-500" />
            {mission.name}
          </h1>
          <p className="text-gray-500 text-sm">{mission.description}</p>
        </div>
        <Button onClick={handleRun} disabled={running}>
          <Play className="h-4 w-4 mr-2" />
          {running ? "Running..." : "Run Now"}
        </Button>
      </div>

      {/* Agent config */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-gray-500">Agent</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3 mb-2">
            <Badge>{mission.agent.llm_tier}</Badge>
            {mission.schedule && (
              <Badge variant="outline" className="font-mono">
                {mission.schedule}
              </Badge>
            )}
          </div>
          <p className="text-sm text-gray-600 bg-gray-50 p-3 rounded">
            {mission.agent.system_prompt}
          </p>
        </CardContent>
      </Card>

      {/* Steps */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm text-gray-500">
            Steps ({mission.steps.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {mission.steps.map((step, i) => (
              <div key={i}>
                {i > 0 && <Separator className="mb-3" />}
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-xs font-bold">
                    {i + 1}
                  </div>
                  <div className="flex-1">
                    <Badge variant="secondary" className="mb-1">
                      {String(step.action)}
                    </Badge>
                    <pre className="text-xs bg-gray-50 p-2 rounded mt-1 overflow-x-auto">
                      {JSON.stringify(
                        Object.fromEntries(
                          Object.entries(step).filter(
                            ([k, v]) =>
                              k !== "action" &&
                              v !== null &&
                              v !== 500 &&
                              v !== 6 &&
                              v !== "POST"
                          )
                        ),
                        null,
                        2
                      )}
                    </pre>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

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
              Execution — {runResult.status}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm mb-3">
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
              <div className="p-3 bg-white rounded border text-xs font-mono space-y-1">
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
