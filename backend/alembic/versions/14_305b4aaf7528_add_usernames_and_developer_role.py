"""Add unique usernames and the default developer role.

Revision ID: 14_305b4aaf7528
Revises: 13_c8008b743a4c
Create Date: 2026-11-27 18:00:00.000000

"""
import re
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '14_305b4aaf7528'
down_revision: Union[str, Sequence[str], None] = '13_c8008b743a4c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_USERS = {
    "admin@baseframework.com": "Admin",
    "developer@baseframework.com": "Developer",
}
RESERVED = {name.lower() for name in DEFAULT_USERS.values()}


def _backfill_username(email: str, user_id: uuid.UUID, used: set[str]) -> str:
    normalized_email = email.lower()
    if normalized_email in DEFAULT_USERS:
        base = DEFAULT_USERS[normalized_email]
    else:
        base = re.sub(r"[^A-Za-z0-9_]", "_", email.split("@", 1)[0]).strip("_")
        if not base or not base[0].isalpha():
            base = f"user_{base}"
        if len(base) < 2:
            base += "_user"
    base = base[:64]
    candidate = base
    suffix = user_id.hex[:8]
    if (candidate.lower() in RESERVED and normalized_email not in DEFAULT_USERS) or candidate.lower() in used:
        candidate = f"{base[:55]}_{suffix}"
    counter = 2
    while candidate.lower() in used:
        candidate = f"{base[:50]}_{suffix}_{counter}"
        counter += 1
    used.add(candidate.lower())
    return candidate


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=64), nullable=True))
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, email FROM users ORDER BY id")).all()
    # Reserve the requested names for the matching default emails, even if
    # another account already has the same email local part.
    rows = sorted(rows, key=lambda row: row.email.lower() not in DEFAULT_USERS)
    used: set[str] = set()
    for row in rows:
        username = _backfill_username(row.email, uuid.UUID(str(row.id)), used)
        connection.execute(
            sa.text("UPDATE users SET username = :username WHERE id = :id"),
            {"username": username, "id": row.id},
        )
    op.alter_column("users", "username", nullable=False)
    op.execute(
        "CREATE UNIQUE INDEX uq_users_username ON users (lower(username)) "
        "WHERE is_deleted = false"
    )

    developer_exists = connection.execute(
        sa.text("SELECT 1 FROM roles WHERE code = 'developer' AND is_deleted = false")
    ).scalar_one_or_none()
    if developer_exists is None:
        op.execute(
            "INSERT INTO roles (code, name, description, is_system, created_by) "
            "VALUES ('developer', 'Developer', 'Read access to application logs', false, "
            "'migration:14')"
        )
        op.execute(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT r.id, p.id FROM roles r CROSS JOIN permissions p "
            "WHERE r.code = 'developer' AND r.created_by = 'migration:14' "
            "AND p.code IN ('exception_logs:read', 'request_logs:read', "
            "'service_call_logs:read')"
        )


def downgrade() -> None:
    op.execute("DELETE FROM roles WHERE code = 'developer' AND created_by = 'migration:14'")
    op.drop_index("uq_users_username", table_name="users")
    op.drop_column("users", "username")
