import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth, agencies, clients, projects, tasks, invites, dashboard

app = FastAPI(title="AgencyDesk API")

# Comma-separated list, e.g. "https://agencydesk.vercel.app,http://localhost:5173".
# Defaults to "*" for local/demo use; set this env var once you have a real
# frontend URL to lock it down.
_origins = os.getenv("ALLOWED_ORIGINS", "*")
allow_origins = ["*"] if _origins.strip() == "*" else [o.strip() for o in _origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(agencies.router)
app.include_router(clients.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(invites.router)
app.include_router(dashboard.router)


@app.get("/health")
def health():
    return {"status": "ok"}
