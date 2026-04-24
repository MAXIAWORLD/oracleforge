"""TDD — Phase 4: Tests d'intégration — lifespan complet + HTTP end-to-end.

Ces tests lancent l'app FastAPI complète avec le lifespan (DB init, engine, etc.).
Ils utilisent TestClient (sync) qui démarre/arrête le lifespan proprement.
Ils sont ROUGES si le lifespan, les routes ou la persistance DB sont cassés.
"""

from __future__ import annotations

import os
import pytest
import yaml

os.environ.setdefault("SECRET_KEY", "test-secret-key-32-chars-ok!!")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("DEBUG", "true")

from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def client(tmp_path):
    """TestClient avec lifespan complet sur répertoire missions temporaire."""
    missions_dir = tmp_path / "missions"
    missions_dir.mkdir()

    mission_yaml = {
        "name": "integration-test",
        "description": "test mission",
        "steps": [{"action": "log", "text_template": "integration ok"}],
    }
    (missions_dir / "integration-test.yaml").write_text(
        yaml.dump(mission_yaml), encoding="utf-8"
    )

    os.environ["MISSIONS_DIR"] = str(missions_dir)
    os.environ["CHROMA_PERSIST_DIR"] = str(tmp_path / "chroma")
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

    from core.config import get_settings

    get_settings.cache_clear()

    from main import create_app

    _app = create_app()

    with TestClient(_app, headers={"X-API-Key": "test-secret-key-32-chars-ok!!"}) as c:
        yield c

    get_settings.cache_clear()


# ── Tests : health ────────────────────────────────────────────────


def test_health_returns_ok(client):
    """/health répond 200 avec status ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_includes_version(client):
    """/health expose la version de l'app."""
    resp = client.get("/health")
    assert "version" in resp.json()


# ── Tests : missions ──────────────────────────────────────────────


def test_list_missions_returns_loaded_yaml(client):
    """/api/missions retourne la mission chargée depuis le YAML."""
    resp = client.get("/api/missions")
    assert resp.status_code == 200
    names = [m["name"] for m in resp.json()["missions"]]
    assert "integration-test" in names


def test_get_mission_detail(client):
    """/api/missions/{name} retourne les détails de la mission."""
    resp = client.get("/api/missions/integration-test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "integration-test"
    assert len(data["steps"]) == 1


def test_get_unknown_mission_returns_404(client):
    """/api/missions/{name} → 404 si la mission n'existe pas."""
    resp = client.get("/api/missions/ghost-mission")
    assert resp.status_code == 404


# ── Tests : run + persistance ────────────────────────────────────


def test_run_mission_returns_success(client):
    """POST /api/missions/{name}/run → status success."""
    resp = client.post("/api/missions/integration-test/run")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["steps_completed"] == 1
    assert "run_id" in data


def test_run_history_persisted_in_db(client):
    """Après un run, /history retourne ce run (DB, pas mémoire)."""
    run_id = client.post("/api/missions/integration-test/run").json()["run_id"]

    resp = client.get("/api/missions/integration-test/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert run_id in [r["run_id"] for r in data["runs"]]


def test_run_history_supports_limit_param(client):
    """Le paramètre limit borne les résultats de /history."""
    for _ in range(4):
        client.post("/api/missions/integration-test/run")

    resp = client.get("/api/missions/integration-test/history?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()["runs"]) == 2


def test_global_history_endpoint(client):
    """GET /api/missions/history/all retourne tous les runs."""
    client.post("/api/missions/integration-test/run")
    resp = client.get("/api/missions/history/all")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


# ── Tests : observabilité ─────────────────────────────────────────


def test_observability_summary(client):
    """GET /api/observability/summary répond 200."""
    resp = client.get("/api/observability/summary")
    assert resp.status_code == 200


def test_rag_stats(client):
    """GET /api/rag/stats répond 200."""
    resp = client.get("/api/rag/stats")
    assert resp.status_code == 200


# ── Tests : sécurité ─────────────────────────────────────────────


def test_request_without_api_key_returns_401(tmp_path):
    """Toutes les routes requièrent X-API-Key."""
    missions_dir = tmp_path / "missions"
    missions_dir.mkdir()
    os.environ["MISSIONS_DIR"] = str(missions_dir)
    os.environ["CHROMA_PERSIST_DIR"] = str(tmp_path / "chroma")

    from core.config import get_settings

    get_settings.cache_clear()
    from main import create_app

    _app = create_app()

    with TestClient(_app, raise_server_exceptions=False) as anon:
        resp = anon.get("/api/missions")
        assert resp.status_code == 401

    get_settings.cache_clear()
