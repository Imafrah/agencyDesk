import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..deps import Ctx, get_ctx, get_plain_db
from ..security import hash_password
from ..routers.auth import _session_token

router = APIRouter(tags=["invites"])


@router.post("/invites", response_model=schemas.InviteOut)
def create_invite(payload: schemas.InviteCreate, ctx: Ctx = Depends(get_ctx)):
    """
    Idempotent by construction: a partial unique index on
    (agency_id, email, role) WHERE status='pending' means there can only
    ever be one live invite for a given email+role in this agency. Calling
    this again for the same email+role just rotates the token on the
    existing row (a "resend") instead of creating a duplicate.
    """
    ctx.require(models.RoleType.agency_admin)

    if payload.role == models.RoleType.client_user and not payload.client_id:
        raise HTTPException(status_code=400, detail="client_user invites require a client_id")
    if payload.role != models.RoleType.client_user and payload.client_id:
        raise HTTPException(status_code=400, detail="client_id only applies to client_user invites")
    if payload.client_id:
        client = (
            ctx.db.query(models.Client)
            .filter(models.Client.id == payload.client_id, models.Client.agency_id == ctx.agency_id)
            .first()
        )
        if not client:
            raise HTTPException(status_code=404, detail="Client not found in this agency")

    existing = (
        ctx.db.query(models.Invite)
        .filter(
            models.Invite.agency_id == ctx.agency_id,
            models.Invite.email == payload.email,
            models.Invite.role == payload.role,
            models.Invite.status == models.InviteStatus.pending,
        )
        .first()
    )
    if existing:
        existing.token = secrets.token_urlsafe(24)
        ctx.db.flush()
        return existing

    invite = models.Invite(
        agency_id=ctx.agency_id,
        email=payload.email,
        role=payload.role,
        client_id=payload.client_id,
        token=secrets.token_urlsafe(24),
    )
    ctx.db.add(invite)
    ctx.db.flush()
    return invite


@router.get("/invites", response_model=list[schemas.InviteOut])
def list_invites(ctx: Ctx = Depends(get_ctx)):
    ctx.require(models.RoleType.agency_admin)
    return (
        ctx.db.query(models.Invite)
        .filter(models.Invite.agency_id == ctx.agency_id)
        .order_by(models.Invite.created_at.desc())
        .all()
    )


@router.post("/invites/accept", response_model=schemas.TokenResponse)
def accept_invite(payload: schemas.InviteAccept, db: Session = Depends(get_plain_db)):
    """
    Handles the "invite race" edge case: resending never duplicated the
    invite (see create_invite above), and accepting is idempotent here too —
    if the membership already exists (e.g. the same link was submitted
    twice, or double-clicked), we just log the person in instead of erroring
    or creating a second account/membership.
    """
    invite = db.query(models.Invite).filter(models.Invite.token == payload.token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.status == models.InviteStatus.revoked:
        raise HTTPException(status_code=400, detail="This invite has been revoked")

    user = db.query(models.User).filter(models.User.email == invite.email).first()
    if not user:
        if not payload.name or not payload.password:
            raise HTTPException(status_code=400, detail="name and password required for a new account")
        user = models.User(
            email=invite.email, name=payload.name, password_hash=hash_password(payload.password)
        )
        db.add(user)
        db.flush()

    membership = (
        db.query(models.Membership)
        .filter(models.Membership.user_id == user.id, models.Membership.agency_id == invite.agency_id)
        .first()
    )
    if not membership:
        membership = models.Membership(
            user_id=user.id,
            agency_id=invite.agency_id,
            role=invite.role,
            client_id=invite.client_id,
        )
        db.add(membership)
        db.flush()
    elif membership.status == models.MembershipStatus.removed:
        membership.status = models.MembershipStatus.active

    if invite.status == models.InviteStatus.pending:
        invite.status = models.InviteStatus.accepted
        invite.accepted_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(membership)

    agency = db.get(models.Agency, invite.agency_id)
    return _session_token(membership, agency)
