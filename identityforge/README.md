# IdentityForge

**DID + Reputation API** — W3C DID with ed25519 keys, reputation scoring, universal agent identity (ElizaOS, AutoGen, CrewAI, LangChain).

Part of the [Forge Suite](https://maxiaworld.app) by MAXIA Lab.

## Status

🚧 **In development** — extracted from MAXIA V12

## Source modules (MAXIA V12)

- `backend/agents/cross_chain_identity.py`
- `backend/agents/agent_reputation.py`
- `backend/features/reputation_oracle.py`
- `backend/infra/reputation_staking.py`
- `llama-index-maxia/src/llama_index_maxia/identity.py`

## Planned features

- `POST /identity/create` — generate DID + ed25519 keypair
- `GET /identity/resolve/{did}` — resolve DID document
- `POST /identity/sign` — sign payload with DID key
- `POST /identity/verify` — verify signature
- `GET /identity/{did}/reputation` — get reputation score
- `POST /identity/{did}/reputation/update` — update score

## Stack

- Backend: Python 3.12 + FastAPI, port 8008
- Domain: identity.maxiaworld.app
