from .conftest import client, login, auth_headers


def _pixel_project_and_tasks():
    token = login("pixel_admin")
    projects = client.get("/projects", headers=auth_headers(token)).json()
    project = next(p for p in projects if p["name"] == "Northwind Rebrand")
    tasks = client.get(f"/projects/{project['id']}/tasks", headers=auth_headers(token)).json()
    by_title = {t["title"]: t for t in tasks}
    return project, by_title, token


def _loop_project():
    token = login("loop_admin")
    projects = client.get("/projects", headers=auth_headers(token)).json()
    project = next(p for p in projects if p["name"] == "Acme Launch Site")
    return project, token


# ── cross-tenant access ─────────────────────────────────────────────────
def test_cross_tenant_task_lookup_by_guessed_id_returns_404():
    project, tasks, _ = _pixel_project_and_tasks()
    pixel_task_id = tasks["Logo concepts"]["id"]

    loop_token = login("loop_admin")
    resp = client.get(f"/tasks/{pixel_task_id}", headers=auth_headers(loop_token))
    assert resp.status_code == 404


def test_cross_tenant_project_lookup_by_guessed_id_returns_404():
    project, _ = _loop_project()
    loop_project_id = project["id"]

    pixel_token = login("pixel_admin")
    resp = client.get(f"/projects/{loop_project_id}", headers=auth_headers(pixel_token))
    assert resp.status_code == 404


def test_cross_tenant_client_list_never_shows_other_agency():
    pixel_token = login("pixel_admin")
    names = {c["name"] for c in client.get("/clients", headers=auth_headers(pixel_token)).json()}
    assert "Acme Corp" not in names
    assert "Northwind Traders" in names


# ── internal content never reaches the client portal ────────────────────
def test_client_task_list_excludes_internal_tasks():
    project, tasks, _ = _pixel_project_and_tasks()
    client_token = login("northwind_client")
    resp = client.get(f"/projects/{project['id']}/tasks", headers=auth_headers(client_token))
    assert resp.status_code == 200
    titles = {t["title"] for t in resp.json()}
    assert "Internal budget review" not in titles
    assert "Logo concepts" in titles


def test_client_cannot_fetch_internal_task_directly_by_id():
    _, tasks, _ = _pixel_project_and_tasks()
    internal_id = tasks["Internal budget review"]["id"]
    client_token = login("northwind_client")
    resp = client.get(f"/tasks/{internal_id}", headers=auth_headers(client_token))
    assert resp.status_code == 404


def test_client_sees_only_client_visible_comments():
    _, tasks, _ = _pixel_project_and_tasks()
    logo_task_id = tasks["Logo concepts"]["id"]
    client_token = login("northwind_client")
    resp = client.get(f"/tasks/{logo_task_id}/comments", headers=auth_headers(client_token))
    assert resp.status_code == 200
    bodies = [c["body"] for c in resp.json()]
    assert all("font we're not licensed" not in b for b in bodies)
    assert any("three directions" in b for b in bodies)


def test_client_cannot_see_time_entries():
    _, tasks, _ = _pixel_project_and_tasks()
    logo_task_id = tasks["Logo concepts"]["id"]
    client_token = login("northwind_client")
    resp = client.get(f"/tasks/{logo_task_id}/time-entries", headers=auth_headers(client_token))
    assert resp.status_code == 403  # staff-only endpoint, independent of RLS too


def test_client_cannot_create_or_change_status_of_task():
    project, tasks, _ = _pixel_project_and_tasks()
    client_token = login("northwind_client")

    create_resp = client.post(
        f"/projects/{project['id']}/tasks",
        headers=auth_headers(client_token),
        json={"title": "Sneaky task", "visibility": "client_visible"},
    )
    assert create_resp.status_code == 403

    logo_task_id = tasks["Logo concepts"]["id"]
    patch_resp = client.patch(
        f"/tasks/{logo_task_id}", headers=auth_headers(client_token), json={"status": "done"}
    )
    assert patch_resp.status_code == 403


def test_client_can_comment_but_only_client_visible():
    _, tasks, _ = _pixel_project_and_tasks()
    logo_task_id = tasks["Logo concepts"]["id"]
    client_token = login("northwind_client")
    resp = client.post(
        f"/tasks/{logo_task_id}/comments",
        headers=auth_headers(client_token),
        json={"body": "Loving direction 1!", "visibility": "internal"},  # attempt to force internal
    )
    assert resp.status_code == 200
    # even though the client asked for "internal", the server pins it to client_visible
    assert resp.json()["visibility"] == "client_visible"


# ── one person, two agencies ─────────────────────────────────────────────
def test_same_email_different_roles_in_different_agencies():
    pixel_token = login("jordan", agency_name="Pixel & Co")
    loop_token = login("jordan", agency_name="Studio Loop")

    # As a Pixel & Co agency_member, Jordan can see Pixel projects.
    pixel_projects = client.get("/projects", headers=auth_headers(pixel_token)).json()
    assert any(p["name"] == "Northwind Rebrand" for p in pixel_projects)

    # As a Studio Loop client_user, Jordan sees only Acme's client-visible work,
    # and nothing from Pixel & Co leaks through on the same human being.
    loop_projects = client.get("/projects", headers=auth_headers(loop_token)).json()
    names = {p["name"] for p in loop_projects}
    assert names == {"Acme Launch Site"}


# ── invite races ──────────────────────────────────────────────────────────
def test_resending_invite_does_not_duplicate():
    token = login("pixel_admin")
    payload = {"email": "new-member@pixelco.test", "role": "agency_member"}
    first = client.post("/invites", headers=auth_headers(token), json=payload).json()
    second = client.post("/invites", headers=auth_headers(token), json=payload).json()
    assert first["id"] == second["id"]
    assert first["token"] != second["token"]  # resend rotates the token

    invites = client.get("/invites", headers=auth_headers(token)).json()
    matching = [i for i in invites if i["email"] == "new-member@pixelco.test"]
    assert len(matching) == 1


def test_accepting_same_invite_twice_does_not_create_two_accounts():
    token = login("pixel_admin")
    payload = {"email": "double-accept@pixelco.test", "role": "agency_member"}
    invite = client.post("/invites", headers=auth_headers(token), json=payload).json()

    accept_body = {"token": invite["token"], "name": "Double Accept", "password": "password123"}
    first = client.post("/invites/accept", json=accept_body)
    assert first.status_code == 200

    second = client.post("/invites/accept", json=accept_body)
    assert second.status_code == 200

    # Logging in now must resolve to exactly one membership in this agency,
    # not two — a login with a single active membership returns
    # access_token directly rather than a list of choices.
    login_resp = client.post(
        "/auth/login", json={"email": "double-accept@pixelco.test", "password": "password123"}
    )
    assert login_resp.json().get("access_token") is not None


# ── removing a team member mid-task ───────────────────────────────────────
def test_removing_project_member_unassigns_their_open_tasks():
    token = login("pixel_admin")
    project, tasks, _ = _pixel_project_and_tasks()
    wireframe = tasks["Homepage wireframe"]

    members = client.get("/agency/members", headers=auth_headers(token)).json()
    jordan_id = next(m["user_id"] for m in members if m["email"] == "jordan@freelance.test")
    assert wireframe["assignee_id"] == jordan_id

    resp = client.delete(
        f"/projects/{project['id']}/assignments/{jordan_id}", headers=auth_headers(token)
    )
    assert resp.status_code == 200
    assert wireframe["id"] in resp.json()["unassigned_task_ids"]

    refreshed = client.get(f"/tasks/{wireframe['id']}", headers=auth_headers(token)).json()
    assert refreshed["assignee_id"] is None
