"""TDD B1.4 — CORS allow_origins conditionne sur app_env (audit H13).

Bug audit: main.py:118-133 a une liste statique incluant localhost en
production:
    allow_origins=[
        'http://localhost:3000',
        'http://localhost:3001',
        'http://127.0.0.1:3000',
        'https://llmbudget.maxiaworld.app',
    ]

Combine avec allow_credentials=True, une page locale (qui peut etre
exploitee par un dev sans le savoir) peut faire des requetes
cross-origin avec cookies vers la prod.

Fix: une fonction get_cors_origins(app_env) qui retourne uniquement
l'origin prod en production, et autorise localhost en dev.
"""



def test_get_cors_origins_in_production_excludes_localhost():
    """En production, allow_origins ne doit contenir QUE l'origin prod."""
    from main import get_cors_origins

    origins = get_cors_origins("production")
    assert origins == ["https://llmbudget.maxiaworld.app"], (
        f"En production, allow_origins doit etre uniquement l'origin prod. "
        f"Got: {origins}"
    )


def test_get_cors_origins_in_development_includes_localhost():
    """En dev, allow_origins doit inclure localhost pour faciliter le dev."""
    from main import get_cors_origins

    origins = get_cors_origins("development")
    assert "http://localhost:3000" in origins, (
        f"En dev, localhost:3000 doit etre dans allow_origins. Got: {origins}"
    )
    assert "http://localhost:3001" in origins, (
        f"En dev, localhost:3001 doit etre dans allow_origins. Got: {origins}"
    )
    assert "https://llmbudget.maxiaworld.app" in origins, (
        f"L'origin prod doit toujours etre dans allow_origins (dev). Got: {origins}"
    )


def test_get_cors_origins_unknown_env_defaults_to_safe():
    """Une valeur inconnue doit defaulter sur la liste prod (fail-safe)."""
    from main import get_cors_origins

    origins = get_cors_origins("staging")
    # Politique safe: tout ce qui n'est pas explicitement 'development' /
    # 'test' renvoie la config production (origin unique).
    assert "http://localhost:3000" not in origins, (
        f"Pour env inconnu, fail-safe = pas de localhost. Got: {origins}"
    )
