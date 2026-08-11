import uuid
import enum

from sqlalchemy import (
    Column,
    String,
    Text,
    ForeignKey,
    DateTime,
    Date,
    Integer,
    Enum,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .database import Base


class RoleType(str, enum.Enum):
    agency_admin = "agency_admin"
    agency_member = "agency_member"
    client_user = "client_user"


class MembershipStatus(str, enum.Enum):
    active = "active"
    removed = "removed"


class VisibilityType(str, enum.Enum):
    internal = "internal"
    client_visible = "client_visible"


class TaskStatus(str, enum.Enum):
    todo = "todo"
    in_progress = "in_progress"
    in_review = "in_review"
    done = "done"


class TaskPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    needs_changes = "needs_changes"


class InviteStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    revoked = "revoked"


def _uuid_col(primary_key=False, fk=None):
    kwargs = dict(default=uuid.uuid4)
    if primary_key:
        kwargs["primary_key"] = True
    if fk:
        return Column(UUID(as_uuid=True), ForeignKey(fk), **kwargs)
    return Column(UUID(as_uuid=True), **kwargs)


class Agency(Base):
    __tablename__ = "agencies"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    """Global identity. Never carries a tenant or role directly — see Membership."""

    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    memberships = relationship("Membership", back_populates="user")


class Membership(Base):
    __tablename__ = "memberships"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False)
    role = Column(Enum(RoleType, name="role_type"), nullable=False)
    client_id = Column(UUID(as_uuid=True), nullable=True)
    status = Column(
        Enum(MembershipStatus, name="membership_status"),
        nullable=False,
        default=MembershipStatus.active,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "agency_id"),)

    user = relationship("User", back_populates="memberships")


class Client(Base):
    __tablename__ = "clients"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Project(Base):
    __tablename__ = "projects"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False)
    client_id = Column(UUID(as_uuid=True), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ProjectAssignment(Base):
    __tablename__ = "project_assignments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), nullable=False)
    agency_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("project_id", "user_id"),)


class Task(Base):
    __tablename__ = "tasks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), nullable=False)
    project_id = Column(UUID(as_uuid=True), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(TaskStatus, name="task_status"), nullable=False, default=TaskStatus.todo)
    priority = Column(
        Enum(TaskPriority, name="task_priority"), nullable=False, default=TaskPriority.medium
    )
    assignee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    due_date = Column(Date, nullable=True)
    visibility = Column(
        Enum(VisibilityType, name="visibility_type"),
        nullable=False,
        default=VisibilityType.internal,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class Comment(Base):
    __tablename__ = "comments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), nullable=False)
    task_id = Column(UUID(as_uuid=True), nullable=False)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    body = Column(Text, nullable=False)
    visibility = Column(
        Enum(VisibilityType, name="visibility_type"),
        nullable=False,
        default=VisibilityType.internal,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FileAsset(Base):
    __tablename__ = "files"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), nullable=False)
    task_id = Column(UUID(as_uuid=True), nullable=False)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    storage_path = Column(String, nullable=False)
    visibility = Column(
        Enum(VisibilityType, name="visibility_type"),
        nullable=False,
        default=VisibilityType.internal,
    )
    approval_status = Column(
        Enum(ApprovalStatus, name="approval_status_type"),
        nullable=False,
        default=ApprovalStatus.pending,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TimeEntry(Base):
    __tablename__ = "time_entries"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), nullable=False)
    task_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    note = Column(Text, nullable=True)
    entry_date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Invite(Base):
    __tablename__ = "invites"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_id = Column(UUID(as_uuid=True), ForeignKey("agencies.id"), nullable=False)
    email = Column(String, nullable=False)
    role = Column(Enum(RoleType, name="role_type"), nullable=False)
    client_id = Column(UUID(as_uuid=True), nullable=True)
    token = Column(String, nullable=False, unique=True)
    status = Column(Enum(InviteStatus, name="invite_status"), nullable=False, default=InviteStatus.pending)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    accepted_at = Column(DateTime(timezone=True), nullable=True)
