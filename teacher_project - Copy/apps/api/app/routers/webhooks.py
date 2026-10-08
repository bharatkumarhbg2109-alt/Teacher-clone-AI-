"""Clerk + Stripe webhooks. No-ops gracefully when secrets are unset."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.models.user import User
from app.models.user_stats import UserStats

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = logging.getLogger("teachclone.webhooks")

# --- IP3: Billing event log ------------------------------------------------
BILLING_LOG = Path("billing_log.json")


def log_billing_event(event_type: str, data: dict) -> None:
    """Append a billing event to billing_log.json (one JSON object per line)."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        **data,
    }
    with open(BILLING_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    log.info("Billing event: %s %s", event_type, data)


# --- IP4: Clerk webhook signature verification ------------------------------
async def _verify_clerk_webhook(request: Request) -> dict:
    """Verify the Clerk webhook signature using svix.

    Raises HTTPException(400) if the secret is missing or the signature is
    invalid.  Returns the parsed JSON payload on success.
    """
    secret = settings.CLERK_WEBHOOK_SECRET
    if not secret:
        raise HTTPException(
            status_code=400,
            detail="CLERK_WEBHOOK_SECRET is not configured. Webhook rejected.",
        )

    payload_bytes = await request.body()
    headers = {
        "svix-id": request.headers.get("svix-id", ""),
        "svix-timestamp": request.headers.get("svix-timestamp", ""),
        "svix-signature": request.headers.get("svix-signature", ""),
    }

    try:
        from svix.webhooks import Webhook, WebhookVerificationError

        wh = Webhook(secret)
        return wh.verify(payload_bytes, headers)
    except WebhookVerificationError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid webhook signature: {exc}")


@router.post("/clerk")
async def clerk_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    body = await request.body()

    if settings.CLERK_WEBHOOK_SECRET:
        payload = await _verify_clerk_webhook(request)
    else:
        # No secret configured — parse body directly (dev mode only).
        payload = await request.json()

    event = payload.get("type")
    data = payload.get("data", {})
    clerk_id = data.get("id")
    if not clerk_id:
        return {"ok": True}

    existing = (
        await db.execute(select(User).where(User.clerk_id == clerk_id))
    ).scalar_one_or_none()

    if event == "user.created" and not existing:
        emails = data.get("email_addresses", [])
        email = emails[0].get("email_address") if emails else f"{clerk_id}@clerk.local"
        user = User(
            clerk_id=clerk_id,
            email=email,
            full_name=f"{data.get('first_name', '')} {data.get('last_name', '')}".strip(),
            avatar_url=data.get("image_url"),
        )
        db.add(user)
        await db.flush()
        db.add(UserStats(user_id=user.id))
    elif event == "user.updated" and existing:
        emails = data.get("email_addresses", [])
        if emails:
            existing.email = emails[0].get("email_address", existing.email)
        existing.avatar_url = data.get("image_url", existing.avatar_url)
    elif event == "user.deleted" and existing:
        existing.is_active = False

    await db.flush()
    return {"ok": True}


@router.post("/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    body = await request.body()
    if not settings.STRIPE_SECRET_KEY:
        return {"ok": True, "skipped": True}

    import stripe

    try:
        event = stripe.Webhook.construct_event(
            body, request.headers.get("stripe-signature", ""), settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception:
        return {"ok": False, "error": "invalid signature"}

    kind = event["type"]
    obj = event["data"]["object"]
    customer = obj.get("customer")

    if kind == "checkout.session.completed":
        user_id = obj.get("metadata", {}).get("user_id")
        if user_id:
            user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            if user:
                user.stripe_customer_id = obj.get("customer")
                user.stripe_subscription_id = obj.get("subscription")
                # Plan resolved from price on subscription.updated; default to pro here.
                user.plan = user.plan if user.plan != "free" else "pro"
        log_billing_event(kind, {"customer_id": customer, "user_id": user_id})
    elif kind == "customer.subscription.updated":
        sub_items = obj.get("items", {}).get("data", [])
        price_id = sub_items[0]["price"]["id"] if sub_items else None
        plan = settings.price_to_plan.get(price_id)
        if plan and customer:
            user = (
                await db.execute(select(User).where(User.stripe_customer_id == customer))
            ).scalar_one_or_none()
            if user:
                user.plan = plan
        log_billing_event(kind, {"customer_id": customer, "plan": plan})
    elif kind == "invoice.payment_failed":
        # IP3: Log the failure and downgrade the user's plan.
        log_billing_event(kind, {"customer_id": customer, "reason": "payment_failed"})
        if customer:
            await db.execute(
                update(User)
                .where(User.stripe_customer_id == customer)
                .values(plan="free")
            )
    elif kind == "customer.subscription.deleted":
        log_billing_event(kind, {"customer_id": customer, "reason": "subscription_deleted"})
        if customer:
            await db.execute(
                update(User)
                .where(User.stripe_customer_id == customer)
                .values(plan="free")
            )

    await db.flush()
    return {"ok": True}
