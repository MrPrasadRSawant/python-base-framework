from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, false, text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin


class User(AuditMixin, Base):
    """A person who signs in to the web app.

    ``email`` is stored lower-cased. Email and case-insensitive username are
    unique among non-deleted users, so a soft-deleted account can be recreated.
    Only the argon2 hash of the password is stored.
    """

    __tablename__ = "users"
    __table_args__ = (
        Index(
            "uq_users_email",
            "email",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        Index(
            "uq_users_username",
            text("lower(username)"),
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )
    # Sign-in bookkeeping: written on every login attempt, recorded as login /
    # login_failed events instead of row updates (see app/core/activity_log.py).
    __activity_log_ignore__ = frozenset({"failed_login_count", "locked_until", "last_login_on"})

    username: Mapped[str] = mapped_column(String(64))
    email: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Lockout: failed logins in a row; locked while locked_until is in the future.
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
