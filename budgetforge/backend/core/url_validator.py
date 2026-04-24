import ipaddress
import socket
from urllib.parse import urlparse, urlunparse

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),  # loopback
    ipaddress.ip_network("10.0.0.0/8"),  # RFC 1918
    ipaddress.ip_network("172.16.0.0/12"),  # RFC 1918
    ipaddress.ip_network("192.168.0.0/16"),  # RFC 1918
    ipaddress.ip_network("169.254.0.0/16"),  # link-local (AWS metadata etc.)
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 ULA
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
]

_BLOCKED_HOSTNAMES = {"localhost", "metadata.google.internal"}


def resolve_safe_host(url: str) -> tuple[str, str]:
    """Résout le DNS une seule fois, valide chaque IP, retourne (url_pincée, hostname).

    Utilisé pour pinner l'IP au moment de l'envoi et éviter le DNS rebinding TOCTOU.
    Lève ValueError si l'URL est invalide ou l'IP dans une plage bloquée.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Scheme non autorisé: {parsed.scheme!r}")
        hostname = parsed.hostname
        if not hostname:
            raise ValueError("Hostname manquant")
        if hostname.lower() in _BLOCKED_HOSTNAMES:
            raise ValueError(f"Hostname bloqué: {hostname!r}")

        # Si c'est déjà une IP : valider directement
        try:
            addr = ipaddress.ip_address(hostname)
            for net in _BLOCKED_NETWORKS:
                if addr in net:
                    raise ValueError(f"IP {hostname} dans plage bloquée {net}")
            return url, hostname
        except ValueError as exc:
            if "bloquée" in str(exc) or "bloqué" in str(exc):
                raise

        # Résolution DNS unique
        try:
            infos = socket.getaddrinfo(hostname, None)
        except OSError:
            raise ValueError(f"Impossible de résoudre: {hostname!r}")

        chosen_ip: str | None = None
        for info in infos:
            ip_str = info[4][0]
            try:
                addr = ipaddress.ip_address(ip_str)
            except ValueError:
                continue
            for net in _BLOCKED_NETWORKS:
                if addr in net:
                    raise ValueError(f"IP résolue {ip_str} dans plage bloquée {net}")
            if chosen_ip is None:
                chosen_ip = ip_str

        if chosen_ip is None:
            raise ValueError("Aucune IP valide résolue")

        port = parsed.port
        if ":" in chosen_ip:  # IPv6
            netloc = f"[{chosen_ip}]" + (f":{port}" if port else "")
        else:
            netloc = chosen_ip + (f":{port}" if port else "")

        return urlunparse(parsed._replace(netloc=netloc)), hostname

    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Erreur validation URL: {exc}") from exc


def is_safe_webhook_url(url: str) -> bool:
    """Vérifie qu'une URL de webhook n'est pas une cible SSRF.

    Autorise uniquement http/https vers des hôtes publics.
    Bloque: loopback, RFC 1918, link-local, métadonnées cloud, schémas non-HTTP.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        if hostname.lower() in _BLOCKED_HOSTNAMES:
            return False
        try:
            addr = ipaddress.ip_address(hostname)
            for network in _BLOCKED_NETWORKS:
                if addr in network:
                    return False
        except ValueError:
            # domain name — résoudre DNS et vérifier chaque IP résolue
            try:
                resolved = socket.getaddrinfo(hostname, None)
            except OSError:
                return False  # non résolvable → refus fail-safe
            for item in resolved:
                ip_str = item[4][0]
                try:
                    addr = ipaddress.ip_address(ip_str)
                    for network in _BLOCKED_NETWORKS:
                        if addr in network:
                            return False
                except ValueError:
                    pass
        return True
    except Exception:
        return False
