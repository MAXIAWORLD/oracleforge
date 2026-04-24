import pytest
import asyncio
import redis.asyncio as redis
from services.distributed_budget_lock import (
    distributed_budget_lock,
    fallback_budget_lock,
    set_redis_config,
    close_redis_connection,
)


@pytest.fixture
def redis_test_config():
    """Configure Redis pour les tests."""
    set_redis_config(host="localhost", port=6379, db=1)  # Utiliser DB 1 pour les tests
    yield
    # Nettoyer après le test
    asyncio.run(close_redis_connection())


@pytest.fixture
def redis_client():
    """Client Redis pour les tests."""
    return redis.Redis(host="localhost", port=6379, db=1, decode_responses=False)


@pytest.mark.asyncio
class TestDistributedLockRedis:
    """Tests pour le verrou distribué Redis."""

    async def test_distributed_lock_acquire_release(
        self, redis_test_config, redis_client
    ):
        """Test l'acquisition et libération basique du lock Redis."""
        project_id = 999
        lock_key = f"budget_lock:{project_id}"

        async with distributed_budget_lock(project_id):
            # Vérifier que le lock est présent dans Redis
            lock_exists = await redis_client.exists(lock_key)
            assert lock_exists == 1, "Lock should exist in Redis"

            # Vérifier que le TTL est raisonnable
            ttl = await redis_client.ttl(lock_key)
            assert 0 < ttl <= 60, f"TTL should be between 1 and 60 seconds, got {ttl}"

        # Vérifier que le lock est libéré
        lock_exists = await redis_client.exists(lock_key)
        assert lock_exists == 0, "Lock should be released from Redis"

    async def test_distributed_lock_prevents_concurrent_access(self, redis_test_config):
        """Test que le lock distribué empêche l'accès concurrent."""
        project_id = 1000
        access_count = 0

        async def critical_section():
            nonlocal access_count
            async with distributed_budget_lock(project_id):
                # Simuler une opération critique
                current_count = access_count
                await asyncio.sleep(
                    0.01
                )  # Petite pause pour créer une condition de course
                access_count = current_count + 1

        # Lancer plusieurs tâches concurrentes
        tasks = [critical_section() for _ in range(10)]
        await asyncio.gather(*tasks)

        # Vérifier qu'il n'y a pas eu de condition de course
        assert access_count == 10, (
            "All critical sections should have executed sequentially"
        )

    async def test_distributed_lock_timeout(self, redis_test_config, redis_client):
        """Test le timeout quand le lock n'est pas disponible."""
        project_id = 1001
        lock_key = f"budget_lock:{project_id}"

        # Acquérir le lock d'abord
        await redis_client.set(lock_key, b"locked", ex=60)

        # Essayer d'acquérir avec un timeout court
        with pytest.raises(TimeoutError):
            async with distributed_budget_lock(project_id, timeout=0.1):
                pass

        # Nettoyer
        await redis_client.delete(lock_key)

    async def test_distributed_lock_across_processes_simulation(
        self, redis_test_config
    ):
        """Simule l'utilisation du lock distribué par plusieurs processus."""
        project_id = 1002
        results = []

        async def process_1():
            async with distributed_budget_lock(project_id):
                results.append("process_1_start")
                await asyncio.sleep(0.05)
                results.append("process_1_end")

        async def process_2():
            await asyncio.sleep(0.01)  # Démarrer légèrement après
            async with distributed_budget_lock(project_id):
                results.append("process_2_start")
                await asyncio.sleep(0.05)
                results.append("process_2_end")

        # Exécuter les deux processus
        await asyncio.gather(process_1(), process_2())

        # Vérifier la sérialisation
        assert results == [
            "process_1_start",
            "process_1_end",
            "process_2_start",
            "process_2_end",
        ], "Processes should execute sequentially"


@pytest.mark.asyncio
class TestFallbackLock:
    """Tests pour le fallback mémoire."""

    async def test_fallback_lock_basic_functionality(self):
        """Test le fonctionnement basique du fallback mémoire."""
        project_id = 2000
        counter = 0

        async def critical_section():
            nonlocal counter
            async with fallback_budget_lock(project_id):
                current = counter
                await asyncio.sleep(0.01)
                counter = current + 1

        tasks = [critical_section() for _ in range(5)]
        await asyncio.gather(*tasks)

        assert counter == 5, "Fallback lock should prevent race conditions"

    async def test_fallback_lock_isolation(self):
        """Test que les locks sont isolés par project_id."""
        counters = {1: 0, 2: 0}

        async def critical_section(pid):
            async with fallback_budget_lock(pid):
                current = counters[pid]
                await asyncio.sleep(0.01)
                counters[pid] = current + 1

        # Lancer des tâches pour les deux projets
        tasks = []
        for pid in [1, 2]:
            tasks.extend([critical_section(pid) for _ in range(3)])

        await asyncio.gather(*tasks)

        assert counters[1] == 3, "Project 1 should have 3 increments"
        assert counters[2] == 3, "Project 2 should have 3 increments"


@pytest.mark.asyncio
class TestIntegration:
    """Tests d'intégration pour le système complet."""

    async def test_main_export_uses_distributed_first(
        self, redis_test_config, redis_client
    ):
        """Test que l'export principal utilise Redis d'abord."""
        from services.distributed_budget_lock import budget_lock

        project_id = 3000
        lock_key = f"budget_lock:{project_id}"

        async with budget_lock(project_id):
            # Vérifier que Redis est utilisé
            lock_exists = await redis_client.exists(lock_key)
            assert lock_exists == 1, "Main export should use Redis when available"

        # Vérifier libération
        lock_exists = await redis_client.exists(lock_key)
        assert lock_exists == 0, "Lock should be released"

    async def test_main_export_falls_back_when_redis_unavailable(self):
        """Test le fallback quand Redis n'est pas disponible."""
        from services.distributed_budget_lock import budget_lock

        # Configurer une connexion Redis invalide
        set_redis_config(host="invalid-host", port=6379)

        project_id = 3001
        counter = 0

        async def critical_section():
            nonlocal counter
            async with budget_lock(project_id):
                current = counter
                await asyncio.sleep(0.01)
                counter = current + 1

        # Devrait utiliser le fallback sans erreur
        tasks = [critical_section() for _ in range(3)]
        await asyncio.gather(*tasks)

        assert counter == 3, "Should work with fallback when Redis is unavailable"

        # Restaurer la configuration
        set_redis_config(host="localhost", port=6379, db=1)
