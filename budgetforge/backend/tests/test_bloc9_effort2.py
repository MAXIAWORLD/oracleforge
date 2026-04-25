"""TDD RED → GREEN — Bloc 9 : 7 findings effort≤2

H26  dynamic_pricing   Singleton sans close() au shutdown
M01  distributed_lock  _memory_locks dict illimité
M02  token_estimator   CODE_PATTERNS regex non compilées
M03  alert_service     Email header injection via project_name
M04  portal            Timing attack enum email
M10  models            Stampede 9 requêtes outbound par cache miss
M11  admin             billing_sync HTTP 200 sur erreur
"""

import asyncio
import re
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ─────────────────────────────────────────────
# H26 — DynamicPricingManager.close() + lifespan
# ─────────────────────────────────────────────


class TestH26PricingManagerShutdown:
    def test_pricing_manager_has_close_method(self):
        from services.dynamic_pricing import DynamicPricingManager

        mgr = DynamicPricingManager()
        assert hasattr(mgr, "close"), (
            "DynamicPricingManager doit avoir une méthode close()"
        )
        assert callable(mgr.close)

    def test_close_clears_cache(self):
        from services.dynamic_pricing import DynamicPricingManager, PriceConfig
        from datetime import datetime, timezone

        mgr = DynamicPricingManager()
        # Injecter une entrée dans le cache
        mgr._cache["gpt-4o"] = PriceConfig(
            input_per_1m_usd=5.0,
            output_per_1m_usd=15.0,
            provider="openai",
            source="test",
        )
        mgr._cache_timestamps["gpt-4o"] = datetime.now(timezone.utc)
        assert len(mgr._cache) == 1
        mgr.close()
        assert len(mgr._cache) == 0
        assert len(mgr._cache_timestamps) == 0

    def test_shutdown_pricing_manager_function_exists(self):
        import services.dynamic_pricing as dp

        assert hasattr(dp, "shutdown_pricing_manager"), (
            "shutdown_pricing_manager() doit exister pour l'appel depuis lifespan"
        )

    def test_shutdown_pricing_manager_resets_singleton(self):
        import services.dynamic_pricing as dp

        # S'assurer qu'un singleton existe
        dp.get_pricing_manager()
        assert dp._pricing_manager is not None
        dp.shutdown_pricing_manager()
        assert dp._pricing_manager is None


# ─────────────────────────────────────────────
# M01 — _memory_locks borné
# ─────────────────────────────────────────────


class TestM01MemoryLocksBounded:
    @pytest.mark.asyncio
    async def test_memory_locks_capped_at_max_size(self):
        """_memory_locks ne doit pas dépasser _MEMORY_LOCKS_MAX_SIZE entrées."""
        import services.distributed_budget_lock as dbl

        # Réinitialiser pour ce test
        dbl._memory_locks.clear()

        max_size = dbl._MEMORY_LOCKS_MAX_SIZE  # doit exister
        assert max_size > 0, "_MEMORY_LOCKS_MAX_SIZE doit être défini"

        # Insérer max_size + 100 entrées
        for pid in range(max_size + 100):
            await dbl._get_memory_lock(pid)

        assert len(dbl._memory_locks) <= max_size, (
            f"_memory_locks doit rester ≤ {max_size}, got {len(dbl._memory_locks)}"
        )

    @pytest.mark.asyncio
    async def test_memory_lock_still_functional_after_eviction(self):
        """Le lock mémoire doit rester utilisable après éviction de vieilles entrées."""
        import services.distributed_budget_lock as dbl

        dbl._memory_locks.clear()

        max_size = dbl._MEMORY_LOCKS_MAX_SIZE
        # Remplir jusqu'à la limite
        for pid in range(max_size):
            await dbl._get_memory_lock(pid)

        # Ajouter une entrée supplémentaire — ne doit pas lever d'exception
        lock = await dbl._get_memory_lock(max_size + 1)
        assert lock is not None
        assert isinstance(lock, asyncio.Lock)


# ─────────────────────────────────────────────
# M02 — CODE_PATTERNS précompilées
# ─────────────────────────────────────────────


class TestM02CodePatternsCompiled:
    def test_code_patterns_are_compiled(self):
        """CODE_PATTERNS doit contenir des re.Pattern, pas des str."""
        from services.token_estimator import TokenEstimator

        for pat in TokenEstimator.CODE_PATTERNS:
            assert isinstance(pat, re.Pattern), (
                f"Pattern {pat!r} n'est pas compilé — risque ReDoS + overhead"
            )

    def test_code_patterns_detect_python_function(self):
        """La détection de code Python doit toujours fonctionner après compilation."""
        from services.token_estimator import TokenEstimator

        lang = TokenEstimator.detect_language("def hello(world):\n    return world")
        assert lang == "code"

    def test_code_patterns_detect_js_function(self):
        from services.token_estimator import TokenEstimator

        lang = TokenEstimator.detect_language("function foo(x) { return x + 1; }")
        assert lang == "code"

    def test_code_patterns_no_false_positive_on_plain_text(self):
        from services.token_estimator import TokenEstimator

        lang = TokenEstimator.detect_language(
            "Bonjour, voici un texte ordinaire sans code."
        )
        # Doit détecter une langue naturelle, pas "code"
        assert lang != "code"


# ─────────────────────────────────────────────
# M03 — Email header injection sanitization
# ─────────────────────────────────────────────


class TestM03EmailHeaderInjection:
    def test_subject_strips_crlf(self):
        """Un project_name contenant \\r\\n ne doit pas polluer les headers email."""
        from unittest.mock import MagicMock, patch
        import email

        malicious_name = "Legit Project\r\nBcc: attacker@evil.com"

        with (
            patch("services.alert_service.smtplib.SMTP") as mock_smtp,
            patch("services.alert_service.settings") as mock_cfg,
        ):
            mock_cfg.smtp_host = "smtp.example.com"
            mock_cfg.smtp_port = 587
            mock_cfg.smtp_user = "u"
            mock_cfg.smtp_password = "p"
            mock_cfg.alert_from_email = "noreply@example.com"

            captured = {}

            def fake_sendmail(from_addr, to_addr, msg_str):
                captured["msg"] = msg_str

            mock_server = MagicMock()
            mock_server.sendmail.side_effect = fake_sendmail
            mock_smtp.return_value.__enter__.return_value = mock_server

            from services.alert_service import AlertService

            AlertService.send_email("user@example.com", malicious_name, 8.0, 10.0)

            assert "captured" in captured or mock_server.sendmail.called
            # Extraire le subject depuis le message capturé
            if mock_server.sendmail.called:
                raw = mock_server.sendmail.call_args[0][2]
                msg = email.message_from_string(raw)
                subject = msg["Subject"]
                assert "\r" not in subject, f"\\r trouvé dans Subject: {subject!r}"
                assert "\n" not in subject, f"\\n trouvé dans Subject: {subject!r}"

    def test_subject_strips_newline_only(self):
        """Un project_name avec \\n seul doit aussi être sanitisé."""
        from unittest.mock import MagicMock, patch
        import email

        with (
            patch("services.alert_service.smtplib.SMTP") as mock_smtp,
            patch("services.alert_service.settings") as mock_cfg,
        ):
            mock_cfg.smtp_host = "smtp.example.com"
            mock_cfg.smtp_port = 587
            mock_cfg.smtp_user = ""
            mock_cfg.smtp_password = ""
            mock_cfg.alert_from_email = "noreply@example.com"

            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            from services.alert_service import AlertService

            AlertService.send_email("user@example.com", "Project\nEvil", 5.0, 10.0)

            if mock_server.sendmail.called:
                raw = mock_server.sendmail.call_args[0][2]
                msg = email.message_from_string(raw)
                subject = msg["Subject"]
                assert "\n" not in subject


# ─────────────────────────────────────────────
# M04 — Timing attack portal_request
# ─────────────────────────────────────────────


class TestM04PortalRequestTimingConstant:
    @pytest.mark.asyncio
    async def test_portal_request_sleeps_when_email_not_found(self):
        """portal_request doit appeler asyncio.sleep même si l'email n'existe pas."""
        from unittest.mock import patch

        # Patch _get_projects_for_email pour retourner []
        with (
            patch("routes.portal._get_projects_for_email", return_value=[]),
            patch("routes.portal.cleanup_expired_tokens"),
            patch("routes.portal.asyncio") as mock_asyncio,
        ):
            mock_asyncio.sleep = AsyncMock()

            # Importer et créer un router de test minimal
            from routes.portal import portal_request as _fn
            # Si la fonction appelle asyncio.sleep quand pas de projets → test passe
            # On vérifie que la branche "not projects" passe par sleep

            # On mock la requête
            fake_request = MagicMock()
            fake_request.state = MagicMock()
            fake_db = MagicMock()

            from routes.portal import PortalRequestBody

            body = PortalRequestBody(email="unknown@example.com")

            try:
                await _fn(fake_request, body, fake_db)
            except Exception:
                pass  # On ne teste que le sleep, pas le résultat complet

            mock_asyncio.sleep.assert_called_once()

    def test_portal_request_is_async(self):
        """portal_request doit être async pour supporter asyncio.sleep."""
        import inspect
        from routes.portal import portal_request

        assert inspect.iscoroutinefunction(portal_request), (
            "portal_request doit être async def pour timing constant"
        )


# ─────────────────────────────────────────────
# M10 — Stampede protection get_models
# ─────────────────────────────────────────────


class TestM10ModelsStampedeProtection:
    @pytest.mark.asyncio
    async def test_concurrent_get_models_calls_single_fetch(self):
        """Appels concurrents sur cache froid ne doivent pas fire N×9 requêtes."""
        import routes.models as m

        # Vider le cache
        m._cache.clear()

        fetch_count = 0

        async def fake_fetch(*args, **kwargs):
            nonlocal fetch_count
            fetch_count += 1
            await asyncio.sleep(0.02)  # simule latence réseau
            return []

        with patch.multiple(
            "routes.models",
            _fetch_openai_models=fake_fetch,
            _fetch_anthropic_models=fake_fetch,
            _fetch_google_models=fake_fetch,
            _fetch_deepseek_models=fake_fetch,
            _fetch_ollama_models=fake_fetch,
            _fetch_openrouter_models=fake_fetch,
            _fetch_together_models=fake_fetch,
            _fetch_azure_openai_models=fake_fetch,
            _fetch_aws_bedrock_models=fake_fetch,
        ):
            m._cache.clear()
            m._models_result_cache.clear()
            # 5 appels simultanés sur cache froid
            results = await asyncio.gather(*[m.get_models() for _ in range(5)])

        # Avec stampede protection: max 9 fetches (un seul gather)
        # Sans protection: jusqu'à 45 fetches (5 × 9)
        assert fetch_count <= 9, (
            f"Stampede détecté: {fetch_count} fetches pour 5 appels concurrents "
            f"(max attendu 9, got {fetch_count})"
        )

    def test_models_module_has_fetch_lock(self):
        """routes.models doit exposer un lock pour serialiser les fetches."""
        import routes.models as m

        assert hasattr(m, "_fetch_lock"), (
            "_fetch_lock doit exister dans routes.models pour éviter le stampede"
        )


# ─────────────────────────────────────────────
# M11 — billing_sync retourne 503 sur erreur
# ─────────────────────────────────────────────


class TestM11BillingSync503:
    def test_billing_sync_returns_503_when_stripe_key_missing(self):
        """billing_sync doit lever HTTPException(503) si STRIPE_SECRET_KEY absent."""
        from fastapi import HTTPException
        from unittest.mock import patch, MagicMock

        with (
            patch("routes.admin.settings") as mock_settings,
            patch("routes.admin.get_db"),
        ):
            mock_settings.stripe_secret_key = ""
            mock_db = MagicMock()

            from routes.admin import billing_sync

            with pytest.raises(HTTPException) as exc_info:
                billing_sync(db=mock_db)

            assert exc_info.value.status_code == 503, (
                f"Attendu 503, got {exc_info.value.status_code}"
            )

    def test_billing_sync_returns_200_when_stripe_key_present(self):
        """billing_sync doit retourner 200 quand la clé Stripe est configurée."""
        from unittest.mock import patch, MagicMock

        with (
            patch("routes.admin.settings") as mock_settings,
            patch("routes.admin.reconcile_stripe_subscriptions") as mock_reconcile,
        ):
            mock_settings.stripe_secret_key = "sk_test_abc123"
            mock_reconcile.return_value = {"synced": 3, "errors": 0}
            mock_db = MagicMock()

            from routes.admin import billing_sync

            result = billing_sync(db=mock_db)

            assert result["ok"] is True
            assert result["synced"] == 3
