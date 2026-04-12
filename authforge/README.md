# AuthForge

**Auth complete pour FastAPI** -- JWT, OAuth, RBAC, rate limiting. `pip install authforge` et 3 lignes de code.

Part of the [Forge Suite](https://maxialab.com) by MAXIA Lab.

## Features

- **JWT Tokens** -- Access + refresh tokens with configurable TTL
- **Password Hashing** -- PBKDF2-SHA256 with random salt (100K iterations)
- **RBAC** -- Role-based access control (user, admin, editor)
- **Rate Limiting** -- Sliding window per-key limiter
- **API Keys** -- Generate and validate API keys for programmatic access
- **OAuth Ready** -- Google OAuth integration (configurable)

## Quick Start

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --port 8005 --reload
```

## API

```bash
# Register
curl -X POST http://localhost:8005/api/auth/register \
  -d '{"email": "user@example.com", "password": "MyP@ssw0rd", "display_name": "John"}'

# Login
curl -X POST http://localhost:8005/api/auth/login \
  -d '{"email": "user@example.com", "password": "MyP@ssw0rd"}'
# Returns: {"access_token": "eyJ...", "refresh_token": "eyJ...", "expires_in": 1800}

# Get current user
curl http://localhost:8005/api/auth/me -H "Authorization: Bearer eyJ..."
```

## Tech Stack

Python 3.12, FastAPI, PyJWT, Pydantic V2. 13 tests. Proprietary license.
