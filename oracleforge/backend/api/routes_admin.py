"""MAXIA Oracle — admin dashboard (read-only stats)."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter(tags=["admin"])

_ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")


def _check_auth(request: Request) -> bool:
    token = request.headers.get("X-Admin-Token") or request.query_params.get("token")
    return bool(_ADMIN_TOKEN and token == _ADMIN_TOKEN)


def _stats() -> dict:
    db_path = os.getenv("DB_PATH", "/var/lib/maxia-oracle/db.sqlite")
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    total_keys = cur.execute("SELECT COUNT(*) FROM api_keys").fetchone()[0]
    keys_today = cur.execute(
        "SELECT COUNT(*) FROM api_keys WHERE created_at >= strftime('%s', 'now', 'start of day')"
    ).fetchone()[0]
    keys_7d = cur.execute(
        "SELECT COUNT(*) FROM api_keys WHERE created_at >= strftime('%s', 'now', '-7 days')"
    ).fetchone()[0]

    x402_calls = cur.execute("SELECT COUNT(*) FROM x402_txs").fetchone()[0]
    x402_usdc = cur.execute("SELECT ROUND(COALESCE(SUM(amount_usdc),0),4) FROM x402_txs").fetchone()[0]
    x402_today = cur.execute(
        "SELECT COUNT(*), ROUND(COALESCE(SUM(amount_usdc),0),4) FROM x402_txs "
        "WHERE created_at >= strftime('%s', 'now', 'start of day')"
    ).fetchone()

    x402_recent = cur.execute(
        "SELECT tx_hash, amount_usdc, path, chain, datetime(created_at, 'unixepoch') "
        "FROM x402_txs ORDER BY created_at DESC LIMIT 10"
    ).fetchall()

    alerts = cur.execute("SELECT COUNT(*) FROM price_alerts").fetchone()[0]
    snapshots = cur.execute("SELECT COUNT(*) FROM price_snapshots").fetchone()[0]

    daily = cur.execute(
        "SELECT date(created_at, 'unixepoch') as day, COUNT(*) "
        "FROM x402_txs GROUP BY day ORDER BY day DESC LIMIT 7"
    ).fetchall()

    con.close()
    return {
        "keys": {"total": total_keys, "today": keys_today, "last_7d": keys_7d},
        "x402": {
            "total_calls": x402_calls,
            "total_usdc": x402_usdc,
            "today_calls": x402_today[0],
            "today_usdc": x402_today[1],
            "recent": [
                {"tx": r[0][:12] + "...", "usdc": r[1], "path": r[2], "chain": r[3], "at": r[4]}
                for r in x402_recent
            ],
            "daily": [{"day": r[0], "calls": r[1]} for r in daily],
        },
        "alerts": alerts,
        "snapshots": snapshots,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/admin/stats")
async def admin_stats(request: Request) -> JSONResponse:
    if not _check_auth(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return JSONResponse(_stats())


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request) -> HTMLResponse:
    if not _check_auth(request):
        return HTMLResponse(
            "<html><body style='font-family:monospace;padding:2rem'>"
            "<h2>401 — X-Admin-Token required</h2></body></html>",
            status_code=401,
        )
    s = _stats()
    k = s["keys"]
    x = s["x402"]

    max_calls = max((r["calls"] for r in x["daily"]), default=1) or 1

    rows_recent = "".join(
        f"<tr><td class='dim'>{r['at']}</td><td class='path'>{r['path']}</td>"
        f"<td class='usdc'>+${r['usdc']}</td><td class='chain'>{r['chain']}</td>"
        f"<td class='tx'>{r['tx']}</td></tr>"
        for r in x["recent"]
    )

    bars = "".join(
        f"""<div class="bar-row">
          <span class="bar-label">{r['day']}</span>
          <div class="bar-track"><div class="bar-fill" style="width:{int(r['calls']/max_calls*100)}%"></div></div>
          <span class="bar-val">{r['calls']}</span>
        </div>"""
        for r in x["daily"]
    )

    html = f"""<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<meta http-equiv="refresh" content="30">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MAXIA Oracle — Admin</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
[data-theme="dark"] {{
  --bg:       #0f1117;
  --surface:  #181b23;
  --surface2: #1f2330;
  --border:   #2a2d3a;
  --text:     #e2e4ef;
  --muted:    #7c8098;
  --subtle:   #4a4d60;
  --accent:   #6366f1;
  --accent2:  #818cf8;
  --green:    #34d399;
  --blue:     #60a5fa;
  --red:      #f87171;
  --shadow:   rgba(0,0,0,.4);
}}
[data-theme="light"] {{
  --bg:       #f4f5f9;
  --surface:  #ffffff;
  --surface2: #f0f1f5;
  --border:   #e2e4ed;
  --text:     #1a1d2e;
  --muted:    #6b7080;
  --subtle:   #9ca3b0;
  --accent:   #6366f1;
  --accent2:  #4f46e5;
  --green:    #10b981;
  --blue:     #3b82f6;
  --red:      #ef4444;
  --shadow:   rgba(0,0,0,.08);
}}

*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

body {{
  font-family: 'Inter', system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  font-size: 14px;
  line-height: 1.5;
  transition: background .2s, color .2s;
}}

.wrap {{
  max-width: 1100px;
  margin: 0 auto;
  padding: 2rem 1.5rem 4rem;
}}

/* ── Header ── */
header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 1.5rem;
  margin-bottom: 2rem;
  border-bottom: 1px solid var(--border);
  flex-wrap: wrap;
  gap: 1rem;
}}
.logo {{
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: .04em;
  color: var(--text);
  display: flex;
  align-items: center;
  gap: .6rem;
}}
.logo-dot {{
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--green);
  box-shadow: 0 0 6px var(--green);
  animation: pulse 2s ease infinite;
}}
@keyframes pulse {{ 0%,100% {{ opacity:1 }} 50% {{ opacity:.4 }} }}
.logo-sub {{
  font-family: 'JetBrains Mono', monospace;
  font-size: .7rem;
  color: var(--muted);
  font-weight: 400;
}}
.header-right {{
  display: flex;
  align-items: center;
  gap: 1rem;
}}
.badge {{
  font-family: 'JetBrains Mono', monospace;
  font-size: .65rem;
  font-weight: 500;
  padding: .2rem .6rem;
  border-radius: 4px;
  background: var(--surface2);
  border: 1px solid var(--border);
  color: var(--muted);
  letter-spacing: .05em;
}}
.badge.live {{
  background: rgba(52,211,153,.1);
  border-color: rgba(52,211,153,.3);
  color: var(--green);
}}
.theme-btn {{
  width: 32px; height: 32px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--muted);
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px;
  transition: background .15s, color .15s;
}}
.theme-btn:hover {{ background: var(--surface2); color: var(--text); }}

/* ── Section label ── */
.section-label {{
  font-size: .7rem;
  font-weight: 600;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--muted);
  margin: 2rem 0 .875rem;
}}

/* ── Stat grid ── */
.stat-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(175px, 1fr));
  gap: .75rem;
}}

.stat {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1.25rem 1.25rem 1rem;
  animation: fadein .35s ease both;
  box-shadow: 0 1px 3px var(--shadow);
}}
@keyframes fadein {{ from {{ opacity:0; transform:translateY(8px) }} }}

.stat-val {{
  font-size: 2rem;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
  color: var(--text);
  line-height: 1;
  margin-bottom: .45rem;
  letter-spacing: -.02em;
}}
.stat-val.accent  {{ color: var(--accent2); }}
.stat-val.green   {{ color: var(--green); }}
.stat-val.blue    {{ color: var(--blue); }}

.stat-lbl {{
  font-size: .68rem;
  font-weight: 500;
  color: var(--muted);
  letter-spacing: .02em;
}}

/* ── Table ── */
.tbl-wrap {{
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  box-shadow: 0 1px 3px var(--shadow);
}}

table {{
  width: 100%;
  border-collapse: collapse;
  font-size: .8rem;
}}
thead tr {{
  border-bottom: 1px solid var(--border);
  background: var(--surface2);
}}
th {{
  padding: .65rem 1rem;
  text-align: left;
  font-size: .65rem;
  font-weight: 600;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--muted);
}}
td {{
  padding: .65rem 1rem;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
  color: var(--text);
}}
tbody tr:last-child td {{ border-bottom: none; }}
tbody tr:hover {{ background: var(--surface2); }}

td.dim    {{ color: var(--muted); font-family: 'JetBrains Mono', monospace; font-size: .75rem; }}
td.path   {{ color: var(--blue); font-family: 'JetBrains Mono', monospace; font-size: .75rem; }}
td.usdc   {{ color: var(--green); font-weight: 600; font-family: 'JetBrains Mono', monospace; }}
td.chain  {{ color: var(--accent2); font-family: 'JetBrains Mono', monospace; font-size: .7rem; }}
td.tx     {{ color: var(--subtle); font-family: 'JetBrains Mono', monospace; font-size: .7rem; }}
td.empty  {{ color: var(--muted); font-style: italic; padding: 2rem 1rem; text-align: center; }}

/* ── Bar chart ── */
.bars {{ display: flex; flex-direction: column; gap: .5rem; }}
.bar-row {{
  display: grid;
  grid-template-columns: 88px 1fr 48px;
  align-items: center;
  gap: .75rem;
}}
.bar-label {{ font-family: 'JetBrains Mono', monospace; font-size: .65rem; color: var(--muted); }}
.bar-track {{
  height: 6px;
  background: var(--surface2);
  border-radius: 99px;
  overflow: hidden;
}}
.bar-fill {{
  height: 100%;
  background: var(--accent);
  border-radius: 99px;
  transition: width .6s ease;
  min-width: 3px;
  opacity: .85;
}}
.bar-val {{ font-family: 'JetBrains Mono', monospace; font-size: .65rem; color: var(--muted); text-align: right; }}

/* ── Footer ── */
footer {{
  margin-top: 3rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
  font-family: 'JetBrains Mono', monospace;
  font-size: .65rem;
  color: var(--subtle);
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: .5rem;
}}
</style>
</head>
<body>
<div class="wrap">

<header>
  <div class="logo">
    <div class="logo-dot"></div>
    MAXIA Oracle
    <span class="logo-sub">/ admin</span>
  </div>
  <div class="header-right">
    <span class="badge live">PROD</span>
    <span class="badge">AUTO-REFRESH 30s</span>
    <button class="theme-btn" onclick="toggle()" title="Toggle theme">☀</button>
  </div>
</header>

<div class="section-label">Users &amp; Activity</div>
<div class="stat-grid">
  <div class="stat" style="animation-delay:.05s">
    <div class="stat-val">{k['total']}</div>
    <div class="stat-lbl">Total API Keys</div>
  </div>
  <div class="stat" style="animation-delay:.1s">
    <div class="stat-val blue">{k['today']}</div>
    <div class="stat-lbl">New Today</div>
  </div>
  <div class="stat" style="animation-delay:.15s">
    <div class="stat-val blue">{k['last_7d']}</div>
    <div class="stat-lbl">New Last 7d</div>
  </div>
  <div class="stat" style="animation-delay:.2s">
    <div class="stat-val accent">{s['alerts']}</div>
    <div class="stat-lbl">Active Alerts</div>
  </div>
  <div class="stat" style="animation-delay:.25s">
    <div class="stat-val">{s['snapshots']}</div>
    <div class="stat-lbl">Price Snapshots</div>
  </div>
</div>

<div class="section-label">x402 Revenue</div>
<div class="stat-grid">
  <div class="stat" style="animation-delay:.3s">
    <div class="stat-val green">${x['total_usdc']}</div>
    <div class="stat-lbl">Total USDC</div>
  </div>
  <div class="stat" style="animation-delay:.35s">
    <div class="stat-val">{x['total_calls']}</div>
    <div class="stat-lbl">Total Paid Calls</div>
  </div>
  <div class="stat" style="animation-delay:.4s">
    <div class="stat-val green">${x['today_usdc']}</div>
    <div class="stat-lbl">Today USDC</div>
  </div>
  <div class="stat" style="animation-delay:.45s">
    <div class="stat-val">{x['today_calls']}</div>
    <div class="stat-lbl">Today Calls</div>
  </div>
</div>

<div class="section-label">Daily x402 — Last 7 Days</div>
<div class="bars">
  {bars or '<div style="color:var(--muted);font-size:.75rem;padding:.5rem 0;font-family:JetBrains Mono,monospace">— no data —</div>'}
</div>

<div class="section-label">Recent Transactions</div>
<div class="tbl-wrap">
  <table>
    <thead><tr><th>Time UTC</th><th>Path</th><th>Amount</th><th>Chain</th><th>TX Hash</th></tr></thead>
    <tbody>
      {rows_recent or '<tr><td colspan="5" class="empty">No transactions yet</td></tr>'}
    </tbody>
  </table>
</div>

<footer>
  <span>Generated {s['generated_at']}</span>
  <span>oracle.maxiaworld.app · v0.1.9</span>
</footer>

</div>
<script>
  function toggle() {{
    const h = document.documentElement;
    const next = h.dataset.theme === 'dark' ? 'light' : 'dark';
    h.dataset.theme = next;
    document.querySelector('.theme-btn').textContent = next === 'dark' ? '☀' : '☾';
    localStorage.setItem('theme', next);
  }}
  (function() {{
    const saved = localStorage.getItem('theme') || (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
    document.documentElement.dataset.theme = saved;
    document.querySelector('.theme-btn').textContent = saved === 'dark' ? '☀' : '☾';
  }})();
</script>
</body>
</html>"""
    response = HTMLResponse(html)
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "script-src 'unsafe-inline'; "
        "frame-ancestors 'none'"
    )
    return response
