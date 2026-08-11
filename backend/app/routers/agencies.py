from fastapi import APIRouter, Depends

from .. import models
from ..deps import Ctx, get_ctx

router = APIRouter(prefix="/agency", tags=["agency"])


@router.get("/me")
def my_agency(ctx: Ctx = Depends(get_ctx)):
    agency = ctx.db.get(models.Agency, ctx.agency_id)
    return {"id": agency.id, "name": agency.name, "slug": agency.slug, "your_role": ctx.role}


@router.get("/members")
def list_members(ctx: Ctx = Depends(get_ctx)):
    """Agency staff (admins + members) — used to populate assignee pickers."""
    ctx.require(models.RoleType.agency_admin, models.RoleType.agency_member)
    rows = (
        ctx.db.query(models.Membership, models.User)
        .join(models.User, models.User.id == models.Membership.user_id)
        .filter(
            models.Membership.role.in_([models.RoleType.agency_admin, models.RoleType.agency_member]),
            models.Membership.status == models.MembershipStatus.active,
        )
        .all()
    )
    return [
        {"user_id": u.id, "name": u.name, "email": u.email, "role": m.role, "membership_id": m.id}
        for m, u in rows
    ]
