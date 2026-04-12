# OutreachForge

**Email Outreach Automation** -- AI lead scoring, LLM personalisation, multi-language templates, ramp-up progressif.

Part of the [Forge Suite](https://maxialab.com) by MAXIA Lab.

## Features

- **AI Lead Scoring** -- Score prospects by email domain, title, company, profile completeness
- **Template Personalisation** -- `{first_name}`, `{company}`, `{title}` interpolation
- **Batch Scoring** -- Score up to 500 prospects in one request, sorted by priority
- **Tier Classification** -- cold / warm / hot based on score thresholds
- **Multi-Language** -- Templates in 13+ languages (planned)

## Quick Start

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --port 8006 --reload
```

## API

```bash
# Score a prospect
curl -X POST http://localhost:8006/api/score \
  -d '{"email": "cto@techcorp.com", "name": "Jane Smith", "company": "TechCorp", "title": "CTO"}'
# Returns: {"score": 0.75, "tier": "hot", "factors": {"business_email": 0.2, ...}}

# Batch scoring
curl -X POST http://localhost:8006/api/score/batch \
  -d '[{"email": "a@corp.com", "name": "A"}, {"email": "b@gmail.com"}]'

# Personalise template
curl -X POST http://localhost:8006/api/personalize \
  -d '{"template": "Hi {first_name}, I noticed {company} is growing.", "prospect": {"name": "Jane Doe", "company": "Acme"}}'
```

## Tech Stack

Python 3.12, FastAPI, Pydantic V2. 8 tests. Proprietary license.
