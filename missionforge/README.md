# MissionForge

**AI Agent Framework** -- Define autonomous missions in YAML, execute them with multi-provider LLM routing and RAG-grounded intelligence.

Part of the [Forge Suite](https://maxialab.com) by MAXIA Lab.

## Features

- **YAML Missions** -- Define agent missions declaratively. No code needed.
- **Multi-LLM Router** -- 6 tiers (Ollama, Cerebras, Gemini, Groq, Mistral, Claude) with automatic fallback
- **Hybrid RAG** -- ChromaDB vector search + keyword overlay for knowledge-grounded responses
- **Pipeline Executor** -- Chain steps: `rag_retrieve` > `llm_call` > `webhook` > `memory_store` > `log`
- **Cron Scheduling** -- Schedule missions with standard cron expressions
- **Dashboard** -- Next.js + shadcn/ui with real-time observability
- **Observability** -- Token usage, cost tracking, P50/P95 latency per tier

## Quick Start (60 seconds)

### Option 1: Docker (recommended)

```bash
git clone https://github.com/maxialab/missionforge.git
cd missionforge
cp backend/.env.example backend/.env
# Edit backend/.env with your LLM API keys
docker-compose up
```

Open http://localhost:3000 for the dashboard, http://localhost:8001/docs for the API.

### Option 2: Local dev

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys
MISSIONS_DIR="../examples/missions" uvicorn main:app --port 8001 --reload

# Dashboard (new terminal)
cd dashboard
npm install && npm run dev
```

## Define a Mission

Create a YAML file in your missions directory:

```yaml
name: daily-summary
description: "Generate a daily briefing from your knowledge base"
schedule: "0 9 * * *"
agent:
  system_prompt: "You are a precise daily briefing assistant."
  llm_tier: fast
steps:
  - action: rag_retrieve
    query: "latest updates and announcements"
    output_var: context
  - action: llm_call
    prompt: "Write a concise daily summary:\n\n{context}"
    max_tokens: 600
    output_var: summary
  - action: webhook
    url: "{env.SLACK_WEBHOOK}"
    method: POST
    payload_template: '{"text": "{summary}"}'
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/missions` | List all missions |
| POST | `/api/missions/{name}/run` | Run a mission |
| POST | `/api/chat` | Chat with agent (RAG-grounded) |
| POST | `/api/llm/chat` | OpenAI-compatible LLM proxy |
| GET | `/api/llm/models` | Available LLM tiers |
| GET | `/api/observability/summary` | Usage metrics |
| POST | `/api/rag/ingest` | Ingest documents |

## LLM Tiers

| Tier | Provider | Cost | Use case |
|------|----------|------|----------|
| local | Ollama | Free | Classification, parsing, formatting |
| fast | Cerebras | Free | Writing, drafting, analysis |
| fast2 | Gemini | Free | Fallback, general tasks |
| fast3 | Groq | Free | Rate-limited backup |
| mid | Mistral | ~$0.0006/1K | Multi-step reasoning, reports |
| strategic | Claude | ~$0.015/1K | Critical decisions, complex reasoning |

## Mission Step Actions

| Action | Description |
|--------|-------------|
| `rag_retrieve` | Query knowledge base, store result in variable |
| `llm_call` | Call LLM with prompt interpolation |
| `webhook` | HTTP request to external URL |
| `memory_store` | Save data to vector memory |
| `log` | Record message in execution log |

## Configuration

All configuration via environment variables. See `.env.example` for the full list.

Key variables:
- `SECRET_KEY` -- Application secret (required)
- `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, etc. -- LLM provider keys
- `MISSIONS_DIR` -- Path to YAML mission files
- `ALLOWED_ENV_VARS` -- Whitelist for `{env.VAR}` interpolation in missions

## Tech Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic V2, ChromaDB
- **Dashboard**: Next.js, Tailwind CSS, shadcn/ui, Recharts
- **Tests**: 91 tests with pytest (TDD)

## License

Proprietary -- see [LICENSE](LICENSE).

Self-hosted license available at [maxialab.com](https://maxialab.com).
