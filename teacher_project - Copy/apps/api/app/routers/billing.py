"""Billing — checkout, portal, and current plan/usage status."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.billing import (
    BillingStatusResponse,
    CheckoutRequest,
    CheckoutResponse,
    PortalResponse,
)
from app.services import billing

router = APIRouter(prefix="/billing", tags=["billing"])

_PRICE = {
    "pro": settings.STRIPE_PRO_PRICE_ID,
    "creator": settings.STRIPE_CREATOR_PRICE_ID,
    "institution": settings.STRIPE_INSTITUTION_PRICE_ID,
}


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    payload: CheckoutRequest,
    user: User = Depends(get_current_user),
) -> CheckoutResponse:
    url = await billing.create_checkout_session(
        user,
        _PRICE.get(payload.plan, ""),
        success_url=f"{settings.APP_URL}/dashboard?upgraded=1",
        cancel_url=f"{settings.APP_URL}/pricing",
    )
    return CheckoutResponse(checkout_url=url)


@router.post("/portal", response_model=PortalResponse)
async def portal(user: User = Depends(get_current_user)) -> PortalResponse:
    url = await billing.create_portal_session(user, return_url=f"{settings.APP_URL}/settings/account")
    return PortalResponse(portal_url=url)


@router.get("/status", response_model=BillingStatusResponse)
async def status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BillingStatusResponse:
    return BillingStatusResponse(
        plan=user.plan,
        limits=billing.get_plan_limits(user.plan),
        usage=await billing.current_usage(db, user.id),
    )
