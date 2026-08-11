from fastapi import APIRouter, Depends
from sqlalchemy import func

from .. import models, schemas
from ..deps import Ctx, get_ctx
from ..access import assert_visible_project

router = APIRouter(tags=["dashboard"])


@router.get("/projects/{project_id}/dashboard", response_model=schemas.ProjectDashboard)
def project_dashboard(project_id: str, ctx: Ctx = Depends(get_ctx)):
    project = ctx.db.query(models.Project).filter(models.Project.id == project_id).first()
    assert_visible_project(ctx, project)

    # RLS already restricts which task rows a client_user can see (only
    # client_visible tasks on their own project) and hides time_entries from
    # clients entirely, so this query needs no extra role branching.
    counts_rows = (
        ctx.db.query(models.Task.status, func.count(models.Task.id))
        .filter(models.Task.project_id == project_id)
        .group_by(models.Task.status)
        .all()
    )
    counts = {status.value: count for status, count in counts_rows}
    for s in models.TaskStatus:
        counts.setdefault(s.value, 0)

    total_minutes = (
        ctx.db.query(func.coalesce(func.sum(models.TimeEntry.duration_minutes), 0))
        .filter(models.TimeEntry.task_id.in_(ctx.db.query(models.Task.id).filter(models.Task.project_id == project_id)))
        .scalar()
    )

    return schemas.ProjectDashboard(
        project_id=project_id,
        task_counts_by_status=counts,
        total_hours_logged=round((total_minutes or 0) / 60, 2),
    )
