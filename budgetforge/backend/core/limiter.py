from slowapi import Limiter

from core.client_ip import get_real_client_ip


def _key_by_api_or_ip(request) -> str:
    """H4 — rate-limit par API key (Bearer bf-xxx) si présente, sinon par IP.
    Bloque le contournement par rotation d'IP pour une même clé volée.
    Pour les endpoints sans Authorization (signup, portal, admin via X-Admin-Key),
    le fallback IP assure que le comportement existant reste inchangé.

    B1.5 (audit H08): get_real_client_ip lit X-Forwarded-For si la requete
    vient d'un proxy de confiance (nginx sur loopback).
    """
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        key = auth.split(None, 1)[1].strip()
        if key.startswith("bf-"):
            return f"key:{key}"
    return f"ip:{get_real_client_ip(request)}"


# Rate limiting robuste pour production
limiter = Limiter(
    key_func=_key_by_api_or_ip,
    default_limits=["100/minute"],  # Limite par défaut plus généreuse
)
