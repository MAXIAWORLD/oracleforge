import logging
import stripe
from sqlalchemy.orm import Session
from core.config import settings
from core.models import Project

logger = logging.getLogger(__name__)


def _plan_from_price_id(price_id: str) -> str:
    """B2.4 (H25): dériver le plan depuis le price_id configuré en env vars.

    Utilise les env vars STRIPE_PRO_PRICE_ID et STRIPE_AGENCY_PRICE_ID
    plutôt qu'un string match fragile sur le nickname.
    """
    if price_id and price_id == settings.stripe_agency_price_id:
        return "agency"
    if price_id and price_id == settings.stripe_pro_price_id:
        return "pro"
    return "free"


def _plan_from_subscription(sub) -> str:
    """Derive plan name from Stripe subscription items.

    Priorité: price_id (env vars) > nickname (fallback compat).
    """
    for item in sub.items.data:
        price_id = item.price.id or ""
        plan = _plan_from_price_id(price_id)
        if plan != "free":
            return plan
        # Fallback sur nickname pour compat avec Stripe configuré avant env vars
        nickname = (item.price.nickname or "").lower()
        if "agency" in nickname:
            return "agency"
        if "pro" in nickname:
            return "pro"
    return "free"


def reconcile_stripe_subscriptions(db: Session) -> dict:
    """
    Compare active Stripe subscriptions with local DB and fix divergences.
    Returns counts: updated, downgraded, skipped.
    """
    stripe.api_key = settings.stripe_secret_key

    updated = 0
    downgraded = 0
    skipped = 0

    # Fetch all subscriptions (active + cancelled) to catch missed webhooks
    for status in ("active", "canceled"):
        page = stripe.Subscription.list(status=status, limit=100, expand=["data.items"])
        for sub in page.auto_paging_iter():
            project = (
                db.query(Project)
                .filter(Project.stripe_subscription_id == sub.id)
                .first()
            )
            if project is None:
                logger.debug("Subscription %s has no local project — skipped", sub.id)
                skipped += 1
                continue

            if sub.status == "canceled":
                if project.plan != "free":
                    project.plan = "free"
                    db.commit()
                    logger.info(
                        "Reconcile: project %s downgraded to free (sub %s canceled)",
                        project.id,
                        sub.id,
                    )
                    downgraded += 1
            else:
                expected_plan = _plan_from_subscription(sub)
                if project.plan != expected_plan:
                    logger.info(
                        "Reconcile: project %s plan %s → %s (sub %s)",
                        project.id,
                        project.plan,
                        expected_plan,
                        sub.id,
                    )
                    project.plan = expected_plan
                    db.commit()
                    updated += 1

    return {"updated": updated, "downgraded": downgraded, "skipped": skipped}
