import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.database import SessionLocal
import seed as seed_module

client = TestClient(app)

TENANT_TABLES = [
    "invites",
    "time_entries",
    "files",
    "comments",
    "tasks",
    "project_assignments",
    "projects",
    "clients",
    "memberships",
    "agencies",
    "users",
]

CREDS = {
    "pixel_admin": ("admin@pixelco.test", "password123"),
    "pixel_member": ("member@pixelco.test", "password123"),
    "northwind_client": ("client@northwind.test", "password123"),
    "loop_admin": ("admin@studioloop.test", "password123"),
    "jordan": ("jordan@freelance.test", "password123"),
}


@pytest.fixture(scope="session", autouse=True)
def ensure_seed():
    # TRUNCATE isn't filtered by RLS (unlike SELECT/INSERT/UPDATE/DELETE), so
    # this works with a plain, context-free session. Always start each test
    # run from a clean, freshly-seeded DB so tests are order-independent and
    # rerunnable, instead of relying on whatever state a previous run left.
    db = SessionLocal()
    db.execute(text(f"TRUNCATE TABLE {', '.join(TENANT_TABLES)} RESTART IDENTITY CASCADE"))
    db.commit()
    db.close()

    seed_module.main()
    yield


def login(user_key: str, agency_name: str | None = None) -> str:
    """Log in a seeded user and return a session bearer token. For users
    with more than one membership, `agency_name` picks which one."""
    email, password = CREDS[user_key]
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    if body.get("access_token"):
        return body["access_token"]

    assert body.get("choices"), f"expected multiple agency choices for {user_key}"
    match = next(c for c in body["choices"] if c["agency_name"] == agency_name)
    resp2 = client.post(
        "/auth/select-agency",
        json={"pre_auth_token": body["pre_auth_token"], "agency_id": match["agency_id"]},
    )
    assert resp2.status_code == 200, resp2.text
    return resp2.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
