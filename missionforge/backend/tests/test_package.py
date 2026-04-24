"""TDD — Phase 6: Package distribution.

Vérifie:
- missionforge package importable (version, metadata)
- Classes clés exportées : MissionEngine, LLMRouter
- pyproject.toml cohérent avec __version__
- CLI entry-point 'missionforge' déclaré
"""

from __future__ import annotations

import sys
import os

# Ensure backend root is on path
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


# ── Version & metadata ──────────────────────────────────────────────


def test_version_string_exists():
    """Le module backend expose __version__."""
    import importlib.metadata as meta

    # On accepte soit importlib.metadata, soit un __version__ hardcodé
    try:
        version = meta.version("missionforge")
    except meta.PackageNotFoundError:
        # Pas encore installé via pip — on lit la config
        from core.config import get_settings

        version = get_settings().version
    assert version, "Version vide"
    parts = version.split(".")
    assert len(parts) >= 2, f"Version malformée : {version}"


def test_version_is_semver():
    """La version respecte X.Y.Z."""
    from core.config import get_settings

    version = get_settings().version
    parts = version.split(".")
    assert len(parts) == 3, f"Doit être X.Y.Z, got: {version}"
    for p in parts:
        assert p.isdigit(), f"Partie non numérique : {p}"


def test_version_matches_pyproject():
    """__version__ dans config == version dans pyproject.toml."""
    import tomllib
    import pathlib

    pyproject = pathlib.Path(_BACKEND) / "pyproject.toml"
    assert pyproject.exists(), "pyproject.toml absent"
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    pyproject_version = data["project"]["version"]
    from core.config import get_settings

    assert get_settings().version == pyproject_version


# ── Core imports ─────────────────────────────────────────────────────


def test_mission_engine_importable():
    """MissionEngine peut être importé depuis services."""
    from services.mission_engine import MissionEngine

    assert MissionEngine is not None


def test_llm_router_importable():
    """LLMRouter peut être importé depuis services."""
    from services.llm_router import LLMRouter

    assert LLMRouter is not None


def test_rag_service_importable():
    """RagService peut être importé depuis services."""
    from services.rag_service import RagService

    assert RagService is not None


def test_config_importable():
    """get_settings peut être importé depuis core.config."""
    from core.config import get_settings

    settings = get_settings()
    assert settings.app_name


# ── pyproject.toml structure ─────────────────────────────────────────


def test_pyproject_has_project_section():
    """pyproject.toml contient [project]."""
    import tomllib
    import pathlib

    pyproject = pathlib.Path(_BACKEND) / "pyproject.toml"
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    assert "project" in data


def test_pyproject_name_is_missionforge():
    """pyproject.toml name == 'missionforge'."""
    import tomllib
    import pathlib

    pyproject = pathlib.Path(_BACKEND) / "pyproject.toml"
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    assert data["project"]["name"] == "missionforge"


def test_pyproject_python_requires():
    """pyproject.toml exige Python >= 3.12."""
    import tomllib
    import pathlib

    pyproject = pathlib.Path(_BACKEND) / "pyproject.toml"
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    requires = data["project"].get("requires-python", "")
    assert "3.12" in requires, f"requires-python absent ou trop bas: {requires}"


def test_pyproject_has_dependencies():
    """pyproject.toml déclare les dépendances."""
    import tomllib
    import pathlib

    pyproject = pathlib.Path(_BACKEND) / "pyproject.toml"
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    deps = data["project"].get("dependencies", [])
    assert len(deps) >= 5, f"Trop peu de dépendances : {deps}"


def test_pyproject_has_scripts():
    """pyproject.toml déclare le script CLI missionforge."""
    import tomllib
    import pathlib

    pyproject = pathlib.Path(_BACKEND) / "pyproject.toml"
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    scripts = data["project"].get("scripts", {})
    assert "missionforge" in scripts, f"Script CLI absent. Scripts: {scripts}"


def test_pyproject_has_build_system():
    """pyproject.toml contient [build-system]."""
    import tomllib
    import pathlib

    pyproject = pathlib.Path(_BACKEND) / "pyproject.toml"
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    assert "build-system" in data


# ── CLI entry-point ───────────────────────────────────────────────────


def test_cli_module_importable():
    """Le module CLI (main:app ou cli.py) est importable."""
    # On vérifie que create_app() fonctionne — le vrai entry-point
    import os

    os.environ.setdefault("SECRET_KEY", "test-secret-key-32-chars-ok!!")
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    from main import create_app

    app = create_app()
    assert app is not None
