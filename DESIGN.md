# DESIGN.md

## How the schema enforces tenant isolation

Every tenant-owned table (`clients`, `projects`, `tasks`, `comments`, `files`,
`time_entries`, `project_assignments`) carries an `agency_id`. Two layers
enforce isolation on top of that column, not just "remember the WHERE
clause":

**Composite foreign keys.** A child's `agency_id` isn't just copied from its
parent — it's *constrained* to match. `projects.client_id` has a composite
FK `(client_id, agency_id) → clients(id, agency_id)`, and the same pattern
runs `tasks → projects`, `project_assignments → projects`,
`comments/files/time_entries → tasks`. Postgres physically rejects an insert
that tries to attach Tenant B's client to Tenant A's project — it's a
constraint violation, not a code review catch.

**Row-Level Security.** Every request sets three `SET LOCAL` session
variables from the JWT (`app.current_agency_id`, `app.session_role`,
`app.current_client_id`) before touching the DB (`app/deps.py:get_ctx`).
Every tenant table has `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL
SECURITY` with a policy filtering on `agency_id = current_setting(...)`. The
`FORCE` matters: without it, a role that owns the tables (which is what this
single-role setup uses to run migrations) bypasses RLS entirely. This means
a query that forgets a `WHERE agency_id = ...` clause still can't leak
rows — Postgres filters them out underneath the ORM. `invites` and
`memberships` are the deliberate exception (see below).

## How a client is blocked from internal content

`visibility` (`internal` / `client_visible`) lives directly on tasks,
comments, and files — not inherited, so a client-visible task can still
carry internal-only comments. The RLS policies on those three tables add a
second clause on top of the tenant filter: when `session_role =
'client_user'`, only rows with `visibility = 'client_visible'` **and**
belonging to that client's own projects are returned. Because this is
enforced in the same policy Postgres evaluates for every SELECT, it applies
uniformly to the list endpoint, direct-by-ID lookups, and anywhere else a
query touches these tables — there's no separate "is this the client
view" branch to forget. `time_entries` and `project_assignments` policies
exclude `client_user` outright (clients never see hours or team rosters).
The same policies double as `WITH CHECK` clauses, so a client can't insert
an `internal` comment even if the app layer had a bug — `app/routers/
tasks.py:add_comment` pins it server-side regardless, and the DB backs
that up.

## How the identity model supports one person across two agencies

`users` is a single global table keyed by email — it holds no tenant or
role. `memberships` is the join: `(user_id, agency_id) → role`, unique per
pair, with a `client_id` that's required exactly when `role = 'client_user'`
(a CHECK constraint) and itself composite-FK'd to `clients(id, agency_id)`.
One person can hold an `agency_member` row at Agency A and a `client_user`
row at Agency B with zero duplication. Login reflects this: `/auth/login`
authenticates the email once; if there's more than one active membership it
returns the list of agencies instead of a token, and `/auth/select-agency`
issues a token scoped to exactly one `(agency_id, role, client_id)` triple.
Every subsequent request is locked to that one membership for its lifetime —
switching agencies means picking again, not silently blending permissions
from two tenants in one session.

`invites` and `memberships` are intentionally *not* under RLS, because
login, signup, and invite-accept run before any tenant session exists —
there's no `app.current_agency_id` to filter on yet. Isolation there is
app-level (every admin-facing query filters by `agency_id`) plus the
composite FK. Everything client-facing work actually lives in stays under
DB-enforced RLS.

## Edge case I'm proud of: removing a team member mid-task

`DELETE /projects/{id}/assignments/{user_id}` doesn't just drop the
assignment row. In the same transaction it finds that member's non-`done`
tasks on the project and clears `assignee_id` — the work stays visible on
the board with an obvious "needs an owner" signal, instead of silently
pointing at someone who can no longer act on it (they'd fail
`agency_member` project-scoping checks the moment they tried) or getting
deleted outright. The endpoint returns the list of task IDs it touched so
the caller can prompt for reassignment immediately. Invite races got a
similar "make it structurally impossible" treatment rather than a runtime
check: a partial unique index (`agency_id, email, role WHERE status =
'pending'`) means a second invite for the same person just rotates the
token on the existing row, and accepting is idempotent because it looks
for an existing membership before creating one, guarded by the
`(user_id, agency_id)` unique constraint as a backstop.
