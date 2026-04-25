import asyncio
import logging
import re
import secrets
import stripe
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from core.config import settings
from core.database import get_db
from core.limiter import limiter
from core.log_utils import mask_email
from core.models import Project, StripeEvent
from services.onboarding_email import send_onboarding_email, send_downgrade_email

logger = logging.getLogger(__name__)
router = APIRouter(tags=["billing"])

_CHECKOUT_PLANS = {"free", "pro", "agency"}
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _price_ids() -> dict[str, str]:
    return {
        "free": settings.stripe_free_price_id,
        "pro": settings.stripe_pro_price_id,
        "agency": settings.stripe_agency_price_id,
    }


# ── Checkout ──────────────────────────────────────────────────────────────────


@router.post("/api/checkout/{plan}")
@limiter.limit("5/hour")
async def create_checkout_session(request: Request, plan: str):
    if plan not in _CHECKOUT_PLANS:
        raise HTTPException(
            status_code=400,
            detail=f"No checkout available for plan '{plan}'. Valid: {sorted(_CHECKOUT_PLANS)}",
        )

    price_id = _price_ids().get(plan, "")
    if not price_id:
        raise HTTPException(
            status_code=503,
            detail=f"Stripe price ID for plan '{plan}' is not configured on this server.",
        )

    stripe.api_key = settings.stripe_secret_key

    session_params: dict = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": f"{settings.app_url}/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{settings.app_url}/#pricing",
        "metadata": {"plan": plan},
        "allow_promotion_codes": True,
    }
    if plan == "free":
        session_params["payment_method_collection"] = "if_required"
    else:
        session_params["payment_method_types"] = ["card"]

    session = stripe.checkout.Session.create(**session_params)
    return {"checkout_url": session.url}


# ── Stripe webhook ────────────────────────────────────────────────────────────


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError as e:
        logger.warning("Stripe signature verification failed: %s", e)
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    except (ValueError, TypeError) as e:
        logger.warning("Stripe webhook config error: %s", e)
        raise HTTPException(status_code=400, detail="Webhook signature check failed")

    event_id = event.get("id")
    if event_id:
        # F2 — idempotence : tenter l'insert en premier, catcher IntegrityError
        # si un webhook concurrent a déjà inséré le même event_id.
        existing = (
            db.query(StripeEvent).filter(StripeEvent.event_id == event_id).first()
        )
        if existing:
            return {"ok": True}
        db.add(StripeEvent(event_id=event_id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            logger.info("Stripe event %s already processed (race)", event_id)
            return {"ok": True}

    event_type = event.get("type", "")
    data_obj = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data_obj, db)

    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(data_obj, db)

    return {"ok": True}


async def _handle_checkout_completed(session: dict, db: Session) -> None:
    # M1: vérifier payment_status avant toute mise à jour DB
    payment_status = session.get("payment_status")
    if payment_status and payment_status != "paid":
        logger.info(
            "checkout.session.completed ignoré — payment_status=%s (attendu 'paid')",
            payment_status,
        )
        return

    email = (session.get("customer_details") or {}).get("email") or session.get(
        "customer_email"
    )
    if not email or not _EMAIL_RE.match(str(email)):
        logger.warning(
            "Invalid or missing email in checkout — customer=%s session=%s",
            session.get("customer"),
            session.get("id"),
        )
        return

    plan = (session.get("metadata") or {}).get("plan", "pro")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    # Idempotence: upsert if subscription already exists (P2.1)
    if subscription_id:
        existing = (
            db.query(Project)
            .filter(Project.stripe_subscription_id == subscription_id)
            .first()
        )
        if existing:
            existing.plan = plan
            db.commit()
            logger.info(
                "Subscription %s already exists — plan updated to %s (project_id=%s)",
                subscription_id,
                plan,
                existing.id,
            )
            return

    # B2.1 (C14/C15): upsert via email — évite IntegrityError si projet free existe déjà
    existing_by_email = db.query(Project).filter(Project.name == email).first()
    if existing_by_email:
        existing_by_email.plan = plan
        existing_by_email.stripe_customer_id = customer_id
        existing_by_email.stripe_subscription_id = subscription_id
        db.commit()
        logger.info(
            "Existing project %s upgraded to %s (email=%s)",
            existing_by_email.id,
            plan,
            mask_email(email),
        )
        await asyncio.to_thread(
            send_onboarding_email, email, existing_by_email.api_key, plan
        )
        return

    # Nouveau projet (utilisateur qui n'avait pas de compte free)
    project = Project(
        name=email,
        owner_email=email,
        plan=plan,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.info(
        "New %s project created for %s (project_id=%s)",
        plan,
        mask_email(email),
        project.id,
    )

    await asyncio.to_thread(send_onboarding_email, email, project.api_key, plan)


@router.get("/api/billing/reconcile/{session_id}")
@limiter.limit("5/hour")
async def reconcile_stripe_session(
    request: Request, session_id: str, db: Session = Depends(get_db)
):
    # Idempotency: one reconcile per session_id
    reconcile_key = f"reconcile:{session_id}"
    existing = (
        db.query(StripeEvent).filter(StripeEvent.event_id == reconcile_key).first()
    )
    if existing:
        return {"ok": True, "already_processed": True}
    db.add(StripeEvent(event_id=reconcile_key))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"ok": True, "already_processed": True}

    stripe.api_key = settings.stripe_secret_key
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        # Rollback idempotency record so caller can retry
        db.query(StripeEvent).filter(StripeEvent.event_id == reconcile_key).delete()
        db.commit()
        raise HTTPException(status_code=500, detail=f"Stripe error: {e}")

    if session.get("payment_status") != "paid":
        db.query(StripeEvent).filter(StripeEvent.event_id == reconcile_key).delete()
        db.commit()
        raise HTTPException(status_code=402, detail="Payment not completed")

    await _handle_checkout_completed(session, db)
    return {"ok": True}


def _handle_subscription_deleted(subscription: dict, db: Session) -> None:
    subscription_id = subscription.get("id")
    if not subscription_id:
        return
    project = (
        db.query(Project)
        .filter(Project.stripe_subscription_id == subscription_id)
        .first()
    )
    if project:
        # B2.2 (C21): rotation clé API + reset budget au downgrade
        old_key = project.api_key
        project.plan = "free"
        project.budget_usd = None
        project.previous_api_key = old_key
        project.api_key = f"bf-{secrets.token_urlsafe(32)}"
        project.key_rotated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        logger.info(
            "Project %s downgraded to free, API key rotated (subscription %s cancelled)",
            project.id,
            subscription_id,
        )
        send_downgrade_email(project.name)


def validate_stripe_config() -> None:
    """Vérifie que le secret webhook Stripe est configuré. À appeler au démarrage."""
    if not settings.stripe_webhook_secret:
        logger.critical(
            "STRIPE_WEBHOOK_SECRET non configuré — "
            "la vérification des webhooks Stripe sera refusée (400)"
        )
