import Navigation from "@/components/Navigation";
import { Zap, TrendingUp, Shield, DollarSign } from "lucide-react";

export default function HomePage() {
  return (
    <div className="flex min-h-screen">
      <Navigation />

      <main className="flex-1 p-8">
        {/* En-tête */}
        <div className="flex justify-between items-start mb-8">
          <div>
            <h1 className="text-4xl font-bold text-white mb-2">
              Bienvenue sur BudgetForge
            </h1>
            <p className="text-slate-400 text-lg">
              Gérez vos coûts LLM avec contrôle intelligent du budget
            </p>
          </div>

          {/* Filtres temporels */}
          <div className="flex gap-2 bg-slate-800/50 rounded-lg p-1 border border-slate-700">
            <button className="px-4 py-2 rounded-md text-slate-300 hover:text-white hover:bg-slate-700 transition-colors">
              Aujourd'hui
            </button>
            <button className="px-4 py-2 rounded-md text-slate-300 hover:text-white hover:bg-slate-700 transition-colors">
              7 jours
            </button>
            <button className="px-4 py-2 rounded-md bg-slate-700 text-white">
              Ce mois
            </button>
            <button className="px-4 py-2 rounded-md text-slate-300 hover:text-white hover:bg-slate-700 transition-colors">
              All time
            </button>
          </div>
        </div>

        {/* Statistiques rapides */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
            <div className="flex items-center gap-3 mb-2">
              <DollarSign className="w-6 h-6 text-green-400" />
              <h3 className="text-white font-semibold">Budget utilisé</h3>
            </div>
            <p className="text-2xl font-bold text-white">$0.00</p>
            <p className="text-slate-400 text-sm">Sur un budget de $100.00</p>
          </div>

          <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
            <div className="flex items-center gap-3 mb-2">
              <TrendingUp className="w-6 h-6 text-blue-400" />
              <h3 className="text-white font-semibold">Requêtes aujourd'hui</h3>
            </div>
            <p className="text-2xl font-bold text-white">0</p>
            <p className="text-slate-400 text-sm">
              Aucune activité aujourd'hui
            </p>
          </div>

          <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
            <div className="flex items-center gap-3 mb-2">
              <Shield className="w-6 h-6 text-purple-400" />
              <h3 className="text-white font-semibold">Status API</h3>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
              <span className="text-green-400 font-semibold">Opérationnel</span>
            </div>
            <p className="text-slate-400 text-sm mt-1">
              Tous les providers disponibles
            </p>
          </div>
        </div>

        {/* Actions rapides */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-slate-800/50 rounded-lg p-6 border border-slate-700">
            <h3 className="text-white font-bold text-xl mb-4">
              Documentation API
            </h3>
            <p className="text-slate-300 mb-4">
              Intégrez BudgetForge dans vos applications avec notre SDK complet.
              Documentation détaillée et exemples de code.
            </p>
            <div className="space-y-3">
              <a
                href="/docs"
                className="block text-blue-400 hover:text-blue-300"
              >
                • Guide d'intégration
              </a>
              <a
                href="/api-reference"
                className="block text-blue-400 hover:text-blue-300"
              >
                • Référence API
              </a>
              <a
                href="/examples"
                className="block text-blue-400 hover:text-blue-300"
              >
                • Exemples de code
              </a>
            </div>
          </div>
        </div>

        {/* Section fonctionnalités */}
        <div className="mt-12">
          <h2 className="text-2xl font-bold text-white mb-6">
            Fonctionnalités principales
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-slate-800/30 rounded-lg p-6">
              <Shield className="w-8 h-8 text-green-400 mb-3" />
              <h3 className="text-white font-semibold mb-2">
                Enforcement du budget
              </h3>
              <p className="text-slate-400">
                Bloquez automatiquement les requêtes lorsque votre budget est
                dépassé.
              </p>
            </div>

            <div className="bg-slate-800/30 rounded-lg p-6">
              <TrendingUp className="w-8 h-8 text-blue-400 mb-3" />
              <h3 className="text-white font-semibold mb-2">
                Analytics détaillées
              </h3>
              <p className="text-slate-400">
                Suivez vos dépenses par provider, modèle et projet.
              </p>
            </div>

            <div className="bg-slate-800/30 rounded-lg p-6">
              <Zap className="w-8 h-8 text-purple-400 mb-3" />
              <h3 className="text-white font-semibold mb-2">
                Fallback intelligent
              </h3>
              <p className="text-slate-400">
                Basculez automatiquement vers des providers moins chers.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
