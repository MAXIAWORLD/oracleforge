import asyncio
import secrets
import sys
from collections import OrderedDict
import redis.asyncio as redis
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
import logging

if sys.platform != "win32":
    import fcntl as _fcntl

logger = logging.getLogger(__name__)

# Configuration Redis par défaut
REDIS_CONFIG = {"host": "localhost", "port": 6379, "db": 0, "decode_responses": False}

# Singleton Redis connection pool
_redis_pool: Optional[redis.Redis] = None


async def get_redis_client() -> Optional[redis.Redis]:
    """Obtient ou crée le client Redis. Retourne None si Redis n'est pas disponible."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.Redis(**REDIS_CONFIG)
        # Test de connexion
        try:
            await _redis_pool.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis not available, using fallback: {e}")
            _redis_pool = None
            return None
    return _redis_pool


def set_redis_config(host: str = "localhost", port: int = 6379, db: int = 0):
    """Configure Redis pour les tests ou environnement spécifique."""
    global REDIS_CONFIG
    REDIS_CONFIG = {"host": host, "port": port, "db": db, "decode_responses": False}


async def close_redis_connection():
    """Ferme la connexion Redis."""
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None


@asynccontextmanager
async def distributed_budget_lock(
    project_id: int, timeout: float = 30.0
) -> AsyncIterator[None]:
    """Verrou distribué Redis pour sérialiser l'accès au budget.

    Args:
        project_id: ID du projet
        timeout: Timeout en secondes pour acquérir le lock

    Raises:
        TimeoutError: Si le lock ne peut être acquis dans le timeout
    """
    redis_client = await get_redis_client()

    # Si Redis n'est pas disponible, lever une exception pour déclencher le fallback
    if redis_client is None:
        raise ConnectionError("Redis not available")

    lock_key = f"budget_lock:{project_id}"

    # TTL du lock (en secondes) - assez long pour couvrir la phase critique
    lock_ttl = 60

    # B4.2 (C08): token unique pour delete-if-owner (Lua atomique)
    token = secrets.token_urlsafe(16).encode()

    # Essayer d'acquérir le lock avec SET NX EX (atomic)
    acquired = await redis_client.set(lock_key, token, nx=True, ex=lock_ttl)

    if not acquired:
        # Le lock est déjà pris, attendre avec timeout
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            acquired = await redis_client.set(lock_key, token, nx=True, ex=lock_ttl)
            if acquired:
                break
            await asyncio.sleep(0.1)  # Polling toutes les 100ms
        else:
            raise TimeoutError(
                f"Could not acquire lock for project {project_id} within {timeout}s"
            )

    # Script Lua : delete-if-token-matches (atomic, évite de supprimer le lock d'un autre worker)
    _LUA_RELEASE = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

    try:
        yield
    finally:
        try:
            await redis_client.eval(_LUA_RELEASE, 1, lock_key, token)
        except Exception as e:
            logger.warning(f"Failed to release lock for project {project_id}: {e}")


# Fallback: implémentation mémoire pour compatibilité
_MEMORY_LOCKS_MAX_SIZE = 1024
_memory_locks: OrderedDict[int, asyncio.Lock] = OrderedDict()
_memory_registry_lock = asyncio.Lock()


async def _get_memory_lock(project_id: int) -> asyncio.Lock:
    """Fallback mémoire pour quand Redis n'est pas disponible.
    Borné à _MEMORY_LOCKS_MAX_SIZE pour éviter la fuite mémoire."""
    async with _memory_registry_lock:
        if project_id in _memory_locks:
            # LRU: déplacer en fin de file
            _memory_locks.move_to_end(project_id)
            return _memory_locks[project_id]
        lock = asyncio.Lock()
        _memory_locks[project_id] = lock
        if len(_memory_locks) > _MEMORY_LOCKS_MAX_SIZE:
            # Éviction FIFO: supprimer le plus ancien (premier inséré)
            _memory_locks.popitem(last=False)
        return lock


def _acquire_file_lock(path: str) -> object:
    # B4.3 (H02): O_NOFOLLOW empêche l'attaque symlink par un utilisateur local
    import os

    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    fh = os.fdopen(fd, "r+")
    _fcntl.flock(fh, _fcntl.LOCK_EX)
    return fh


def _release_file_lock(fh) -> None:
    try:
        _fcntl.flock(fh, _fcntl.LOCK_UN)
    finally:
        fh.close()


@asynccontextmanager
async def fallback_budget_lock(project_id: int) -> AsyncIterator[None]:
    """Fallback cross-process via fcntl.flock sur Linux, asyncio.Lock sur Windows."""
    if sys.platform == "win32":
        lock = await _get_memory_lock(project_id)
        async with lock:
            yield
        return

    lock_path = f"/tmp/bf_budget_{project_id}.lock"
    fh = await asyncio.to_thread(_acquire_file_lock, lock_path)
    try:
        yield
    finally:
        await asyncio.to_thread(_release_file_lock, fh)


# Export principal: utilise Redis si disponible, sinon fallback mémoire
@asynccontextmanager
async def budget_lock(project_id: int, timeout: float = 30.0) -> AsyncIterator[None]:
    """Verrou distribué avec fallback mémoire.

    Tente d'utiliser Redis d'abord, sinon utilise le verrou mémoire.
    C1: lock_acquired distingue "échec acquisition" de "exception dans le body"
    — seul l'échec d'acquisition déclenche le fallback, pas les exceptions du body.
    """
    lock_acquired = False
    try:
        async with distributed_budget_lock(project_id, timeout):
            lock_acquired = True
            yield
            return
    except Exception as e:
        if lock_acquired:
            raise  # exception du body → propager, ne pas déclencher le fallback
        logger.warning(f"Redis lock failed, falling back to memory lock: {e}")
    async with fallback_budget_lock(project_id):
        yield
