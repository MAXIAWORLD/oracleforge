import type { LucideIcon } from "lucide-react";
import {
  Crosshair,
  BrainCircuit,
  Eye,
  Shield,
  KeyRound,
  Mail,
} from "lucide-react";

export interface ProductConfig {
  readonly id: string;
  readonly name: string;
  readonly icon: LucideIcon;
  readonly color: string;
  readonly glowColor: string;
  readonly backendPort: number;
  readonly dashboardPort: number;
  readonly metricKey: string;
}

export const PRODUCTS: readonly ProductConfig[] = [
  {
    id: "missionforge",
    name: "MissionForge",
    icon: Crosshair,
    color: "text-neon-cyan",
    glowColor: "#00e5ff",
    backendPort: 8001,
    dashboardPort: 3000,
    metricKey: "missions_loaded",
  },
  {
    id: "llmforge",
    name: "LLMForge",
    icon: BrainCircuit,
    color: "text-neon-violet",
    glowColor: "#b44aff",
    backendPort: 8002,
    dashboardPort: 3001,
    metricKey: "providers_configured",
  },
  {
    id: "oracleforge",
    name: "OracleForge",
    icon: Eye,
    color: "text-neon-amber",
    glowColor: "#ffb800",
    backendPort: 8003,
    dashboardPort: 3002,
    metricKey: "status",
  },
  {
    id: "guardforge",
    name: "GuardForge",
    icon: Shield,
    color: "text-neon-green",
    glowColor: "#0afe7e",
    backendPort: 8004,
    dashboardPort: 3003,
    metricKey: "status",
  },
  {
    id: "authforge",
    name: "AuthForge",
    icon: KeyRound,
    color: "text-neon-blue",
    glowColor: "#3b82f6",
    backendPort: 8005,
    dashboardPort: 3004,
    metricKey: "status",
  },
  {
    id: "outreachforge",
    name: "OutreachForge",
    icon: Mail,
    color: "text-neon-pink",
    glowColor: "#ff2d87",
    backendPort: 8006,
    dashboardPort: 3005,
    metricKey: "status",
  },
] as const;
