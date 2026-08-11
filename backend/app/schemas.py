from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional, List

from pydantic import BaseModel, Field

from .models import RoleType, VisibilityType, TaskStatus, TaskPriority, ApprovalStatus, InviteStatus


# ── auth ─────────────────────────────────────────────────────────────────
class SignupAgency(BaseModel):
    agency_name: str
    admin_name: str
    email: str
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: str
    password: str


class MembershipChoice(BaseModel):
    agency_id: uuid.UUID
    agency_name: str
    role: RoleType


class LoginResponse(BaseModel):
    # Populated when the email has exactly one active membership.
    access_token: Optional[str] = None
    # Populated when the email has multiple memberships and must pick one.
    pre_auth_token: Optional[str] = None
    choices: List[MembershipChoice] = []


class SelectAgencyRequest(BaseModel):
    pre_auth_token: str
    agency_id: uuid.UUID


class TokenResponse(BaseModel):
    access_token: str
    role: RoleType
    agency_id: uuid.UUID
    agency_name: str
    client_id: Optional[uuid.UUID] = None


# ── clients ──────────────────────────────────────────────────────────────
class ClientCreate(BaseModel):
    name: str


class ClientOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── projects ─────────────────────────────────────────────────────────────
class ProjectCreate(BaseModel):
    client_id: uuid.UUID
    name: str
    description: Optional[str] = None


class ProjectOut(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    name: str
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectAssignmentCreate(BaseModel):
    user_id: uuid.UUID


# ── tasks ────────────────────────────────────────────────────────────────
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.medium
    assignee_id: Optional[uuid.UUID] = None
    due_date: Optional[date] = None
    visibility: VisibilityType = VisibilityType.internal


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    assignee_id: Optional[uuid.UUID] = None
    due_date: Optional[date] = None
    visibility: Optional[VisibilityType] = None


class TaskOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: Optional[str]
    status: TaskStatus
    priority: TaskPriority
    assignee_id: Optional[uuid.UUID]
    due_date: Optional[date]
    visibility: VisibilityType
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── comments ─────────────────────────────────────────────────────────────
class CommentCreate(BaseModel):
    body: str
    visibility: VisibilityType = VisibilityType.internal


class CommentOut(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    author_id: uuid.UUID
    body: str
    visibility: VisibilityType
    created_at: datetime

    class Config:
        from_attributes = True


# ── files ────────────────────────────────────────────────────────────────
class FileOut(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    filename: str
    visibility: VisibilityType
    approval_status: ApprovalStatus
    created_at: datetime

    class Config:
        from_attributes = True


class FileApprovalUpdate(BaseModel):
    approval_status: ApprovalStatus


# ── time entries ─────────────────────────────────────────────────────────
class TimeEntryCreate(BaseModel):
    duration_minutes: int = Field(gt=0)
    note: Optional[str] = None
    entry_date: date


class TimeEntryOut(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    duration_minutes: int
    note: Optional[str]
    entry_date: date
    created_at: datetime

    class Config:
        from_attributes = True


# ── invites ──────────────────────────────────────────────────────────────
class InviteCreate(BaseModel):
    email: str
    role: RoleType
    client_id: Optional[uuid.UUID] = None


class InviteOut(BaseModel):
    id: uuid.UUID
    email: str
    role: RoleType
    status: InviteStatus
    token: str
    created_at: datetime

    class Config:
        from_attributes = True


class InviteAccept(BaseModel):
    token: str
    name: Optional[str] = None
    password: Optional[str] = None


# ── dashboard ────────────────────────────────────────────────────────────
class ProjectDashboard(BaseModel):
    project_id: uuid.UUID
    task_counts_by_status: dict
    total_hours_logged: float
