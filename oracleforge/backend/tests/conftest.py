"""Pytest fixtures for the MAXIA Oracle backend tests.

Sets required environment variables BEFORE any project module is imported,
so `core.config`'s strict startup validation succeeds in-process.

The `session_app`, `client` and `api_key` fixtures are exposed at
package scope so every test module (Phase 3, Phase 4, Phase 5, V1.1, …)
can request them without re-declaring the boilerplate.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

# Env vars MUST be set before `core.config` is imported.
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("API_KEY_PEPPER", "test-pepper-that-is-more-than-32-chars-long")
os.environ.setdefault("LOG_LEVEL", "WARNING")
# Phase 4: treasury address is set at session scope so the x402 middleware
# populates the 402 `accepts` list in both Phase 3 and Phase 4 test modules.
# In dev mode this var is optional; tests set it so the behavior is
# deterministic across runs.
os.environ.setdefault(
    "X402_TREASURY_ADDRESS_BASE",
    "0xb3C5AF291eeA9D11DE7178B28eaF443359900f41",
)

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def session_app(tmp_path_factory: pytest.TempPathFactory):
    """Session-scoped: import main.py exactly once with a fresh DB path."""
    db_dir: Path = tmp_path_factory.mktemp("maxia_oracle_db")
    os.environ["DB_PATH"] = str(db_dir / "test.sqlite")
    import main  # noqa: PLC0415 — intentional late import after env setup
    from core.db import init_db  # noqa: PLC0415

    init_db()
    return main.app


@pytest.fixture
def client(session_app) -> Iterator[TestClient]:
    """Function-scoped: truncate mutable tables, then hand a TestClient over."""
    from core.db import get_db  # noqa: PLC0415

    db = get_db()
    db.execute("DELETE FROM api_keys")
    db.execute("DELETE FROM rate_limit")
    db.execute("DELETE FROM register_limit")
    db.execute("DELETE FROM price_snapshots")
    db.execute("DELETE FROM price_alerts")

    with TestClient(session_app) as c:
        yield c


@pytest.fixture
def api_key(client: TestClient) -> str:
    """Register a fresh API key and return the raw value."""
    response = client.post("/api/register")
    assert response.status_code == 201, response.text
    return response.json()["data"]["api_key"]
