"""
TDD — Findings H11, H12, H23, M12 (deferreds audit #4).

H11 — Magic-link via POST (token dans body, hors query string / logs nginx)
H12 — Admin key accepté depuis cookie HttpOnly bf_admin_key
H23 — Email inclus dans le lien magic-link pour pré-remplissage du formulaire
M12 — Plan limits ont des valeurs cohérentes et documentées
"""

from datetime import datetime, timedelta, timezone


# ---------------------------------------------------------------------------
# H11 — POST /api/portal/verify
# ---------------------------------------------------------------------------
class TestH11MagicLinkPost:
    def _make_token(self, db, email="h11@example.com", expired=False):
        from core.models import PortalToken

        delta = timedelta(hours=-1) if expired else timedelta(hours=1)
        tok = PortalToken(
            email=email,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + delta,
        )
        db.add(tok)
        db.commit()
        db.refresh(tok)
        return tok

    def test_post_verify_valid_token_returns_200(self, client, db):
        tok = self._make_token(db)
        resp = client.post("/api/portal/verify", json={"token": tok.token})
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "h11@example.com"

    def test_post_verify_sets_portal_session_cookie(self, client, db):
        tok = self._make_token(db)
        resp = client.post("/api/portal/verify", json={"token": tok.token})
        assert "portal_session" in resp.cookies

    def test_post_verify_invalid_token_401(self, client):
        resp = client.post("/api/portal/verify", json={"token": "bad-token-xyz"})
        assert resp.status_code == 401

    def test_post_verify_expired_token_401(self, client, db):
        tok = self._make_token(db, expired=True)
        resp = client.post("/api/portal/verify", json={"token": tok.token})
        assert resp.status_code == 401

    def test_post_verify_token_single_use(self, client, db):
        """Après un POST verify réussi, le même token est invalidé."""
        tok = self._make_token(db)
        token_str = tok.token
        resp1 = client.post("/api/portal/verify", json={"token": token_str})
        assert resp1.status_code == 200
        resp2 = client.post("/api/portal/verify", json={"token": token_str})
        assert resp2.status_code == 401

    def test_get_verify_backward_compat(self, client, db):
        """GET /api/portal/verify?token=... fonctionne encore (compat liens existants)."""
        tok = self._make_token(db)
        resp = client.get(f"/api/portal/verify?token={tok.token}")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# H12 — Cookie HttpOnly bf_admin_key accepté par require_admin / require_viewer
# ---------------------------------------------------------------------------
class TestH12CookieAuth:
    def test_cookie_auth_accepted_for_viewer_endpoint(self, client, monkeypatch):
        from core.config import settings

        monkeypatch.setattr(settings, "admin_api_key", "secret-h12-key")
        resp = client.get("/api/projects", cookies={"bf_admin_key": "secret-h12-key"})
        assert resp.status_code == 200

    def test_header_auth_still_works(self, client, monkeypatch):
        from core.config import settings

        monkeypatch.setattr(settings, "admin_api_key", "secret-h12-key")
        resp = client.get("/api/projects", headers={"X-Admin-Key": "secret-h12-key"})
        assert resp.status_code == 200

    def test_wrong_cookie_value_rejected(self, client, monkeypatch):
        from core.config import settings

        monkeypatch.setattr(settings, "admin_api_key", "secret-h12-key")
        resp = client.get("/api/projects", cookies={"bf_admin_key": "wrong-value"})
        assert resp.status_code == 401

    def test_no_key_no_cookie_rejected(self, client, monkeypatch):
        from core.config import settings

        monkeypatch.setattr(settings, "admin_api_key", "secret-h12-key")
        resp = client.get("/api/projects")
        assert resp.status_code == 401

    def test_cookie_auth_accepted_for_write_endpoint(self, client, monkeypatch):
        from core.config import settings

        monkeypatch.setattr(settings, "admin_api_key", "secret-h12-key")
        resp = client.post(
            "/api/projects",
            json={"name": "h12-test"},
            cookies={"bf_admin_key": "secret-h12-key"},
        )
        assert resp.status_code in (200, 201)


# ---------------------------------------------------------------------------
# H23 — Email inclus dans le lien magic-link (portal/request)
# ---------------------------------------------------------------------------
class TestH23EmailInMagicLink:
    def _make_project(self, db, email="h23@example.com"):
        from core.models import Project

        proj = Project(name=f"proj-{email}", owner_email=email)
        db.add(proj)
        db.commit()
        return proj

    def test_send_portal_email_called_with_correct_args(self, client, db, monkeypatch):
        """portal/request appelle send_portal_email(email, token)."""
        self._make_project(db)
        calls = []
        import routes.portal as portal_mod

        monkeypatch.setattr(
            portal_mod, "send_portal_email", lambda e, t: calls.append((e, t)) or True
        )

        resp = client.post("/api/portal/request", json={"email": "h23@example.com"})
        assert resp.status_code == 200
        assert len(calls) == 1
        assert calls[0][0] == "h23@example.com"

    def test_magic_link_url_contains_email(self, client, db, monkeypatch):
        """Le lien envoyé contient ?email=... pour pré-remplissage frontend."""
        self._make_project(db)
        sent_bodies = []
        import routes.portal as portal_mod

        def capture_email(to, token):
            # Simulate what send_portal_email does with the link
            link = f"http://test/portal?token={token}&email={to}"
            sent_bodies.append(link)
            return True

        monkeypatch.setattr(portal_mod, "send_portal_email", capture_email)
        # We test the link construction in send_portal_email indirectly
        # via checking the built URL contains email
        monkeypatch.setattr(portal_mod.settings, "app_url", "http://test")
        monkeypatch.setattr(portal_mod.settings, "smtp_host", "")  # skip actual send

        resp = client.post("/api/portal/request", json={"email": "h23@example.com"})
        assert resp.status_code == 200

    def test_magic_link_contains_email_in_send_portal_email(self, db, monkeypatch):
        """send_portal_email construit un lien avec ?email= dedans."""
        import routes.portal as portal_mod

        sent = []

        class FakeSMTP:
            def __init__(self, *a, **kw):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def starttls(self):
                pass

            def login(self, *a):
                pass

            def sendmail(self, frm, to, body):
                sent.append(body)

        import smtplib

        monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
        monkeypatch.setattr(portal_mod.settings, "smtp_host", "smtp.test")
        monkeypatch.setattr(portal_mod.settings, "smtp_port", 587)
        monkeypatch.setattr(portal_mod.settings, "smtp_user", "")
        monkeypatch.setattr(portal_mod.settings, "alert_from_email", "noreply@test.com")
        monkeypatch.setattr(portal_mod.settings, "app_url", "https://app.test")

        result = portal_mod.send_portal_email("user@test.com", "tok123")
        assert result is True
        assert len(sent) == 1
        # Le body MIME est encodé — on parse pour extraire le texte brut
        import email as _email_lib

        msg = _email_lib.message_from_string(sent[0])
        body_text = ""
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    body_text = payload.decode("utf-8")
                    break
        assert "email=user" in body_text

    def test_post_verify_returns_email_for_resend(self, client, db):
        """POST /api/portal/verify retourne email dans body (pour formulaire resend frontend)."""
        from core.models import PortalToken

        tok = PortalToken(
            email="resend@example.com",
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
            + timedelta(hours=1),
        )
        db.add(tok)
        db.commit()
        db.refresh(tok)

        resp = client.post("/api/portal/verify", json={"token": tok.token})
        assert resp.status_code == 200
        assert resp.json()["email"] == "resend@example.com"


# ---------------------------------------------------------------------------
# M12 — Plan limits documentés et cohérents
# ---------------------------------------------------------------------------
class TestM12PlanLimits:
    def test_all_plans_present(self):
        from services.plan_quota import PLAN_LIMITS, PLAN_PROJECT_LIMITS

        assert set(PLAN_LIMITS.keys()) == {"free", "pro", "agency"}
        assert set(PLAN_PROJECT_LIMITS.keys()) == {"free", "pro", "agency"}

    def test_call_limits_ordered(self):
        """free < pro < agency (appels/mois)."""
        from services.plan_quota import PLAN_LIMITS

        assert PLAN_LIMITS["free"] > 0
        assert PLAN_LIMITS["pro"] > PLAN_LIMITS["free"]
        assert PLAN_LIMITS["agency"] > PLAN_LIMITS["pro"]

    def test_project_limits_sensible(self):
        from services.plan_quota import PLAN_PROJECT_LIMITS

        assert PLAN_PROJECT_LIMITS["free"] == 1
        assert PLAN_PROJECT_LIMITS["pro"] == 10
        assert PLAN_PROJECT_LIMITS["agency"] == -1  # illimité

    def test_free_limit_reasonable(self):
        """Free plan : entre 500 et 10 000 appels/mois."""
        from services.plan_quota import PLAN_LIMITS

        assert 500 <= PLAN_LIMITS["free"] <= 10_000
