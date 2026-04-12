"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useTheme } from "next-themes";
import {
  Bot, Cpu, Database, Rocket, Zap, Clock, CheckCircle2,
  AlertCircle, ArrowUp, ArrowDown, Activity, Play,
  MessageSquare, TrendingUp, Shield, BarChart3,
} from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, BarChart, Bar, RadialBarChart, RadialBar,
} from "recharts";
import { api, type ObservabilitySummary, type MissionSummary } from "@/lib/api";

/* ── Mock data ── */
const H24 = Array.from({ length: 24 }, (_, i) => ({
  t: `${String(i).padStart(2, "0")}h`,
  calls: Math.floor(Math.random() * 40 + 8),
  cost: +(Math.random() * 0.03).toFixed(4),
}));
const TIERS = [
  { name: "Local", v: 40, c: "#00e5ff" },
  { name: "Fast", v: 28, c: "#b44aff" },
  { name: "Mid", v: 18, c: "#ff2d87" },
  { name: "Strategic", v: 14, c: "#ffb800" },
];
const WEEK = [
  { d: "Lun", r: 14, s: 13 }, { d: "Mar", r: 9, s: 8 }, { d: "Mer", r: 17, s: 15 },
  { d: "Jeu", r: 11, s: 11 }, { d: "Ven", r: 21, s: 19 }, { d: "Sam", r: 6, s: 6 }, { d: "Dim", r: 4, s: 4 },
];

export default function Page() {
  const [sum, setSum] = useState<ObservabilitySummary | null>(null);
  const [mis, setMis] = useState<MissionSummary[]>([]);
  const [err, setErr] = useState("");
  const { resolvedTheme: th } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);
  useEffect(() => {
    const l = async () => {
      try {
        const [s, m] = await Promise.all([api.observabilitySummary(), api.listMissions()]);
        setSum(s); setMis(m.missions);
      } catch (e: any) { setErr(e.message); }
    };
    l(); const i = setInterval(l, 12000); return () => clearInterval(i);
  }, []);

  if (!mounted) return null;

  const dk = th === "dark";
  const bg = dk ? "#0b0e1a" : "#f5f6fa";
  const card = dk ? "#111427" : "#ffffff";
  const border = dk ? "#1e2245" : "#e8eaf0";
  const txt = dk ? "#e2e4f0" : "#1a1d2e";
  const txt2 = dk ? "#6b7194" : "#8b8fa8";
  const txt3 = dk ? "#3a3f5c" : "#c0c4d4";
  const hover = dk ? "#1a1d35" : "#f0f1f5";
  const ttBg = dk ? "#1a1d35" : "#ffffff";
  const llm = sum?.llm;

  if (err) return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "80vh" }}>
      <div style={{ background: card, border: `1px solid ${border}`, borderRadius: 20, padding: 48, textAlign: "center", maxWidth: 420 }}>
        <AlertCircle size={48} color="#ff3b5c" style={{ margin: "0 auto 16px" }} />
        <p style={{ fontWeight: 700, fontSize: 18, color: txt }}>Backend Unavailable</p>
        <p style={{ fontSize: 13, color: txt2, marginTop: 8 }}>{err}</p>
        <code style={{ display: "block", fontSize: 12, background: dk ? "#0b0e1a" : "#f5f6fa", borderRadius: 12, padding: 16, marginTop: 20, color: txt2 }}>
          uvicorn main:app --port 8001
        </code>
      </div>
    </div>
  );

  const kpis = [
    { l: "Missions", v: sum?.missions.total ?? 0, s: `${sum?.missions.scheduled ?? 0} scheduled`, d: 12, ic: Rocket, g1: "#3b82f6", g2: "#6366f1" },
    { l: "LLM Calls", v: llm?.total_calls ?? 0, s: `$${(llm?.total_cost_usd ?? 0).toFixed(4)}`, d: -3, ic: Zap, g1: "#b44aff", g2: "#8b5cf6" },
    { l: "RAG Chunks", v: sum?.rag.chunks ?? 0, s: sum?.rag.ok ? "Healthy" : "Down", d: undefined, ic: Database, g1: "#00e5ff", g2: "#06b6d4" },
    { l: "Memory", v: sum?.memory.total ?? 0, s: sum?.memory.backend ?? "off", d: 8, ic: Cpu, g1: "#ffb800", g2: "#f59e0b" },
  ];

  const gauges = [
    { l: "API", v: 100, c: "#0afe7e" },
    { l: "ChromaDB", v: sum?.rag.ok ? 100 : 0, c: "#00e5ff" },
    { l: "Memory", v: 100, c: "#b44aff" },
    { l: "Engine", v: 100, c: "#ffb800" },
  ];

  return (
    <div style={{ maxWidth: 1440, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h1 style={{ fontSize: 22, fontWeight: 800, color: txt, letterSpacing: -0.5 }}>Dashboard</h1>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4, background: dk ? "rgba(10,254,126,0.1)" : "rgba(16,185,129,0.1)", color: "#0afe7e", fontSize: 10, fontWeight: 700, padding: "3px 10px", borderRadius: 20 }}>
              <Activity size={10} className="animate-pulse" /> LIVE
            </span>
          </div>
          <p style={{ fontSize: 12, color: txt2, marginTop: 2 }}>MissionForge AI Agent Framework</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Link href="/chat">
            <button style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 14px", borderRadius: 10, fontSize: 12, fontWeight: 600, border: `1px solid ${border}`, background: card, color: txt2, cursor: "pointer" }}>
              <MessageSquare size={13} /> Chat
            </button>
          </Link>
          <Link href="/missions">
            <button style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 14px", borderRadius: 10, fontSize: 12, fontWeight: 600, border: "none", background: "linear-gradient(135deg, #3b82f6, #8b5cf6)", color: "#fff", cursor: "pointer", boxShadow: "0 4px 15px rgba(59,130,246,0.3)" }}>
              <Play size={13} /> Run Mission
            </button>
          </Link>
        </div>
      </div>

      {/* KPI Row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 16 }}>
        {kpis.map((k, i) => (
          <div key={i} style={{ background: card, border: `1px solid ${border}`, borderRadius: 16, padding: 20, position: "relative", overflow: "hidden", transition: "border-color 0.2s, box-shadow 0.2s" }}
            onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.borderColor = k.g1; (e.currentTarget as HTMLDivElement).style.boxShadow = `0 0 25px ${k.g1}22`; }}
            onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.borderColor = border; (e.currentTarget as HTMLDivElement).style.boxShadow = "none"; }}>
            <div style={{ position: "absolute", top: -20, right: -20, width: 80, height: 80, borderRadius: "50%", background: `linear-gradient(135deg, ${k.g1}, ${k.g2})`, opacity: 0.08, filter: "blur(20px)" }} />
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", position: "relative" }}>
              <div>
                <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: 1.5, color: txt2, textTransform: "uppercase" }}>{k.l}</p>
                <p style={{ fontSize: 32, fontWeight: 800, color: txt, marginTop: 4, letterSpacing: -1 }}>{k.v}</p>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
                  <span style={{ fontSize: 11, color: txt2 }}>{k.s}</span>
                  {k.d !== undefined && (
                    <span style={{ fontSize: 11, fontWeight: 600, color: k.d >= 0 ? "#0afe7e" : "#ff3b5c", display: "flex", alignItems: "center", gap: 2 }}>
                      {k.d >= 0 ? <ArrowUp size={12} /> : <ArrowDown size={12} />}{Math.abs(k.d)}%
                    </span>
                  )}
                </div>
              </div>
              <div style={{ width: 44, height: 44, borderRadius: 14, background: `linear-gradient(135deg, ${k.g1}, ${k.g2})`, display: "flex", alignItems: "center", justifyContent: "center", boxShadow: `0 8px 20px ${k.g1}33` }}>
                <k.ic size={20} color="#fff" />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Charts Row */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16, marginBottom: 16 }}>
        {/* Area Chart */}
        <div style={{ background: card, border: `1px solid ${border}`, borderRadius: 16, padding: 20 }}>
          <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1.2, color: txt2, textTransform: "uppercase", marginBottom: 16, display: "flex", alignItems: "center", gap: 6 }}>
            <TrendingUp size={14} color="#00e5ff" /> LLM Usage 24h
          </p>
          <div style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={H24}>
                <defs>
                  <linearGradient id="ga" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="t" tick={{ fontSize: 9, fill: txt3 }} tickLine={false} axisLine={false} interval={3} />
                <YAxis tick={{ fontSize: 9, fill: txt3 }} tickLine={false} axisLine={false} width={28} />
                <Tooltip contentStyle={{ background: ttBg, border: `1px solid ${border}`, borderRadius: 10, fontSize: 11, color: txt, boxShadow: "0 8px 24px rgba(0,0,0,0.2)" }} />
                <Area type="monotone" dataKey="calls" stroke="#3b82f6" strokeWidth={2.5} fill="url(#ga)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Pie Chart */}
        <div style={{ background: card, border: `1px solid ${border}`, borderRadius: 16, padding: 20 }}>
          <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1.2, color: txt2, textTransform: "uppercase", marginBottom: 12, display: "flex", alignItems: "center", gap: 6 }}>
            <BarChart3 size={14} color="#b44aff" /> Tier Split
          </p>
          <div style={{ height: 160 }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={TIERS} cx="50%" cy="50%" innerRadius={48} outerRadius={70} dataKey="v" stroke="none" paddingAngle={3}>
                  {TIERS.map((t, i) => <Cell key={i} fill={t.c} />)}
                </Pie>
                <Tooltip contentStyle={{ background: ttBg, border: `1px solid ${border}`, borderRadius: 10, fontSize: 11, color: txt }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div style={{ display: "flex", justifyContent: "center", gap: 14, marginTop: 8 }}>
            {TIERS.map(t => (
              <div key={t.name} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <div style={{ width: 8, height: 8, borderRadius: 4, background: t.c }} />
                <span style={{ fontSize: 10, color: txt2, fontWeight: 500 }}>{t.name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom Row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
        {/* Bar Chart */}
        <div style={{ background: card, border: `1px solid ${border}`, borderRadius: 16, padding: 20 }}>
          <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1.2, color: txt2, textTransform: "uppercase", marginBottom: 16, display: "flex", alignItems: "center", gap: 6 }}>
            <Rocket size={14} color="#3b82f6" /> Weekly Runs
          </p>
          <div style={{ height: 150 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={WEEK} barGap={2}>
                <XAxis dataKey="d" tick={{ fontSize: 9, fill: txt3 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 9, fill: txt3 }} tickLine={false} axisLine={false} width={22} />
                <Tooltip contentStyle={{ background: ttBg, border: `1px solid ${border}`, borderRadius: 10, fontSize: 11, color: txt }} />
                <Bar dataKey="r" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                <Bar dataKey="s" fill="#0afe7e" radius={[4, 4, 0, 0]} opacity={0.7} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Missions */}
        <div style={{ background: card, border: `1px solid ${border}`, borderRadius: 16, padding: 20 }}>
          <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1.2, color: txt2, textTransform: "uppercase", marginBottom: 16, display: "flex", alignItems: "center", gap: 6 }}>
            <Bot size={14} color="#ff2d87" /> Active Missions
          </p>
          {mis.map(m => (
            <Link key={m.name} href={`/missions/${encodeURIComponent(m.name)}`} style={{ textDecoration: "none" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 12px", borderRadius: 12, marginBottom: 6, cursor: "pointer", transition: "background 0.15s" }}
                onMouseEnter={e => (e.currentTarget.style.background = hover)}
                onMouseLeave={e => (e.currentTarget.style.background = "transparent")}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={{ width: 34, height: 34, borderRadius: 10, background: dk ? "rgba(59,130,246,0.1)" : "#eef2ff", display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <Bot size={16} color="#3b82f6" />
                  </div>
                  <div>
                    <p style={{ fontSize: 13, fontWeight: 600, color: txt }}>{m.name}</p>
                    <p style={{ fontSize: 10, color: txt2 }}>{m.steps_count} steps {m.schedule && `| ${m.schedule}`}</p>
                  </div>
                </div>
                <span style={{ fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 6, background: dk ? "rgba(139,92,246,0.1)" : "#f3f0ff", color: "#8b5cf6" }}>{m.agent_tier}</span>
              </div>
            </Link>
          ))}
          {mis.length === 0 && <p style={{ fontSize: 12, color: txt3, textAlign: "center", padding: 24 }}>No missions</p>}
        </div>

        {/* Health Gauges */}
        <div style={{ background: card, border: `1px solid ${border}`, borderRadius: 16, padding: 20 }}>
          <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1.2, color: txt2, textTransform: "uppercase", marginBottom: 16, display: "flex", alignItems: "center", gap: 6 }}>
            <Shield size={14} color="#0afe7e" /> System Health
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 8 }}>
            {gauges.map(g => (
              <div key={g.l} style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                <div style={{ width: 72, height: 72, position: "relative" }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <RadialBarChart cx="50%" cy="50%" innerRadius="70%" outerRadius="100%" startAngle={90} endAngle={-270} data={[{ v: g.v, fill: g.c }]}>
                      <RadialBar dataKey="v" cornerRadius={10} background={{ fill: dk ? "#1e2245" : "#f0f1f5" }} />
                    </RadialBarChart>
                  </ResponsiveContainer>
                  <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <span style={{ fontSize: 13, fontWeight: 800, color: txt }}>{g.v}%</span>
                  </div>
                </div>
                <span style={{ fontSize: 10, color: txt2, fontWeight: 600, marginTop: 4 }}>{g.l}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
