"""Multi-tenant organizations — for coaching institutes."""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.org_member import OrgMember
from app.models.organization import Organization
from app.models.student_session import StudentSession
from app.models.user import User
from app.models.user_stats import UserStats
from app.services.email import send_invitation_email

router = APIRouter(prefix="/organizations", tags=["organizations"])

_SLUG = re.compile(r"^[a-z0-9-]+$")


class OrgCreate(BaseModel):
    name: str
    slug: str


class InviteRequest(BaseModel):
    email: str
    role: str = "student"


async def _require_admin(db: AsyncSession, org_id: str, user: User) -> Organization:
    org = (
        await db.execute(select(Organization).where(Organization.id == org_id))
    ).scalar_one_or_none()
    if not org:
        raise HTTPException(404, "Organization not found")
    member = (
        await db.execute(
            select(OrgMember).where(OrgMember.org_id == org.id, OrgMember.user_id == user.id)
        )
    ).scalar_one_or_none()
    if not member or member.role != "admin":
        raise HTTPException(403, "Admin access required")
    return org


@router.post("")
async def create_org(
    payload: OrgCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not _SLUG.match(payload.slug):
        raise HTTPException(400, "Slug must be lowercase alphanumeric + hyphens")
    org = Organization(name=payload.name, slug=payload.slug, owner_id=user.id, plan="institution")
    db.add(org)
    await db.flush()
    db.add(OrgMember(org_id=org.id, user_id=user.id, role="admin"))
    await db.flush()
    return {"id": str(org.id), "slug": org.slug, "name": org.name}


@router.get("/{slug}")
async def get_org(
    slug: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org = (
        await db.execute(select(Organization).where(Organization.slug == slug))
    ).scalar_one_or_none()
    if not org:
        raise HTTPException(404, "Organization not found")
    members = (
        await db.execute(select(func.count()).select_from(OrgMember).where(OrgMember.org_id == org.id))
    ).scalar_one()
    return {"id": str(org.id), "name": org.name, "slug": org.slug, "members": members}


@router.post("/{org_id}/members/invite")
async def invite_member(
    org_id: str,
    payload: InviteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org = await _require_admin(db, org_id, user)
    from app.config import settings

    invite_url = f"{settings.APP_URL}/join/{org.slug}"
    await send_invitation_email(payload.email, user.full_name, org.name, payload.role, invite_url)
    return {"success": True, "invited": payload.email}


@router.get("/{org_id}/members")
async def list_members(
    org_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    await _require_admin(db, org_id, user)
    rows = (
        (await db.execute(
            select(OrgMember, User).join(User, OrgMember.user_id == User.id).where(OrgMember.org_id == org_id)
        )).all()
    )
    return [
        {"user_id": str(u.id), "name": u.full_name, "email": u.email, "role": m.role}
        for m, u in rows
    ]


@router.get("/{org_id}/leaderboard")
async def leaderboard(
    org_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    await _require_admin(db, org_id, user)
    rows = (
        (await db.execute(
            select(User.full_name, UserStats)
            .join(OrgMember, OrgMember.user_id == User.id)
            .join(UserStats, UserStats.user_id == User.id)
            .where(OrgMember.org_id == org_id)
            .order_by(UserStats.xp_total.desc())
            .limit(10)
        )).all()
    )
    return [
        {"name": name, "xp": s.xp_total, "level": s.level, "streak": s.streak_days}
        for name, s in rows
    ]
