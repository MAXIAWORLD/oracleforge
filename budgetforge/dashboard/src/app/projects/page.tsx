import Navigation from "@/components/Navigation";
import { Folder, Plus, DollarSign, TrendingUp } from "lucide-react";

export default function ProjectsPage() {
  // Données mock pour le moment - à remplacer par API call
  const projects = [
    {
      id: 1,
      name: "Production App",
      apiKey: "bf_1234567890abcdef",
      budgetUsed: 45.67,
      budgetTotal: 100.0,
      callsToday: 124,
      lastActivity: "2 heures",
    },
    {
      id: 2,
      name: "Staging Environment",
      apiKey: "bf_abcdef123456789",
      budgetUsed: 12.34,
      budgetTotal: 50.0,
      callsToday: 45,
      lastActivity: "5 heures",
    },
    {
      id: 3,
      name: "Development Sandbox",
      apiKey: "bf_7890abcdef123456",
      budgetUsed: 8.9,
      budgetTotal: 25.0,
      callsToday: 23,
      lastActivity: "1 jour",
    },
  ];

  return (
    <div className="flex min-h-screen">
      <Navigation />

      <main className="flex-1 p-8">
        {/* En-tête */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-4xl font-bold text-white mb-2">Projets</h1>
            <p className="text-slate-400 text-lg">
              Gérez vos projets et surveillez leur utilisation
            </p>
          </div>

          <button className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white px-6 py-3 rounded-lg font-semibold transition-all duration-200 flex items-center gap-2">
            <Plus className="w-5 h-5" />
            Nouveau projet
          </button>
        </div>

        {/* Liste des projets */}
        <div className="grid gap-6">
          {projects.map((project) => (
            <div
              key={project.id}
              className="bg-slate-800/50 rounded-lg p-6 border border-slate-700 hover:border-slate-600 transition-colors cursor-pointer"
            >
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center gap-3">
                  <Folder className="w-8 h-8 text-purple-400" />
                  <div>
                    <h3 className="text-white font-bold text-xl">
                      {project.name}
                    </h3>
                    <p className="text-slate-400 text-sm font-mono">
                      {project.apiKey}
                    </p>
                  </div>
                </div>

                <div className="text-right">
                  <div className="flex items-center gap-2 text-green-400 mb-1">
                    <DollarSign className="w-4 h-4" />
                    <span className="font-bold">
                      ${project.budgetUsed.toFixed(2)}
                    </span>
                    <span className="text-slate-400">
                      / ${project.budgetTotal.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-blue-400">
                    <TrendingUp className="w-4 h-4" />
                    <span>{project.callsToday} appels aujourd'hui</span>
                  </div>
                </div>
              </div>

              <div className="flex justify-between items-center text-sm text-slate-400">
                <span>Dernière activité : {project.lastActivity}</span>
                <a
                  href={`/projects/${project.id}`}
                  className="text-purple-400 hover:text-purple-300 transition-colors"
                >
                  Voir les détails →
                </a>
              </div>
            </div>
          ))}
        </div>

        {/* État vide */}
        {projects.length === 0 && (
          <div className="text-center py-12">
            <Folder className="w-16 h-16 text-slate-600 mx-auto mb-4" />
            <h3 className="text-white text-xl font-semibold mb-2">
              Aucun projet
            </h3>
            <p className="text-slate-400 mb-6">
              Créez votre premier projet pour commencer à utiliser BudgetForge
            </p>
            <button className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white px-6 py-3 rounded-lg font-semibold transition-all duration-200 flex items-center gap-2 mx-auto">
              <Plus className="w-5 h-5" />
              Créer un projet
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
