# MemoryForge

**Persistent AI Memory API** — ChromaDB + hybrid vector/keyword search. Store and retrieve memory chunks across any AI agent or LLM session.

Part of the [Forge Suite](https://maxiaworld.app) by MAXIA Lab.

## Status

🚧 **In development** — extracted from MAXIA V12

## Source modules (MAXIA V12)

- `backend/features/memory_service.py`
- `local_ceo/rag_knowledge.py`
- `local_ceo/vector_memory_local.py`
- `local_ceo/memory_prod/store.py`

## Planned features

- `POST /memory/store` — store chunk with metadata
- `GET /memory/retrieve?q=` — hybrid vector + keyword search
- `DELETE /memory/{id}` — remove chunk
- `GET /memory/stats` — count, size, top namespaces
- Namespaces per agent/session
- TTL support (auto-expiry)
- ChromaDB backend (swappable)

## Stack

- Backend: Python 3.12 + FastAPI, port 8007
- DB: ChromaDB (local) / managed (prod)
- Domain: memory.maxiaworld.app
