"""RBAC tables: users get roles, roles get permissions.

    users --< user_roles >-- roles --< role_permissions >-- permissions

Join rows are hard-deleted when a role / permission is taken away (their
``is_deleted`` column is never used), so checks need no soft-delete filter.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, Uuid, false, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class Role(AuditMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (
        Index("uq_roles_code", "code", unique=True, postgresql_where=text("is_deleted = false")),
    )

    code: Mapped[str] = mapped_column(String(64))  # e.g. "admin"
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(String(512))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())


class Permission(AuditMixin, Base):
    """Rows mirror the catalog in core/security/permissions.py (seeded by migrations)."""

    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(128), unique=True)  # resource:action
    description: Mapped[str | None] = mapped_column(String(512))


class UserRole(AuditMixin, Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), index=True
    )


class RolePermission(AuditMixin, Base):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id"),)

    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), index=True
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), index=True
    )
