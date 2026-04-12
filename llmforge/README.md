# LLMForge

**LLM Router Multi-Provider** -- One endpoint, intelligent routing, automatic fallback. Like LiteLLM but with a dashboard.

Part of the [Forge Suite](https://maxialab.com) by MAXIA Lab.

## Features

- **6 LLM Tiers** -- Ollama, Cerebras, Gemini, Groq, Mistral, Claude with auto-fallback
- **Response Cache** -- Configurable TTL, avoid redundant API calls
- **Budget Caps** -- Global and per-key daily spending limits
- **P50/P95 Latency** -- Real-time latency percentiles per tier
- **OpenAI-Compatible** -- Drop-in replacement for any OpenAI SDK client
- **Auto-Classification** -- Routes prompts to the cheapest tier that can handle them

## Quick Start

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add your LLM API keys to .env
uvicorn main:app --port 8002 --reload
```

## Usage

```bash
# OpenAI-compatible chat
curl -X POST http://localhost:8002/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}]}'

# Specify a tier
curl -X POST http://localhost:8002/api/chat \
  -d '{"messages": [{"role": "user", "content": "Analyze this..."}], "model": "strategic"}'

# Check usage
curl http://localhost:8002/api/usage
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health + provider count |
| GET | `/api/models` | Available tiers with pricing |
| POST | `/api/chat` | OpenAI-compatible chat |
| POST | `/api/completions` | Text completion |
| GET | `/api/usage` | Today's stats (calls, cost, P50/P95) |
| GET | `/api/usage/tiers` | Per-tier breakdown |
| GET | `/api/cache/stats` | Cache hit rate |
| POST | `/api/cache/clear` | Clear cache |

## Pricing (Tiers)

| Tier | Provider | Cost/1K tokens | Speed |
|------|----------|---------------|-------|
| local | Ollama | Free | Local GPU |
| fast | Cerebras | Free | ~3000 tok/s |
| fast2 | Gemini | Free | Fast |
| fast3 | Groq | Free | Rate-limited |
| mid | Mistral | ~$0.0006 | Good |
| strategic | Claude | ~$0.015 | Best quality |

## Tech Stack

Python 3.12, FastAPI, Pydantic V2, httpx. 24 tests with pytest.

## License

Proprietary -- see [LICENSE](LICENSE). Self-hosted license at [maxialab.com](https://maxialab.com).
