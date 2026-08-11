"""
Idempotent seed data for local dev / grading.

Creates two agencies, staff, a client contact who is a client_user in one
agency AND an agency_member in the other (the "one person, two agencies"
edge case), and a mix of internal / client-visible tasks, comments, a file,
and a time entry — enough to exercise every isolation rule by hand or via
tests/test_isolation.py.

Safe to run repeatedly: it checks for the first agency's slug and exits
early if the data already exists.
"""
import datetime
from sqlalchemy import text

from app.database import SessionLocal
from app import models
from app.security import hash_password

db = SessionLocal()


def set_ctx(agency_id, role="agency_admin", client_id=None):
    db.execute(text("SET LOCAL app.current_agency_id = :v"), {"v": str(agency_id)})
    db.execute(text("SET LOCAL app.session_role = :v"), {"v": role})
    db.execute(
        text("SET LOCAL app.current_client_id = :v"),
        {"v": str(client_id) if client_id else "00000000-0000-0000-0000-000000000000"},
    )
    db.execute(text("SET LOCAL app.current_user_id = :v"), {"v": "00000000-0000-0000-0000-000000000000"})


def get_or_create_user(email, name):
    user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        return user
    user = models.User(email=email, name=name, password_hash=hash_password("password123"))
    db.add(user)
    db.flush()
    return user


def main():
    if db.query(models.Agency).filter(models.Agency.slug == "pixel-co").first():
        print("Seed data already present — skipping.")
        return

    # ── identity (no RLS on users/memberships) ─────────────────────────
    pixel = models.Agency(name="Pixel & Co", slug="pixel-co")
    loop = models.Agency(name="Studio Loop", slug="studio-loop")
    db.add_all([pixel, loop])
    db.flush()

    ava = get_or_create_user("admin@pixelco.test", "Ava Admin")
    milo = get_or_create_user("member@pixelco.test", "Milo Member")
    nora = get_or_create_user("client@northwind.test", "Nora Client")
    sam = get_or_create_user("admin@studioloop.test", "Sam Studio")
    # Jordan: agency_member at Pixel & Co, AND client_user at Studio Loop —
    # the "same email, two agencies, two different roles" edge case.
    jordan = get_or_create_user("jordan@freelance.test", "Jordan Freelance")

    db.add(models.Membership(user_id=ava.id, agency_id=pixel.id, role=models.RoleType.agency_admin))
    db.add(models.Membership(user_id=milo.id, agency_id=pixel.id, role=models.RoleType.agency_member))
    db.add(models.Membership(user_id=jordan.id, agency_id=pixel.id, role=models.RoleType.agency_member))
    db.add(models.Membership(user_id=sam.id, agency_id=loop.id, role=models.RoleType.agency_admin))
    db.flush()

    # ── Pixel & Co tenant data ──────────────────────────────────────────
    set_ctx(pixel.id, role="agency_admin")

    northwind = models.Client(agency_id=pixel.id, name="Northwind Traders")
    db.add(northwind)
    db.flush()

    db.add(
        models.Membership(
            user_id=nora.id, agency_id=pixel.id, role=models.RoleType.client_user, client_id=northwind.id
        )
    )
    db.flush()

    project1 = models.Project(
        agency_id=pixel.id,
        client_id=northwind.id,
        name="Northwind Rebrand",
        description="Full brand refresh: logo, site, style guide.",
    )
    db.add(project1)
    db.flush()

    db.add_all(
        [
            models.ProjectAssignment(project_id=project1.id, agency_id=pixel.id, user_id=milo.id),
            models.ProjectAssignment(project_id=project1.id, agency_id=pixel.id, user_id=jordan.id),
        ]
    )
    db.flush()

    t_internal = models.Task(
        agency_id=pixel.id,
        project_id=project1.id,
        title="Internal budget review",
        description="Confirm hours against SOW before we quote extra work.",
        status=models.TaskStatus.todo,
        priority=models.TaskPriority.medium,
        assignee_id=ava.id,
        visibility=models.VisibilityType.internal,
    )
    t_logo = models.Task(
        agency_id=pixel.id,
        project_id=project1.id,
        title="Logo concepts",
        description="Three initial directions for review.",
        status=models.TaskStatus.in_progress,
        priority=models.TaskPriority.high,
        assignee_id=milo.id,
        visibility=models.VisibilityType.client_visible,
    )
    t_wire = models.Task(
        agency_id=pixel.id,
        project_id=project1.id,
        title="Homepage wireframe",
        status=models.TaskStatus.in_review,
        priority=models.TaskPriority.medium,
        assignee_id=jordan.id,
        visibility=models.VisibilityType.client_visible,
    )
    db.add_all([t_internal, t_logo, t_wire])
    db.flush()

    db.add_all(
        [
            models.Comment(
                agency_id=pixel.id,
                task_id=t_logo.id,
                author_id=milo.id,
                body="Uploaded three directions — let us know which resonates.",
                visibility=models.VisibilityType.client_visible,
            ),
            models.Comment(
                agency_id=pixel.id,
                task_id=t_logo.id,
                author_id=ava.id,
                body="Heads up: direction 2 reuses a font we're not licensed for, swap before sending.",
                visibility=models.VisibilityType.internal,
            ),
            models.TimeEntry(
                agency_id=pixel.id,
                task_id=t_logo.id,
                user_id=milo.id,
                duration_minutes=180,
                note="Initial concepts",
                entry_date=datetime.date.today(),
            ),
            models.FileAsset(
                agency_id=pixel.id,
                task_id=t_logo.id,
                uploaded_by=milo.id,
                filename="logo-concepts-v1.pdf",
                storage_path="/dev/null",
                visibility=models.VisibilityType.client_visible,
                approval_status=models.ApprovalStatus.pending,
            ),
        ]
    )
    db.commit()

    # ── Studio Loop tenant data (separate tenant, must never see Pixel data)
    set_ctx(loop.id, role="agency_admin")

    acme = models.Client(agency_id=loop.id, name="Acme Corp")
    db.add(acme)
    db.flush()

    db.add(
        models.Membership(
            user_id=jordan.id, agency_id=loop.id, role=models.RoleType.client_user, client_id=acme.id
        )
    )
    db.flush()

    project2 = models.Project(agency_id=loop.id, client_id=acme.id, name="Acme Launch Site")
    db.add(project2)
    db.flush()

    db.add(
        models.Task(
            agency_id=loop.id,
            project_id=project2.id,
            title="Draft homepage copy",
            status=models.TaskStatus.todo,
            priority=models.TaskPriority.medium,
            assignee_id=sam.id,
            visibility=models.VisibilityType.client_visible,
        )
    )
    db.commit()

    print("Seeded:")
    print("  Pixel & Co  — admin: admin@pixelco.test / password123")
    print("               member: member@pixelco.test / password123")
    print("               client (Northwind): client@northwind.test / password123")
    print("  Studio Loop — admin: admin@studioloop.test / password123")
    print("  Jordan Freelance — jordan@freelance.test / password123")
    print("               agency_member at Pixel & Co, client_user (Acme) at Studio Loop")


if __name__ == "__main__":
    main()
