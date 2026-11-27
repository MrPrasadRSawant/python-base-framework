"""Allow developers to manage role permissions within their own grant scope."""

from alembic import op
import sqlalchemy as sa

revision = "15_dev_permissions"
down_revision = "14_305b4aaf7528"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT r.id, p.id FROM roles r CROSS JOIN permissions p "
            "WHERE r.code = 'developer' AND r.is_deleted = false "
            "AND p.code IN ('roles:read', 'roles:manage') "
            "AND NOT EXISTS (SELECT 1 FROM role_permissions rp "
            "WHERE rp.role_id = r.id AND rp.permission_id = p.id)"
        )
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions rp USING roles r, permissions p "
        "WHERE rp.role_id = r.id AND rp.permission_id = p.id "
        "AND r.code = 'developer' AND p.code IN ('roles:read', 'roles:manage')"
    )
