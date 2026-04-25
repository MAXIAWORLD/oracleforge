"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, Zap, Settings, Folder } from "lucide-react";

const navigation = [
  { name: "Dashboard", href: "/", icon: Home },
  { name: "Projects", href: "/projects", icon: Folder },
  { name: "API Keys", href: "/api-keys", icon: Zap },
  { name: "Settings", href: "/settings", icon: Settings },
];

export default function Navigation() {
  const pathname = usePathname();

  return (
    <nav className="bg-slate-900 border-r border-slate-700 w-64 min-h-screen">
      <div className="p-6">
        {/* Logo */}
        <div className="flex items-center gap-3 mb-8">
          <div className="w-8 h-8 bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg flex items-center justify-center">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <span className="text-white font-bold text-xl">BudgetForge</span>
        </div>

        {/* Navigation */}
        <div className="space-y-2">
          {navigation.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;

            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 ${
                  isActive
                    ? "bg-gradient-to-r from-purple-500/20 to-pink-500/20 text-white border-l-4 border-purple-500"
                    : "text-slate-400 hover:text-white hover:bg-slate-800"
                }`}
              >
                <Icon className="w-5 h-5" />
                <span className="font-medium">{item.name}</span>
              </Link>
            );
          })}
        </div>

        {/* Status */}
        <div className="mt-8 p-4 bg-slate-800/50 rounded-lg border border-slate-700">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
            <span className="text-green-400 text-sm font-medium">
              API Online
            </span>
          </div>
          <p className="text-slate-400 text-xs">BudgetForge est opérationnel</p>
        </div>
      </div>
    </nav>
  );
}
