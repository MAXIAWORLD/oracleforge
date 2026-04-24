"use client";

import { useEffect, useState } from "react";
import Navigation from "@/components/Navigation";
import TimeFilter from "@/components/TimeFilter";
import {
  Folder,
  DollarSign,
  TrendingUp,
  BarChart3,
  ArrowLeft,
} from "lucide-react";
import Link from "next/link";

interface Project {
  id: number;
  name: string;
  apiKey: string;
  budgetUsed: number;
  budgetTotal: number;
  callsToday: number;
  lastActivity: string;
}

interface UsageBreakdown {
  local_pct: number;
  cloud_pct: number;
  total_calls: number;
  providers: {
    [key: string]: {
      calls: number;
      cost_usd: number;
      tokens_in: number;
      tokens_out: number;
    };
  };
}

export default function ProjectDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const [project, setProject] = useState<Project | null>(null);
  const [breakdown, setBreakdown] = useState<UsageBreakdown | null>(null);
  const [dailyUsage, setDailyUsage] = useState<any[]>([]);
  const [selectedPeriod, setSelectedPeriod] = useState<string>("month");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Mock data pour le moment - à remplacer par API calls
    const mockProject: Project = {
      id: parseInt(params.id),
      name: "Production App",
      apiKey: "bf_1234567890abcdef",
      budgetUsed: 45.67,
      budgetTotal: 100.0,
      callsToday: 124,
      lastActivity: "2 heures",
    };

    const mockBreakdown: UsageBreakdown = {
      local_pct: 25.0,
      cloud_pct: 75.0,
      total_calls: 124,
      providers: {
        openai: {
          calls: 45,
          cost_usd: 12.34,
          tokens_in: 45000,
          tokens_out: 12000,
        },
        anthropic: {
          calls: 32,
          cost_usd: 8.76,
          tokens_in: 32000,
          tokens_out: 8500,
        },
        google: {
          calls: 28,
          cost_usd: 4.56,
          tokens_in: 28000,
          tokens_out: 7200,
        },
        ollama: {
          calls: 19,
          cost_usd: 0.0,
          tokens_in: 19000,
          tokens_out: 4800,
        },
      },
    };

    // Mock données quotidiennes selon la période
    const generateDailyData = (period: string) => {
      const today = new Date();
      const data = [];

      if (period === "today") {
        data.push({ date: today.toISOString().split("T")[0], spend: 0.011 });
      } else if (period === "7d") {
        for (let i = 6; i >= 0; i--) {
          const date = new Date(today);
          date.setDate(today.getDate() - i);
          data.push({
            date: date.toISOString().split("T")[0],
            spend: Math.random() * 0.02 + 0.005,
          });
        }
      } else if (period === "month") {
        for (let i = 29; i >= 0; i--) {
          const date = new Date(today);
          date.setDate(today.getDate() - i);
          data.push({
            date: date.toISOString().split("T")[0],
            spend: Math.random() * 0.015 + 0.003,
          });
        }
      } else {
        // all time
        for (let i = 59; i >= 0; i--) {
          const date = new Date(today);
          date.setDate(today.getDate() - i);
          data.push({
            date: date.toISOString().split("T")[0],
            spend: Math.random() * 0.01 + 0.002,
          });
        }
      }

      return data;
    };

    setProject(mockProject);
    setBreakdown(mockBreakdown);
    setDailyUsage(generateDailyData(selectedPeriod));
    setLoading(false);
  }, [params.id, selectedPeriod]);

  if (loading) {
    return (
      <div className="flex min-h-screen">
        <Navigation />
        <main className="flex-1 p-8 flex items-center justify-center">
          <div className="text-center">
            <div className="w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
            <p className="text-slate-400">Chargement du projet...</p>
          </div>
        </main>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="flex min-h-screen">
        <Navigation />
        <main className="flex-1 p-8 flex items-center justify-center">
          <div className="text-center">
            <h2 className="text-2xl font-bold text-white mb-2">
              Projet non trouvé
            </h2>
            <p className="text-slate-400 mb-4">
              Le projet que vous recherchez n'existe pas.
            </p>
            <Link
              href="/projects"
              className="text-purple-400 hover:text-purple-300"
            >
              ← Retour aux projets
            </Link>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <Navigation />

      <main className="flex-1 p-8">
        {/* En-tête */}
        <div className="flex justify-between items-start mb-8">
          <div className="flex items-center gap-4">
            <Link
              href="/projects"
              className="text-slate-400 hover:text-white transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div>
              <h1 className="text-4xl font-bold text-white mb-2">
                {project.name}
              </h1>
              <p className="text-slate-400 text-lg font-mono">
                {project.apiKey}
              </p>
            </div>
          </div>

          {/* Filtres temporels */}
          <TimeFilter
            selectedPeriod={selectedPeriod}
            onPeriodChange={setSelectedPeriod}
          />
        </div>

        {/* Statistiques rapides */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
            <div className="flex items-center gap-3 mb-2">
              <DollarSign className="w-6 h-6 text-green-400" />
              <h3 className="text-white font-semibold">Budget utilisé</h3>
            </div>
            <p className="text-2xl font-bold text-white">
              ${project.budgetUsed.toFixed(2)}
            </p>
            <p className="text-slate-400 text-sm">
              Sur un budget de ${project.budgetTotal.toFixed(2)}
            </p>
            <div className="mt-2 w-full bg-slate-700 rounded-full h-2">
              <div
                className="bg-gradient-to-r from-green-400 to-blue-400 h-2 rounded-full"
                style={{
                  width: `${(project.budgetUsed / project.budgetTotal) * 100}%`,
                }}
              ></div>
            </div>
          </div>

          <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
            <div className="flex items-center gap-3 mb-2">
              <TrendingUp className="w-6 h-6 text-blue-400" />
              <h3 className="text-white font-semibold">Requêtes aujourd'hui</h3>
            </div>
            <p className="text-2xl font-bold text-white">
              {project.callsToday}
            </p>
            <p className="text-slate-400 text-sm">
              Dernière activité : {project.lastActivity}
            </p>
          </div>

          <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
            <div className="flex items-center gap-3 mb-2">
              <BarChart3 className="w-6 h-6 text-purple-400" />
              <h3 className="text-white font-semibold">
                Répartition providers
              </h3>
            </div>
            {breakdown && (
              <>
                <div className="flex gap-4 mb-2">
                  <div className="text-center">
                    <div className="text-green-400 font-bold text-lg">
                      {breakdown.local_pct}%
                    </div>
                    <div className="text-slate-400 text-xs">Local</div>
                  </div>
                  <div className="text-center">
                    <div className="text-blue-400 font-bold text-lg">
                      {breakdown.cloud_pct}%
                    </div>
                    <div className="text-slate-400 text-xs">Cloud</div>
                  </div>
                </div>
                <div className="w-full bg-slate-700 rounded-full h-2">
                  <div
                    className="bg-gradient-to-r from-green-400 to-blue-400 h-2 rounded-full"
                    style={{ width: `${breakdown.local_pct}%` }}
                  ></div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Breakdown détaillé par provider */}
        {breakdown && (
          <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700 mb-8">
            <h2 className="text-2xl font-bold text-white mb-6">
              Répartition par provider
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {Object.entries(breakdown.providers).map(([provider, stats]) => (
                <div
                  key={provider}
                  className="bg-slate-900/50 rounded-lg p-4 border border-slate-700"
                >
                  <h3 className="text-white font-semibold mb-3 capitalize">
                    {provider}
                  </h3>

                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-slate-400 text-sm">Appels</span>
                      <span className="text-white font-medium">
                        {stats.calls}
                      </span>
                    </div>

                    <div className="flex justify-between">
                      <span className="text-slate-400 text-sm">Coût</span>
                      <span className="text-green-400 font-medium">
                        ${stats.cost_usd.toFixed(2)}
                      </span>
                    </div>

                    <div className="flex justify-between">
                      <span className="text-slate-400 text-sm">Tokens in</span>
                      <span className="text-blue-400 font-medium">
                        {stats.tokens_in.toLocaleString()}
                      </span>
                    </div>

                    <div className="flex justify-between">
                      <span className="text-slate-400 text-sm">Tokens out</span>
                      <span className="text-purple-400 font-medium">
                        {stats.tokens_out.toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Données quotidiennes */}
        <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700 mb-8">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-white">
              Évolution quotidienne
            </h2>
            <span className="text-slate-400">
              Période:{" "}
              {selectedPeriod === "today"
                ? "Aujourd'hui"
                : selectedPeriod === "7d"
                  ? "7 jours"
                  : selectedPeriod === "month"
                    ? "Ce mois"
                    : "All time"}
            </span>
          </div>

          {dailyUsage.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {dailyUsage
                .slice(-8)
                .reverse()
                .map((day) => (
                  <div
                    key={day.date}
                    className="bg-slate-900/50 rounded-lg p-4 border border-slate-700"
                  >
                    <div className="text-sm text-slate-400 mb-1">
                      {day.date}
                    </div>
                    <div className="text-lg font-bold text-green-400">
                      ${day.spend.toFixed(2)}
                    </div>
                  </div>
                ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <BarChart3 className="w-12 h-12 text-slate-600 mx-auto mb-4" />
              <p className="text-slate-400">
                Aucune donnée disponible pour cette période
              </p>
            </div>
          )}
        </div>

        {/* Graphique donut (placeholder pour le moment) */}
        <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
          <h2 className="text-2xl font-bold text-white mb-6">
            Répartition graphique
          </h2>

          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <BarChart3 className="w-16 h-16 text-slate-600 mx-auto mb-4" />
              <p className="text-slate-400">
                Graphique donut providers en cours de développement
              </p>
              <p className="text-slate-500 text-sm mt-2">
                Utilisez la répartition détaillée ci-dessus
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
