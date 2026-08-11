import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FileParam
from fastapi.responses import FileResponse

from .. import models, schemas
from ..deps import Ctx, get_ctx
from ..access import assert_visible_project, get_task_or_404
from ..config import settings

router = APIRouter(tags=["tasks"])


def _assert_assignee_valid(ctx: Ctx, project: models.Project, assignee_id):
    if assignee_id is None:
        return
    membership = (
        ctx.db.query(models.Membership)
        .filter(
            models.Membership.user_id == assignee_id,
            models.Membership.agency_id == ctx.agency_id,
            models.Membership.role.in_([models.RoleType.agency_admin, models.RoleType.agency_member]),
            models.Membership.status == models.MembershipStatus.active,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=400, detail="Assignee must be active agency staff")
    if membership.role == models.RoleType.agency_member:
        assigned = (
            ctx.db.query(models.ProjectAssignment)
            .filter(
                models.ProjectAssignment.project_id == project.id,
                models.ProjectAssignment.user_id == assignee_id,
            )
            .first()
        )
        if not assigned:
            raise HTTPException(status_code=400, detail="Assignee is not assigned to this project")


# ── tasks ────────────────────────────────────────────────────────────────
@router.post("/projects/{project_id}/tasks", response_model=schemas.TaskOut)
def create_task(project_id: str, payload: schemas.TaskCreate, ctx: Ctx = Depends(get_ctx)):
    ctx.require(models.RoleType.agency_admin, models.RoleType.agency_member)
    project = ctx.db.query(models.Project).filter(models.Project.id == project_id).first()
    assert_visible_project(ctx, project)
    _assert_assignee_valid(ctx, project, payload.assignee_id)

    task = models.Task(
        agency_id=ctx.agency_id,
        project_id=project.id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        assignee_id=payload.assignee_id,
        due_date=payload.due_date,
        visibility=payload.visibility,
    )
    ctx.db.add(task)
    ctx.db.flush()
    return task


@router.get("/projects/{project_id}/tasks", response_model=list[schemas.TaskOut])
def list_tasks(project_id: str, ctx: Ctx = Depends(get_ctx)):
    project = ctx.db.query(models.Project).filter(models.Project.id == project_id).first()
    assert_visible_project(ctx, project)
    # RLS already drops internal tasks for client_user; nothing extra needed.
    return (
        ctx.db.query(models.Task)
        .filter(models.Task.project_id == project_id)
        .order_by(models.Task.created_at.desc())
        .all()
    )


@router.get("/tasks/{task_id}", response_model=schemas.TaskOut)
def get_task(task_id: str, ctx: Ctx = Depends(get_ctx)):
    return get_task_or_404(ctx, task_id)


@router.patch("/tasks/{task_id}", response_model=schemas.TaskOut)
def update_task(task_id: str, payload: schemas.TaskUpdate, ctx: Ctx = Depends(get_ctx)):
    # Clients "cannot create tasks or change status" — blocked outright here,
    # not just at the status field, since editing anything on a task they
    # can see is staff-only.
    ctx.require(models.RoleType.agency_admin, models.RoleType.agency_member)
    task = get_task_or_404(ctx, task_id)
    project = ctx.db.query(models.Project).filter(models.Project.id == task.project_id).first()

    data = payload.model_dump(exclude_unset=True)
    if "assignee_id" in data:
        _assert_assignee_valid(ctx, project, data["assignee_id"])
    for field, value in data.items():
        setattr(task, field, value)
    ctx.db.flush()
    return task


# ── comments ─────────────────────────────────────────────────────────────
@router.post("/tasks/{task_id}/comments", response_model=schemas.CommentOut)
def add_comment(task_id: str, payload: schemas.CommentCreate, ctx: Ctx = Depends(get_ctx)):
    task = get_task_or_404(ctx, task_id)
    visibility = payload.visibility
    if ctx.role == models.RoleType.client_user:
        # A client can only ever post client-visible comments on a
        # client-visible task — enforced here AND by the RLS WITH CHECK
        # clause on `comments`, so a bug here still can't leak an internal
        # comment through.
        if task.visibility != models.VisibilityType.client_visible:
            raise HTTPException(status_code=403, detail="Cannot comment on an internal task")
        visibility = models.VisibilityType.client_visible

    comment = models.Comment(
        agency_id=ctx.agency_id,
        task_id=task.id,
        author_id=ctx.user_id,
        body=payload.body,
        visibility=visibility,
    )
    ctx.db.add(comment)
    ctx.db.flush()
    return comment


@router.get("/tasks/{task_id}/comments", response_model=list[schemas.CommentOut])
def list_comments(task_id: str, ctx: Ctx = Depends(get_ctx)):
    get_task_or_404(ctx, task_id)
    return (
        ctx.db.query(models.Comment)
        .filter(models.Comment.task_id == task_id)
        .order_by(models.Comment.created_at.asc())
        .all()
    )


# ── files ────────────────────────────────────────────────────────────────
@router.post("/tasks/{task_id}/files", response_model=schemas.FileOut)
def upload_file(
    task_id: str,
    visibility: models.VisibilityType = models.VisibilityType.internal,
    upload: UploadFile = FileParam(...),
    ctx: Ctx = Depends(get_ctx),
):
    ctx.require(models.RoleType.agency_admin, models.RoleType.agency_member)
    task = get_task_or_404(ctx, task_id)

    task_dir = os.path.join(settings.upload_dir, str(ctx.agency_id), str(task.id))
    os.makedirs(task_dir, exist_ok=True)
    stored_name = f"{uuid.uuid4()}_{upload.filename}"
    dest = os.path.join(task_dir, stored_name)
    with open(dest, "wb") as f:
        f.write(upload.file.read())

    file_row = models.FileAsset(
        agency_id=ctx.agency_id,
        task_id=task.id,
        uploaded_by=ctx.user_id,
        filename=upload.filename,
        storage_path=dest,
        visibility=visibility,
    )
    ctx.db.add(file_row)
    ctx.db.flush()
    return file_row


@router.get("/tasks/{task_id}/files", response_model=list[schemas.FileOut])
def list_files(task_id: str, ctx: Ctx = Depends(get_ctx)):
    get_task_or_404(ctx, task_id)
    return (
        ctx.db.query(models.FileAsset)
        .filter(models.FileAsset.task_id == task_id)
        .order_by(models.FileAsset.created_at.desc())
        .all()
    )


@router.get("/files/{file_id}/download")
def download_file(file_id: str, ctx: Ctx = Depends(get_ctx)):
    # RLS on `files` already refuses to return the row at all if this file
    # is internal-only and the caller is a client_user — no separate check
    # needed, the query result being empty *is* the access check.
    file_row = ctx.db.query(models.FileAsset).filter(models.FileAsset.id == file_id).first()
    if not file_row:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_row.storage_path, filename=file_row.filename)


@router.patch("/files/{file_id}/approval", response_model=schemas.FileOut)
def set_file_approval(file_id: str, payload: schemas.FileApprovalUpdate, ctx: Ctx = Depends(get_ctx)):
    ctx.require(models.RoleType.client_user)
    file_row = ctx.db.query(models.FileAsset).filter(models.FileAsset.id == file_id).first()
    if not file_row:
        raise HTTPException(status_code=404, detail="File not found")
    file_row.approval_status = payload.approval_status
    ctx.db.flush()
    return file_row


# ── time entries (agency staff only — never exposed to clients) ───────────
@router.post("/tasks/{task_id}/time-entries", response_model=schemas.TimeEntryOut)
def log_time(task_id: str, payload: schemas.TimeEntryCreate, ctx: Ctx = Depends(get_ctx)):
    ctx.require(models.RoleType.agency_admin, models.RoleType.agency_member)
    task = get_task_or_404(ctx, task_id)
    entry = models.TimeEntry(
        agency_id=ctx.agency_id,
        task_id=task.id,
        user_id=ctx.user_id,
        duration_minutes=payload.duration_minutes,
        note=payload.note,
        entry_date=payload.entry_date,
    )
    ctx.db.add(entry)
    ctx.db.flush()
    return entry


@router.get("/tasks/{task_id}/time-entries", response_model=list[schemas.TimeEntryOut])
def list_time_entries(task_id: str, ctx: Ctx = Depends(get_ctx)):
    ctx.require(models.RoleType.agency_admin, models.RoleType.agency_member)
    get_task_or_404(ctx, task_id)
    return (
        ctx.db.query(models.TimeEntry)
        .filter(models.TimeEntry.task_id == task_id)
        .order_by(models.TimeEntry.entry_date.desc())
        .all()
    )
