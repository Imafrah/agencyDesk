"""initial schema: multi-tenant AgencyDesk core tables + RLS

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-11

"""
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


UPGRADE_SQL = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE TYPE role_type AS ENUM ('agency_admin','agency_member','client_user');
CREATE TYPE membership_status AS ENUM ('active','removed');
CREATE TYPE visibility_type AS ENUM ('internal','client_visible');
CREATE TYPE task_status AS ENUM ('todo','in_progress','in_review','done');
CREATE TYPE task_priority AS ENUM ('low','medium','high','urgent');
CREATE TYPE approval_status_type AS ENUM ('pending','approved','needs_changes');
CREATE TYPE invite_status AS ENUM ('pending','accepted','revoked');

-- ── agencies: the tenant itself ────────────────────────────────────────────
CREATE TABLE agencies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── users: GLOBAL identity, never tenant-scoped. One row per email no matter
-- how many agencies the person is involved with. Tenant + role live on
-- `memberships`, not here — this is what lets one email be agency_admin at
-- Agency A and client_user at Agency B without any duplication or hacks.
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email CITEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── clients: an agency's own clients ────────────────────────────────────────
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agency_id UUID NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (id, agency_id)
);
CREATE INDEX idx_clients_agency ON clients(agency_id);

-- ── memberships: (user, agency) -> role. This is the tenant join table.
-- A user has at most one role per agency. client_user rows must point at a
-- client *within that same agency* (enforced by the composite FK below, not
-- just app code) — a client contact can never be wired to another agency's
-- client record even by mistake.
CREATE TABLE memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agency_id UUID NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    role role_type NOT NULL,
    client_id UUID,
    status membership_status NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, agency_id),
    UNIQUE (id, agency_id),
    FOREIGN KEY (client_id, agency_id) REFERENCES clients(id, agency_id),
    CONSTRAINT client_role_consistency CHECK (
        (role = 'client_user' AND client_id IS NOT NULL) OR
        (role <> 'client_user' AND client_id IS NULL)
    )
);
CREATE INDEX idx_memberships_agency ON memberships(agency_id);
CREATE INDEX idx_memberships_user ON memberships(user_id);

-- ── projects: belongs to a client, which must belong to the same agency.
-- The composite FK (client_id, agency_id) -> clients(id, agency_id) makes
-- "project.agency_id disagrees with project.client.agency_id" a constraint
-- violation, not just a bug to catch in code review.
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agency_id UUID NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    client_id UUID NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (id, agency_id),
    FOREIGN KEY (client_id, agency_id) REFERENCES clients(id, agency_id)
);
CREATE INDEX idx_projects_agency ON projects(agency_id);
CREATE INDEX idx_projects_client ON projects(client_id);

-- ── project_assignments: which agency_members can act on a project.
-- agency_member visibility ("assigned projects only") is derived from this.
CREATE TABLE project_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL,
    agency_id UUID NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, user_id),
    FOREIGN KEY (project_id, agency_id) REFERENCES projects(id, agency_id) ON DELETE CASCADE
);
CREATE INDEX idx_pa_agency ON project_assignments(agency_id);
CREATE INDEX idx_pa_project ON project_assignments(project_id);
CREATE INDEX idx_pa_user ON project_assignments(user_id);

-- ── tasks: same composite-FK trick ties every task to a project in the SAME
-- tenant. assignee_id references the global users table; the app layer
-- checks the assignee has an active staff membership in this agency (a
-- cross-agency FK can't express "same tenant" for a global users table).
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agency_id UUID NOT NULL,
    project_id UUID NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    status task_status NOT NULL DEFAULT 'todo',
    priority task_priority NOT NULL DEFAULT 'medium',
    assignee_id UUID REFERENCES users(id) ON DELETE SET NULL,
    due_date DATE,
    visibility visibility_type NOT NULL DEFAULT 'internal',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (id, agency_id),
    FOREIGN KEY (project_id, agency_id) REFERENCES projects(id, agency_id) ON DELETE CASCADE
);
CREATE INDEX idx_tasks_agency ON tasks(agency_id);
CREATE INDEX idx_tasks_project ON tasks(project_id);
CREATE INDEX idx_tasks_assignee ON tasks(assignee_id);

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_tasks_updated_at BEFORE UPDATE ON tasks
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ── comments: visibility flag lives directly on the row (not inherited),
-- so a client-visible task can still carry internal-only comments.
CREATE TABLE comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agency_id UUID NOT NULL,
    task_id UUID NOT NULL,
    author_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    visibility visibility_type NOT NULL DEFAULT 'internal',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (task_id, agency_id) REFERENCES tasks(id, agency_id) ON DELETE CASCADE
);
CREATE INDEX idx_comments_agency ON comments(agency_id);
CREATE INDEX idx_comments_task ON comments(task_id);

-- ── files ────────────────────────────────────────────────────────────────
CREATE TABLE files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agency_id UUID NOT NULL,
    task_id UUID NOT NULL,
    uploaded_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    visibility visibility_type NOT NULL DEFAULT 'internal',
    approval_status approval_status_type NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (task_id, agency_id) REFERENCES tasks(id, agency_id) ON DELETE CASCADE
);
CREATE INDEX idx_files_agency ON files(agency_id);
CREATE INDEX idx_files_task ON files(task_id);

-- ── time_entries: agency-staff only, never exposed to clients ─────────────
CREATE TABLE time_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agency_id UUID NOT NULL,
    task_id UUID NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
    note TEXT,
    entry_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (task_id, agency_id) REFERENCES tasks(id, agency_id) ON DELETE CASCADE
);
CREATE INDEX idx_time_agency ON time_entries(agency_id);
CREATE INDEX idx_time_task ON time_entries(task_id);

-- ── invites: idempotent by design. A partial unique index means only ONE
-- pending invite can exist per (agency, email, role) — resending updates
-- that row's token instead of inserting a duplicate, and accepting flips
-- status to 'accepted' so a second accept has nothing pending to act on.
CREATE TABLE invites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agency_id UUID NOT NULL REFERENCES agencies(id) ON DELETE CASCADE,
    email CITEXT NOT NULL,
    role role_type NOT NULL,
    client_id UUID,
    token TEXT NOT NULL UNIQUE,
    status invite_status NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    accepted_at TIMESTAMPTZ,
    FOREIGN KEY (client_id, agency_id) REFERENCES clients(id, agency_id),
    CONSTRAINT invite_client_role_consistency CHECK (
        (role = 'client_user' AND client_id IS NOT NULL) OR
        (role <> 'client_user' AND client_id IS NULL)
    )
);
CREATE INDEX idx_invites_agency ON invites(agency_id);
CREATE UNIQUE INDEX uq_invites_pending ON invites(agency_id, email, role) WHERE status = 'pending';

-- ═══════════════════════════════════════════════════════════════════════
-- Row-Level Security: DB-enforced tenant isolation, independent of the app.
-- Every request sets three session-local settings (see app/deps.py):
--   app.current_agency_id, app.session_role, app.current_client_id
-- Even a bug that forgets a WHERE agency_id=... clause cannot leak rows,
-- because Postgres itself filters them out. FORCE ROW LEVEL SECURITY means
-- this applies even to the table owner / migration role.
-- ═══════════════════════════════════════════════════════════════════════

ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE clients FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON clients
  USING (
    agency_id = current_setting('app.current_agency_id', true)::uuid
    AND (
      current_setting('app.session_role', true) <> 'client_user'
      OR id = current_setting('app.current_client_id', true)::uuid
    )
  );

ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON projects
  USING (
    agency_id = current_setting('app.current_agency_id', true)::uuid
    AND (
      current_setting('app.session_role', true) <> 'client_user'
      OR client_id = current_setting('app.current_client_id', true)::uuid
    )
  );

ALTER TABLE project_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_assignments FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON project_assignments
  USING (
    agency_id = current_setting('app.current_agency_id', true)::uuid
    AND current_setting('app.session_role', true) <> 'client_user'
  );

ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON tasks
  USING (
    agency_id = current_setting('app.current_agency_id', true)::uuid
    AND (
      current_setting('app.session_role', true) <> 'client_user'
      OR (
        visibility = 'client_visible'
        AND project_id IN (
          SELECT id FROM projects WHERE client_id = current_setting('app.current_client_id', true)::uuid
        )
      )
    )
  );

ALTER TABLE comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE comments FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON comments
  USING (
    agency_id = current_setting('app.current_agency_id', true)::uuid
    AND (
      current_setting('app.session_role', true) <> 'client_user'
      OR (
        visibility = 'client_visible'
        AND task_id IN (
          SELECT t.id FROM tasks t JOIN projects p ON p.id = t.project_id
          WHERE p.client_id = current_setting('app.current_client_id', true)::uuid
        )
      )
    )
  );

ALTER TABLE files ENABLE ROW LEVEL SECURITY;
ALTER TABLE files FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON files
  USING (
    agency_id = current_setting('app.current_agency_id', true)::uuid
    AND (
      current_setting('app.session_role', true) <> 'client_user'
      OR (
        visibility = 'client_visible'
        AND task_id IN (
          SELECT t.id FROM tasks t JOIN projects p ON p.id = t.project_id
          WHERE p.client_id = current_setting('app.current_client_id', true)::uuid
        )
      )
    )
  );

ALTER TABLE time_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE time_entries FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON time_entries
  USING (
    agency_id = current_setting('app.current_agency_id', true)::uuid
    AND current_setting('app.session_role', true) <> 'client_user'
  );

-- NOTE: `invites` and `memberships` are intentionally NOT under RLS. They're
-- identity/provisioning tables touched by endpoints that run *before* a
-- tenant session exists (login, invite-accept) — RLS session variables
-- aren't available yet at that point in the request. Isolation on these two
-- tables is enforced at the app layer (every query filters by agency_id)
-- plus the composite FK on memberships.client_id, which still guarantees a
-- membership's client belongs to the same agency as the membership itself.
-- Every table that holds actual client-facing work product — clients,
-- projects, tasks, comments, files, time_entries, project_assignments — is
-- under DB-enforced RLS above.
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS invites CASCADE;
DROP TABLE IF EXISTS time_entries CASCADE;
DROP TABLE IF EXISTS files CASCADE;
DROP TABLE IF EXISTS comments CASCADE;
DROP TABLE IF EXISTS tasks CASCADE;
DROP TABLE IF EXISTS project_assignments CASCADE;
DROP TABLE IF EXISTS projects CASCADE;
DROP TABLE IF EXISTS memberships CASCADE;
DROP TABLE IF EXISTS clients CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS agencies CASCADE;
DROP FUNCTION IF EXISTS set_updated_at CASCADE;
DROP TYPE IF EXISTS invite_status;
DROP TYPE IF EXISTS approval_status_type;
DROP TYPE IF EXISTS task_priority;
DROP TYPE IF EXISTS task_status;
DROP TYPE IF EXISTS visibility_type;
DROP TYPE IF EXISTS membership_status;
DROP TYPE IF EXISTS role_type;
"""


def upgrade():
    op.execute(UPGRADE_SQL)


def downgrade():
    op.execute(DOWNGRADE_SQL)
