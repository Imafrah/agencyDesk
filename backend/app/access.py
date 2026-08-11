from fastapi import HTTPException

from . import models
from .deps import Ctx


def assert_visible_project(ctx: Ctx, project: models.Project | None) -> models.Project:
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if ctx.role == models.RoleType.agency_member and not is_assigned(ctx, project.id):
        raise HTTPException(status_code=403, detail="Not assigned to this project")
    return project


def is_assigned(ctx: Ctx, project_id) -> bool:
    return (
        ctx.db.query(models.ProjectAssignment)
        .filter(
            models.ProjectAssignment.project_id == project_id,
            models.ProjectAssignment.user_id == ctx.user_id,
        )
        .first()
        is not None
    )


def get_task_or_404(ctx: Ctx, task_id) -> models.Task:
    task = ctx.db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        # Either it doesn't exist, belongs to another tenant, or RLS hid it
        # from a client because it's internal-only — all three should look
        # identical from the outside, which is the point.
        raise HTTPException(status_code=404, detail="Task not found")
    if ctx.role == models.RoleType.agency_member:
        project = ctx.db.query(models.Project).filter(models.Project.id == task.project_id).first()
        if not project or not is_assigned(ctx, project.id):
            raise HTTPException(status_code=404, detail="Task not found")
    return task
