"""B1.5 — Resolve real client IP behind nginx proxy (audit H08).

Pourquoi:
- nginx terminate TLS et forward vers uvicorn sur 127.0.0.1.
- Sans config, request.client.host = '127.0.0.1' pour toutes les
  requetes -> rate-limit IP bucket commun, signup IP rate-limit casse.

Fix:
- Si request.client.host est un proxy de confiance (loopback ou
  range fourni), lire X-Forwarded-For et prendre la premiere IP.
- Sinon, garder request.client.host (anti-spoofing: un client direct
  ne peut pas faire confiance a son propre X-Forwarded-For).
"""

# Proxies de confiance par defaut: nginx tourne sur loopback.
_DEFAULT_TRUSTED_PROXIES = frozenset({"127.0.0.1", "::1"})


def get_real_client_ip(request, trusted_proxies=_DEFAULT_TRUSTED_PROXIES) -> str:
    """Retourne l'IP reelle du client.

    Args:
        request: Starlette/FastAPI Request (utilise .client et .headers).
        trusted_proxies: ensemble d'IPs de proxies de confiance dont
            l'X-Forwarded-For est lu.

    Returns:
        IP reelle ou 'unknown' si introuvable.
    """
    client_host = request.client.host if request.client else None

    if client_host and client_host in trusted_proxies:
        # Headers Starlette: case-insensitive selon HTTP, mais l'objet
        # Starlette Headers normalise. Pour un dict simple (tests),
        # on tente les deux formes.
        xff = None
        if hasattr(request.headers, "get"):
            xff = request.headers.get("x-forwarded-for") or request.headers.get(
                "X-Forwarded-For"
            )
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first

    return client_host or "unknown"
