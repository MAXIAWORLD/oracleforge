"""TDD — Phase 3: Alembic migrations.

Ces tests vérifient que le schéma DB est géré par Alembic (pas seulement create_all).
Ils sont ROUGES jusqu'à ce qu'alembic soit configuré et la première migration créée.

Stratégie : fichier SQLite temporaire (pas in-memory, Alembic a besoin d'une vraie URL).
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

# Répertoire racine du backend
BACKEND_DIR = Path(__file__).parent.parent
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"


# ── Helpers ───────────────────────────────────────────────────────


def _run_alembic(cmd: str, db_url: str, *extra_args) -> None:
    """Lance une commande Alembic via l'API Python (pas subprocess)."""
    from alembic.config import Config
    from alembic import command as alembic_command

    old_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    os.environ.setdefault("SECRET_KEY", "test-secret-key-32-chars-ok!!")
    try:
        cfg = Config(str(ALEMBIC_INI))
        cfg.set_main_option("sqlalchemy.url", db_url)
        getattr(alembic_command, cmd)(cfg, *extra_args)
    finally:
        if old_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old_url


def _get_tables(db_url: str) -> set[str]:
    """Retourne les noms de tables présentes dans la DB SQLite."""
    sync_url = db_url.replace("sqlite+aiosqlite://", "sqlite://")
    engine = create_engine(sync_url)
    with engine.connect():
        return set(inspect(engine).get_table_names())


# ── Tests : alembic.ini présent ───────────────────────────────────


def test_alembic_ini_exists():
    """alembic.ini doit être présent à la racine du backend."""
    assert ALEMBIC_INI.exists(), (
        f"alembic.ini non trouvé dans {BACKEND_DIR}. "
        "Lance: cd backend && alembic init alembic"
    )


def test_alembic_versions_dir_exists():
    """Le répertoire alembic/versions/ doit exister."""
    versions_dir = BACKEND_DIR / "alembic" / "versions"
    assert versions_dir.is_dir(), "alembic/versions/ introuvable — lancer alembic init"


def test_at_least_one_migration_file_exists():
    """Au moins une migration doit être présente dans alembic/versions/."""
    versions_dir = BACKEND_DIR / "alembic" / "versions"
    migrations = list(versions_dir.glob("*.py"))
    assert len(migrations) >= 1, (
        "Aucune migration trouvée. "
        "Lance: alembic revision --autogenerate -m 'initial schema'"
    )


# ── Tests : upgrade head ──────────────────────────────────────────


def test_upgrade_head_exits_zero(tmp_path):
    """alembic upgrade head doit se terminer sans exception."""
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    _run_alembic("upgrade", db_url, "head")  # lève si erreur


def test_upgrade_head_creates_missions_table(tmp_path):
    """upgrade head crée la table 'missions'."""
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    _run_alembic("upgrade", db_url, "head")
    assert "missions" in _get_tables(db_url)


def test_upgrade_head_creates_execution_logs_table(tmp_path):
    """upgrade head crée la table 'execution_logs'."""
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    _run_alembic("upgrade", db_url, "head")
    assert "execution_logs" in _get_tables(db_url)


def test_upgrade_head_creates_llm_call_records_table(tmp_path):
    """upgrade head crée la table 'llm_call_records'."""
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    _run_alembic("upgrade", db_url, "head")
    assert "llm_call_records" in _get_tables(db_url)


def test_upgrade_head_idempotent(tmp_path):
    """Lancer upgrade head deux fois de suite ne produit pas d'erreur."""
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    _run_alembic("upgrade", db_url, "head")
    _run_alembic("upgrade", db_url, "head")  # no-op, ne lève pas


# ── Tests : schéma execution_logs ────────────────────────────────


def test_execution_logs_has_run_id_column(tmp_path):
    """La table execution_logs doit avoir une colonne run_id (ajoutée Phase 1)."""
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    _run_alembic("upgrade", db_url, "head")

    sync_url = db_url.replace("sqlite+aiosqlite://", "sqlite://")
    engine = create_engine(sync_url)
    cols = {c["name"] for c in inspect(engine).get_columns("execution_logs")}
    assert "run_id" in cols, "Colonne run_id absente de execution_logs"


def test_execution_logs_mission_id_is_nullable(tmp_path):
    """mission_id dans execution_logs doit être nullable (pas de FK obligatoire)."""
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    _run_alembic("upgrade", db_url, "head")

    sync_url = db_url.replace("sqlite+aiosqlite://", "sqlite://")
    engine = create_engine(sync_url)
    cols = {c["name"]: c for c in inspect(engine).get_columns("execution_logs")}
    assert cols["mission_id"]["nullable"] is True


# ── Tests : downgrade ─────────────────────────────────────────────


def test_downgrade_base_exits_zero(tmp_path):
    """alembic downgrade base doit se terminer sans exception."""
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    _run_alembic("upgrade", db_url, "head")
    _run_alembic("downgrade", db_url, "base")  # lève si erreur


def test_downgrade_base_removes_tables(tmp_path):
    """Après downgrade base, les tables métier sont supprimées."""
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    _run_alembic("upgrade", db_url, "head")
    _run_alembic("downgrade", db_url, "base")
    tables = _get_tables(db_url)
    assert "missions" not in tables
    assert "execution_logs" not in tables
    assert "llm_call_records" not in tables


# ── Tests : données survivent à une migration future ─────────────


def test_existing_data_survives_upgrade(tmp_path):
    """Les données insérées avant upgrade head persistent après (idempotence)."""
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    _run_alembic("upgrade", db_url, "head")

    sync_url = db_url.replace("sqlite+aiosqlite://", "sqlite://")
    engine = create_engine(sync_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO execution_logs "
                "(mission_name, status, steps_completed, total_steps, tokens_used, cost_usd) "
                "VALUES ('test-mission', 'success', 1, 1, 100, 0.001)"
            )
        )

    # Rejouer upgrade head (no-op) — les données doivent survivre
    _run_alembic("upgrade", db_url, "head")

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT mission_name FROM execution_logs")).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "test-mission"
