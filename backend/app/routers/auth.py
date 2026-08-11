import uuid
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..deps import get_plain_db
from ..security import hash_password, verify_password, create_access_token, decode_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "agency"
    return base


def _session_token(membership: models.Membership, agency: models.Agency) -> schemas.TokenResponse:
    claims = {
        "sub": str(membership.user_id),
        "scope": "session",
        "agency_id": str(membership.agency_id),
        "role": membership.role.value,
        "membership_id": str(membership.id),
    }
    if membership.client_id:
        claims["client_id"] = str(membership.client_id)
    token = create_access_token(claims)
    return schemas.TokenResponse(
        access_token=token,
        role=membership.role,
        agency_id=membership.agency_id,
        agency_name=agency.name,
        client_id=membership.client_id,
    )


@router.post("/signup", response_model=schemas.TokenResponse)
def signup(payload: schemas.SignupAgency, db: Session = Depends(get_plain_db)):
    """Create a brand-new agency (tenant) with its first agency_admin."""
    existing_user = db.query(models.User).filter(models.User.email == payload.email).first()

    slug_base = _slugify(payload.agency_name)
    slug = slug_base
    i = 1
    while db.query(models.Agency).filter(models.Agency.slug == slug).first():
        i += 1
        slug = f"{slug_base}-{i}"

    agency = models.Agency(name=payload.agency_name, slug=slug)
    db.add(agency)
    db.flush()

    if existing_user:
        user = existing_user
        # allow an existing person to also found a new agency, as long as
        # they don't already have a membership there (impossible here since
        # the agency is brand new).
    else:
        user = models.User(
            email=payload.email, password_hash=hash_password(payload.password), name=payload.admin_name
        )
        db.add(user)
        db.flush()

    membership = models.Membership(
        user_id=user.id, agency_id=agency.id, role=models.RoleType.agency_admin
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return _session_token(membership, agency)


@router.post("/login", response_model=schemas.LoginResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_plain_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    memberships = (
        db.query(models.Membership)
        .filter(
            models.Membership.user_id == user.id,
            models.Membership.status == models.MembershipStatus.active,
        )
        .all()
    )
    if not memberships:
        raise HTTPException(status_code=403, detail="No active agency membership for this account")

    if len(memberships) == 1:
        m = memberships[0]
        agency = db.get(models.Agency, m.agency_id)
        return schemas.LoginResponse(access_token=_session_token(m, agency).access_token)

    pre_auth = create_access_token({"sub": str(user.id), "scope": "pre_auth"}, expire_minutes=10)
    choices = []
    for m in memberships:
        agency = db.get(models.Agency, m.agency_id)
        choices.append(schemas.MembershipChoice(agency_id=agency.id, agency_name=agency.name, role=m.role))
    return schemas.LoginResponse(pre_auth_token=pre_auth, choices=choices)


@router.post("/select-agency", response_model=schemas.TokenResponse)
def select_agency(payload: schemas.SelectAgencyRequest, db: Session = Depends(get_plain_db)):
    claims = decode_access_token(payload.pre_auth_token)
    if not claims or claims.get("scope") != "pre_auth":
        raise HTTPException(status_code=401, detail="Invalid or expired pre-auth token")

    user_id = uuid.UUID(claims["sub"])
    membership = (
        db.query(models.Membership)
        .filter(
            models.Membership.user_id == user_id,
            models.Membership.agency_id == payload.agency_id,
            models.Membership.status == models.MembershipStatus.active,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="No active membership in that agency")

    agency = db.get(models.Agency, membership.agency_id)
    return _session_token(membership, agency)
