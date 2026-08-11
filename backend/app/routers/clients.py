from fastapi import APIRouter, Depends, HTTPException

from .. import models, schemas
from ..deps import Ctx, get_ctx

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("", response_model=schemas.ClientOut)
def create_client(payload: schemas.ClientCreate, ctx: Ctx = Depends(get_ctx)):
    ctx.require(models.RoleType.agency_admin)
    client = models.Client(agency_id=ctx.agency_id, name=payload.name)
    ctx.db.add(client)
    ctx.db.flush()
    return client


@router.get("", response_model=list[schemas.ClientOut])
def list_clients(ctx: Ctx = Depends(get_ctx)):
    # RLS already restricts a client_user to only their own client row;
    # no extra filtering needed here.
    return ctx.db.query(models.Client).order_by(models.Client.created_at.desc()).all()


@router.get("/{client_id}", response_model=schemas.ClientOut)
def get_client(client_id: str, ctx: Ctx = Depends(get_ctx)):
    client = ctx.db.query(models.Client).filter(models.Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client
