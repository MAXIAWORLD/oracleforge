import logging
import stripe
from sqlalchemy.orm import Session
from core.config import settings
from core.models import Project

logger = logging.getLogger(__name__)

_PLAN_PRICE_MAP = {
    "pro": ["pro", "price_pro"],
    "agency": ["agency", "price_agency"],
}


def _plan_from_subscription(sub) -> str:
    """Derive plan name from Stripe subscription items."""
    for item in sub.items.data:
        nickname = (item.price.nickname or "").lower()
        price_id = item.price.id or ""
        if "agency" in nickname or "agency" in price_id:
            return "agency"
        if "pro" in nickname or "pro" in price_id:
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
