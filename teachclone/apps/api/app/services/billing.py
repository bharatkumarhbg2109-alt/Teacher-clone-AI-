"""Plan limits, quota metering, and Stripe checkout/portal.

In DEV_MODE (or on the creator/institution plans) quotas are effectively
unlimited. Stripe calls are no-ops unless a secret key is configured.
"""
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.usage_log import UsageLog

UNLIMITED = 10**9

PLAN_LIMITS = {
    "free": {"sources_per_month": settings.FREE_VIDEOS_PER_MONTH, "messages_per_day": settings.FREE_MESSAGES_PER_DAY,
             "sessions": 10, "exports_per_month": settings.FREE_EXPORTS_PER_MONTH,
             "quizzes_per_month": settings.FREE_QUIZZES_PER_MONTH},
    "pro": {"sources_per_month": 20, "messages_per_day": 500, "sessions": UNLIMITED,
            "exports_per_month": UNLIMITED, "quizzes_per_month": UNLIMITED},
    "creator": {"sources_per_month": UNLIMITED, "messages_per_day": UNLIMITED, "sessions": UNLIMITED,
                "exports_per_month": UNLIMITED, "quizzes_per_month": UNLIMITED},
    "institution": {"sources_per_month": UNLIMITED, "messages_per_day": UNLIMITED, "sessions": UNLIMITED,
                    "exports_per_month": UNLIMITED, "quizzes_per_month": UNLIMITED},
}

_EVENT_LIMIT = {
    "source_processed": "sources_per_month",
    "message_sent": "messages_per_day",
    "quiz_generated": "quizzes_per_month",
    "export_created": "exports_per_month",
}


def get_plan_limits(plan: str) -> dict:
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])


def _period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def _count(db: AsyncSession, user_id, event_type: str, daily: bool) -> int:
    q = select(func.count()).select_from(UsageLog).where(
        UsageLog.user_id == user_id, UsageLog.event_type == event_type
    )
    if daily:
        today = datetime.now(timezone.utc).date()
        q = q.where(func.date(UsageLog.created_at) == today)
    else:
        q = q.where(UsageLog.billing_period == _period())
    return (await db.execute(q)).scalar_one()


async def check_quota(db: AsyncSession, user, event_type: str) -> tuple[bool, str]:
    if settings.DEV_MODE:
        return True, ""
    limits = get_plan_limits(user.plan)
    limit_key = _EVENT_LIMIT.get(event_type)
    if not limit_key:
        return True, ""
    limit = limits[limit_key]
    if limit >= UNLIMITED:
        return True, ""
    used = await _count(db, user.id, event_type, daily=limit_key.endswith("per_day"))
    if used >= limit:
        return False, f"{limit_key} limit reached for the {user.plan} plan"
    return True, ""


async def log_usage(db: AsyncSession, user_id, event_type: str, meta: dict | None = None) -> None:
    db.add(
        UsageLog(
            user_id=user_id,
            event_type=event_type,
            billing_period=_period(),
            meta=meta or {},
        )
    )
    await db.flush()


async def current_usage(db: AsyncSession, user_id) -> dict:
    period = _period()

    async def c(event: str) -> int:
        return (
            await db.execute(
                select(func.count()).select_from(UsageLog).where(
                    UsageLog.user_id == user_id,
                    UsageLog.event_type == event,
                    UsageLog.billing_period == period,
                )
            )
        ).scalar_one()

    return {
        "sources": await c("source_processed"),
        "messages": await c("message_sent"),
        "exports": await c("export_created"),
        "quizzes": await c("quiz_generated"),
    }


# --- Stripe (no-ops without a key) ------------------------------------------
def _stripe():
    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


async def create_checkout_session(user, price_id: str, success_url: str, cancel_url: str) -> str:
    if not settings.STRIPE_SECRET_KEY:
        return success_url  # dev: pretend success
    stripe = _stripe()
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        customer=user.stripe_customer_id or None,
        metadata={"user_id": str(user.id)},
    )
    return session.url


async def create_portal_session(user, return_url: str) -> str:
    if not settings.STRIPE_SECRET_KEY or not user.stripe_customer_id:
        return return_url
    stripe = _stripe()
    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id, return_url=return_url
    )
    return session.url
