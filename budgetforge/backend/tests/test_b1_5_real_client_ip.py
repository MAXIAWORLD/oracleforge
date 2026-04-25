"""TDD B1.5 — get_real_client_ip derriere proxy nginx (audit H08).

Bug audit: derriere nginx, request.client.host = '127.0.0.1' (IP du
proxy local). Rate-limit IP bucket toutes les requetes ensemble,
SignupAttempt.ip enregistre 127.0.0.1 pour tous les signups.

Fix: lire X-Forwarded-For si la requete vient d'un proxy de confiance
(127.0.0.1 et autres). Sinon fallback sur request.client.host.

Cette fonction doit etre utilisee par limiter.py et signup.py.
"""

from unittest.mock import MagicMock


def make_request(client_host: str | None, headers: dict | None = None):
    """Build a fake Starlette Request-like object."""
    req = MagicMock()
    req.client = MagicMock(host=client_host) if client_host else None
    req.headers = headers or {}
    return req


def test_returns_xff_first_ip_if_client_is_trusted_proxy():
    """Behind nginx (127.0.0.1), X-Forwarded-For is trusted."""
    from core.client_ip import get_real_client_ip

    req = make_request("127.0.0.1", {"x-forwarded-for": "8.8.8.8"})
    assert get_real_client_ip(req) == "8.8.8.8"


def test_returns_first_ip_from_xff_chain_if_trusted():
    """X-Forwarded-For: client, proxy1, proxy2 -> client."""
    from core.client_ip import get_real_client_ip

    req = make_request("127.0.0.1", {"x-forwarded-for": "1.2.3.4, 10.0.0.1, 10.0.0.2"})
    assert get_real_client_ip(req) == "1.2.3.4"


def test_returns_client_host_if_no_xff_header():
    """Pas de X-Forwarded-For -> fallback request.client.host."""
    from core.client_ip import get_real_client_ip

    req = make_request("127.0.0.1", {})
    assert get_real_client_ip(req) == "127.0.0.1"


def test_ignores_xff_if_client_is_not_trusted_proxy():
    """Si request.client.host n'est PAS un proxy de confiance, ignorer X-Forwarded-For
    (anti-spoofing: client direct ne peut pas mentir sur son IP)."""
    from core.client_ip import get_real_client_ip

    req = make_request("203.0.113.5", {"x-forwarded-for": "8.8.8.8"})
    assert get_real_client_ip(req) == "203.0.113.5"


def test_returns_unknown_if_no_client_and_no_xff():
    """Pas de client, pas de header -> 'unknown' (signup.py defaults)."""
    from core.client_ip import get_real_client_ip

    req = make_request(None, {})
    assert get_real_client_ip(req) == "unknown"


def test_strips_whitespace_in_xff():
    from core.client_ip import get_real_client_ip

    req = make_request("127.0.0.1", {"x-forwarded-for": "  8.8.8.8  ,  10.0.0.1"})
    assert get_real_client_ip(req) == "8.8.8.8"


def test_handles_uppercase_xff_header():
    """HTTP headers are case-insensitive — Starlette normalises to lowercase, mais
    on doit etre robuste."""
    from core.client_ip import get_real_client_ip

    req = make_request("127.0.0.1", {"X-Forwarded-For": "8.8.8.8"})
    assert get_real_client_ip(req) == "8.8.8.8"
