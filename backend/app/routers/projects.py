import uuid

from fastapi import APIRouter, Depends, HTTPException

from .. import models, schemas
from ..deps import Ctx, get_ctx
from ..access import assert_visible_project

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=schemas.ProjectOut)
def create_project(payload: schemas.ProjectCreate, ctx: Ctx = Depends(get_ctx)):
    ctx.require(models.RoleType.agency_admin)
    # RLS on `clients` already scopes this lookup to the current agency.
    client = ctx.db.query(models.Client).filter(models.Client.id == payload.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found in this agency")
    project = models.Project(
        agency_id=ctx.agency_id,
        client_id=payload.client_id,
        name=payload.name,
        description=payload.description,
    )
    ctx.db.add(project)
    ctx.db.flush()
    return project


@router.get("", response_model=list[schemas.ProjectOut])
def list_projects(ctx: Ctx = Depends(get_ctx)):
    q = ctx.db.query(models.Project)
    if ctx.role == models.RoleType.agency_member:
        assigned_ids = [
            r.project_id
            for r in ctx.db.query(models.ProjectAssignment).filter(
                models.ProjectAssignment.user_id == ctx.user_id
            )
        ]
        q = q.filter(models.Project.id.in_(assigned_ids or [uuid.uuid4()]))
    # agency_admin sees all agency projects; client_user is already scoped by RLS.
    return q.order_by(models.Project.created_at.desc()).all()


@router.get("/{project_id}", response_model=schemas.ProjectOut)
def get_project(project_id: str, ctx: Ctx = Depends(get_ctx)):
    project = ctx.db.query(models.Project).filter(models.Project.id == project_id).first()
    assert_visible_project(ctx, project)
    return project


@router.post("/{project_id}/assignments")
def assign_member(project_id: str, payload: schemas.ProjectAssignmentCreate, ctx: Ctx = Depends(get_ctx)):
    ctx.require(models.RoleType.agency_admin)
    project = ctx.db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    member = (
        ctx.db.query(models.Membership)
        .filter(
            models.Membership.user_id == payload.user_id,
            models.Membership.agency_id == ctx.agency_id,
            models.Membership.role.in_([models.RoleType.agency_admin, models.RoleType.agency_member]),
            models.Membership.status == models.MembershipStatus.active,
        )
        .first()
    )
    if not member:
        raise HTTPException(status_code=400, detail="User is not active agency staff")

    exists = (
        ctx.db.query(models.ProjectAssignment)
        .filter(
            models.ProjectAssignment.project_id == project_id,
            models.ProjectAssignment.user_id == payload.user_id,
        )
        .first()
    )
    if exists:
        return {"status": "already assigned"}

    ctx.db.add(
        models.ProjectAssignment(project_id=project.id, agency_id=ctx.agency_id, user_id=payload.user_id)
    )
    return {"status": "assigned"}


@router.get("/{project_id}/assignments")
def list_assignments(project_id: str, ctx: Ctx = Depends(get_ctx)):
    ctx.require(models.RoleType.agency_admin, models.RoleType.agency_member)
    rows = (
        ctx.db.query(models.ProjectAssignment, models.User)
        .join(models.User, models.User.id == models.ProjectAssignment.user_id)
        .filter(models.ProjectAssignment.project_id == project_id)
        .all()
    )
    return [{"user_id": u.id, "name": u.name, "email": u.email} for _, u in rows]


@router.delete("/{project_id}/assignments/{user_id}")
def remove_member(project_id: str, user_id: str, ctx: Ctx = Depends(get_ctx)):
    """
    Removing an agency_member from a project (edge case: 'removing a team
    member mid-task'). Decision: their in-flight tasks on this project are
    unassigned (assignee cleared, status untouched) rather than deleted or
    silently left pointing at someone who can no longer act on them — the
    work stays visible on the board and the admin can see exactly which
    tasks now need a new owner. The assignment row itself is removed so the
    old assignee stops seeing the project via `agency_member` scoping.
    """
    ctx.require(models.RoleType.agency_admin)
    assignment = (
        ctx.db.query(models.ProjectAssignment)
        .filter(
            models.ProjectAssignment.project_id == project_id,
            models.ProjectAssignment.user_id == user_id,
        )
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    orphaned = (
        ctx.db.query(models.Task)
        .filter(
            models.Task.project_id == project_id,
            models.Task.assignee_id == user_id,
            models.Task.status != models.TaskStatus.done,
        )
        .all()
    )
    orphaned_ids = [str(t.id) for t in orphaned]
    for t in orphaned:
        t.assignee_id = None

    ctx.db.delete(assignment)
    return {"status": "removed", "unassigned_task_ids": orphaned_ids}
