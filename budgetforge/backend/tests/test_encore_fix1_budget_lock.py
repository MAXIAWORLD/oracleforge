"""TDD RED — encore fix1 : fallback_budget_lock doit utiliser fcntl.flock sur Linux.

Le fallback actuel utilise asyncio.Lock (in-process uniquement).
Avec 2 workers uvicorn, chaque worker a son propre asyncio.Lock → race condition.
Fix requis : utiliser fcntl.flock (OS-level, cross-process) sur Linux.

Ces tests mockent sys.platform pour tourner sur Windows (dev) ET Linux (prod).
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock


class TestFallbackSelectsCorrectImpl:
    """fallback_budget_lock doit choisir file-lock sur Linux, asyncio.Lock sur Windows."""

    @pytest.mark.asyncio
    async def test_linux_path_uses_file_lock(self, tmp_path, monkeypatch):
        """Sur Linux (mock), le fallback doit ouvrir un fichier lock et appeler fcntl.flock."""
        # Force le chemin Linux
        monkeypatch.setattr("sys.platform", "linux")

        flock_calls = []
        mock_fh = MagicMock()

        def fake_flock(fd, operation):
            flock_calls.append(operation)

        # Recharger le module pour prendre en compte sys.platform mocké
        import importlib
        import services.distributed_budget_lock as mod

        # On patche fcntl au niveau du module (il peut ne pas exister sur Windows)
        mock_fcntl = MagicMock()
        mock_fcntl.LOCK_EX = 2
        mock_fcntl.LOCK_UN = 8
        mock_fcntl.flock = fake_flock

        with patch.dict("sys.modules", {"fcntl": mock_fcntl}):
            # Recharger pour que le module capte la nouvelle platform
            importlib.reload(mod)
            try:
                project_id = 88_001
                async with mod.fallback_budget_lock(project_id):
                    pass
            finally:
                importlib.reload(mod)  # Restaurer

        # Le fallback Linux doit avoir appelé flock avec LOCK_EX
        assert 2 in flock_calls, (
            "fallback_budget_lock on Linux must call fcntl.flock(LOCK_EX). "
            "Current code uses asyncio.Lock — fix needed."
        )

    @pytest.mark.asyncio
    async def test_windows_path_uses_asyncio_lock(self, monkeypatch):
        """Sur Windows, fallback_budget_lock doit utiliser asyncio.Lock (pas fcntl)."""
        monkeypatch.setattr("sys.platform", "win32")

        from services.distributed_budget_lock import fallback_budget_lock

        counter = 0

        async def increment():
            nonlocal counter
            async with fallback_budget_lock(88_002):
                v = counter
                await asyncio.sleep(0.005)
                counter = v + 1

        await asyncio.gather(*[increment() for _ in range(3)])
        assert counter == 3, "Windows asyncio.Lock must serialize tasks"


class TestFallbackFileLockBehavior:
    """Comportement du file lock : sérialisation, robustesse aux exceptions."""

    @pytest.mark.asyncio
    async def test_concurrent_tasks_serialized_with_file_lock(self, monkeypatch):
        """Deux tâches async doivent être sérialisées via file lock."""
        # On ne peut pas simuler le vrai cross-process en pytest,
        # mais on valide que les calls asyncio.to_thread se font en séquence
        import importlib
        import services.distributed_budget_lock as mod

        monkeypatch.setattr("sys.platform", "linux")

        call_log = []
        original_to_thread = asyncio.to_thread

        async def tracking_to_thread(fn, *args, **kwargs):
            if fn.__name__ in ("_acquire_file_lock", "_release_file_lock"):
                call_log.append(fn.__name__)
            return await original_to_thread(fn, *args, **kwargs)

        mock_fcntl = MagicMock()
        mock_fcntl.LOCK_EX = 2
        mock_fcntl.LOCK_UN = 8
        mock_fcntl.flock = MagicMock()

        with patch.dict("sys.modules", {"fcntl": mock_fcntl}):
            importlib.reload(mod)
            try:
                with patch("asyncio.to_thread", side_effect=tracking_to_thread):

                    async def task():
                        async with mod.fallback_budget_lock(88_010):
                            await asyncio.sleep(0.01)

                    await asyncio.gather(task(), task())
            finally:
                importlib.reload(mod)

        # Doit avoir eu acquire + release pour chaque tâche
        assert call_log.count("_acquire_file_lock") == 2, (
            f"Expected 2 _acquire_file_lock calls, got {call_log}"
        )
        assert call_log.count("_release_file_lock") == 2, (
            f"Expected 2 _release_file_lock calls, got {call_log}"
        )

    @pytest.mark.asyncio
    async def test_file_lock_released_on_exception(self, monkeypatch):
        """Le file lock doit être relâché même en cas d'exception."""
        import importlib
        import services.distributed_budget_lock as mod

        monkeypatch.setattr("sys.platform", "linux")

        release_called = []

        async def tracking_to_thread(fn, *args, **kwargs):
            if fn.__name__ == "_release_file_lock":
                release_called.append(True)
            # Simuler sans vrais fichiers
            if fn.__name__ == "_acquire_file_lock":
                return MagicMock()
            if fn.__name__ == "_release_file_lock":
                return None
            return MagicMock()

        mock_fcntl = MagicMock()
        mock_fcntl.LOCK_EX = 2
        mock_fcntl.LOCK_UN = 8
        mock_fcntl.flock = MagicMock()

        with patch.dict("sys.modules", {"fcntl": mock_fcntl}):
            importlib.reload(mod)
            try:
                with patch("asyncio.to_thread", side_effect=tracking_to_thread):
                    try:
                        async with mod.fallback_budget_lock(88_011):
                            raise RuntimeError("crash simulé")
                    except RuntimeError:
                        pass
            finally:
                importlib.reload(mod)

        assert release_called, "_release_file_lock must be called even after exception"
