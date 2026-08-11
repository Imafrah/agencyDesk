import uuid
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Header
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import SessionLocal
from .security import decode_access_token
from .models import RoleType

NIL_UUID = "00000000-0000-0000-0000-000000000000"


def _get_claims(authorization: Optional[str] = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1]
    claims = decode_access_token(token)
    if not claims or claims.get("scope") != "session":
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return claims


@dataclass
class Ctx:
    db: Session
    user_id: uuid.UUID
    agency_id: uuid.UUID
    role: RoleType
    client_id: Optional[uuid.UUID]
    membership_id: uuid.UUID

    def require(self, *roles: RoleType):
        if self.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role for this action")


def get_ctx(claims: dict = Depends(_get_claims)):
    """
    Opens a DB session and sets the RLS session variables that the
    migration's policies key off of, scoped to *this request's transaction*
    via SET LOCAL. Every query issued through `ctx.db` for the rest of the
    request is filtered by Postgres itself, not just by application code.
    """
    db = SessionLocal()
    try:
        db.execute(text("SET LOCAL app.current_user_id = :v"), {"v": claims["sub"]})
        db.execute(text("SET LOCAL app.current_agency_id = :v"), {"v": claims["agency_id"]})
        db.execute(text("SET LOCAL app.session_role = :v"), {"v": claims["role"]})
        db.execute(
            text("SET LOCAL app.current_client_id = :v"),
            {"v": claims.get("client_id") or NIL_UUID},
        )
        ctx = Ctx(
            db=db,
            user_id=uuid.UUID(claims["sub"]),
            agency_id=uuid.UUID(claims["agency_id"]),
            role=RoleType(claims["role"]),
            client_id=uuid.UUID(claims["client_id"]) if claims.get("client_id") else None,
            membership_id=uuid.UUID(claims["membership_id"]),
        )
        yield ctx
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_plain_db():
    """Unscoped session for pre-auth flows (login, signup, invite accept)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
