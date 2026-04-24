"""TDD RED — BudgetLock: test du lock mémoire vs lock distribué.

Ces tests démontrent la limitation du lock mémoire actuel
et préparent les tests pour le lock distribué Redis.
"""

import asyncio
import pytest

from services.budget_lock import budget_lock


class TestBudgetLockMemory:
    """Tests du lock mémoire actuel — efficace single-process mais pas multi-process."""

    @pytest.mark.asyncio
    async def test_lock_serializes_access_same_process(self):
        """Le lock sérialise l'accès dans le même processus."""
        project_id = 42
        counter = 0

        async def task1():
            nonlocal counter
            async with budget_lock(project_id):
                current = counter
                await asyncio.sleep(0.01)
                counter = current + 1

        async def task2():
            nonlocal counter
            await asyncio.sleep(0.005)  # Démarre légèrement après task1
            async with budget_lock(project_id):
                current = counter
                await asyncio.sleep(0.01)
                counter = current + 1

        await asyncio.gather(task1(), task2())

        # Le lock doit sérialiser: les deux tâches ne peuvent pas modifier counter simultanément
        assert counter == 2, "Both tasks should have incremented counter sequentially"

    @pytest.mark.asyncio
    async def test_lock_released_on_exception(self):
        """Le lock est relâché même en cas d'exception."""
        project_id = 43
        lock_acquired = False

        async def task_with_exception():
            nonlocal lock_acquired
            try:
                async with budget_lock(project_id):
                    lock_acquired = True
                    raise ValueError("Test exception")
            except ValueError:
                pass

        await task_with_exception()
        assert lock_acquired

        # Le lock doit être relâché, une autre tâche peut l'acquérir
        async def verify_lock_released():
            async with budget_lock(project_id):
                return True

        result = await verify_lock_released()
        assert result

    @pytest.mark.asyncio
    async def test_different_project_ids_have_separate_locks(self):
        """Les locks sont séparés par project_id."""
        execution_order = []

        async def task_project_1():
            async with budget_lock(1):
                execution_order.append("project1-start")
                await asyncio.sleep(0.01)
                execution_order.append("project1-end")

        async def task_project_2():
            async with budget_lock(2):
                execution_order.append("project2-start")
                await asyncio.sleep(0.01)
                execution_order.append("project2-end")

        # Les deux tâches peuvent s'exécuter en parallèle car project_id différents
        await asyncio.gather(task_project_1(), task_project_2())

        # Les tâches peuvent s'exécuter en parallèle
        assert "project1-start" in execution_order
        assert "project2-start" in execution_order
        assert "project1-end" in execution_order
        assert "project2-end" in execution_order
        # Mais l'ordre peut être entrelacé car locks séparés

    @pytest.mark.asyncio
    async def test_lock_creation_on_first_use(self):
        """Le lock fonctionne pour un project_id donné."""
        project_id = 999
        counter = 0

        async def increment():
            nonlocal counter
            async with budget_lock(project_id):
                current = counter
                await asyncio.sleep(0.01)
                counter = current + 1

        # Plusieurs appels concurrents doivent être sérialisés
        tasks = [increment() for _ in range(5)]
        await asyncio.gather(*tasks)

        assert counter == 5, "All increments should be serialized"


class TestBudgetLockLimitations:
    """Tests qui démontrent les limitations du lock mémoire."""

    @pytest.mark.asyncio
    async def test_lock_memory_only_works_single_process(self):
        """Démonstration que le lock mémoire ne fonctionne qu'en single-process.

        Ce test montre pourquoi un lock distribué est nécessaire pour multi-process.
        """
        # Le lock actuel utilise un dict global _project_locks
        # Ce dict n'est PAS partagé entre processus
        # En multi-process, chaque worker aurait son propre dict → race condition

        # Ce test ne peut pas réellement simuler multi-process dans pytest
        # Mais il documente la limitation
        project_id = 100

        # Simule ce qui arriverait en multi-process:
        # Processus 1 acquiert le lock
        async with budget_lock(project_id):
            # Processus 2 (dans un autre worker) aurait son propre dict _project_locks
            # Donc il pourrait aussi acquérir le "lock" pour le même project_id
            # → Race condition
            pass

        # Ce test passe car nous sommes en single-process
        # Mais il documente le problème

    @pytest.mark.asyncio
    async def test_lock_dict_not_shared_across_imports(self):
        """Démonstration que le dict de locks n'est pas partagé si le module est rechargé."""
        # Simule ce qui arrive quand uvicorn reload ou multi-process
        # Chaque worker a son propre import du module → dict séparé

        project_id = 200

        # "Worker 1"

        # "Worker 2" (simule re-import)
        import importlib
        import services.budget_lock

        importlib.reload(services.budget_lock)

        # Les deux workers auraient des dicts séparés
        # → Pas de coordination réelle

        # Ce test ne peut pas réellement simuler cela de façon safe
        # Mais il documente le risque


class TestDistributedLockRequirements:
    """Tests qui définissent les exigences pour le lock distribué."""

    @pytest.mark.asyncio
    async def test_distributed_lock_should_work_across_processes(self):
        """Le lock distribué doit fonctionner entre processus."""
        # Ce test échouera avec l'implémentation actuelle
        # Mais définit l'exigence pour l'implémentation Redis

        project_id = 300

        # Avec Redis, même code mais lock partagé entre processus
        # async with budget_lock(project_id):
        #     # Un autre processus ne peut pas acquérir le lock
        #     pass

        # Pour l'instant, ce test documente simplement l'exigence
        pass

    @pytest.mark.asyncio
    async def test_distributed_lock_should_survive_process_restart(self):
        """Le lock distribué doit survivre au redémarrage des processus."""
        # Redis maintient l'état du lock même si le processus meurt
        # Important pour éviter les deadlocks

        project_id = 301

        # Exigence: si un processus acquiert le lock puis crash
        # Le lock doit être automatiquement libéré après timeout
        # Pour éviter les deadlocks permanents

        # Pour l'instant, ce test documente simplement l'exigence
        pass
