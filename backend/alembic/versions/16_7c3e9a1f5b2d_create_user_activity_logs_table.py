"""create user_activity_logs table and the user_activity_logs:read permission

Revision ID: 16_7c3e9a1f5b2d
Revises: 15_dev_permissions
Create Date: 2026-11-28 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '16_7c3e9a1f5b2d'
down_revision: Union[str, Sequence[str], None] = '15_dev_permissions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PERMISSION = 'user_activity_logs:read'
DESCRIPTION = 'View the user activity log (audit trail of changes and sign-ins)'


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('user_activity_logs',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('occurred_on', sa.DateTime(timezone=True), nullable=False),
    sa.Column('actor', sa.String(length=255), nullable=False),
    sa.Column('actor_type', sa.String(length=16), nullable=False),
    sa.Column('actor_id', sa.String(length=64), nullable=True),
    sa.Column('action', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('entity_type', sa.String(length=64), nullable=True),
    sa.Column('entity_id', sa.String(length=64), nullable=True),
    sa.Column('changes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('request_id', sa.Uuid(), nullable=True),
    sa.Column('method', sa.String(length=16), nullable=True),
    sa.Column('route', sa.String(length=512), nullable=True),
    sa.Column('ip_address', sa.String(length=64), nullable=True),
    sa.Column('user_agent', sa.String(length=512), nullable=True),
    sa.Column('created_by', sa.String(length=255), server_default='system', nullable=False),
    sa.Column('created_on', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_by', sa.String(length=255), nullable=True),
    sa.Column('updated_on', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_activity_logs'))
    )
    op.create_index(op.f('ix_user_activity_logs_occurred_on'), 'user_activity_logs', ['occurred_on'], unique=False)
    op.create_index(op.f('ix_user_activity_logs_actor_type'), 'user_activity_logs', ['actor_type'], unique=False)
    op.create_index(op.f('ix_user_activity_logs_action'), 'user_activity_logs', ['action'], unique=False)
    op.create_index(op.f('ix_user_activity_logs_status'), 'user_activity_logs', ['status'], unique=False)
    op.create_index(op.f('ix_user_activity_logs_request_id'), 'user_activity_logs', ['request_id'], unique=False)
    op.create_index(op.f('ix_user_activity_logs_ip_address'), 'user_activity_logs', ['ip_address'], unique=False)
    op.create_index(op.f('ix_user_activity_logs_created_on'), 'user_activity_logs', ['created_on'], unique=False)
    op.create_index(op.f('ix_user_activity_logs_is_deleted'), 'user_activity_logs', ['is_deleted'], unique=False)
    op.create_index('ix_user_activity_logs_entity', 'user_activity_logs', ['entity_type', 'entity_id', 'occurred_on'], unique=False)
    op.create_index('ix_user_activity_logs_actor_occurred', 'user_activity_logs', ['actor_id', 'occurred_on'], unique=False)

    # Permission catalog (core/security/permissions.py) + grant to the admin role,
    # which holds every permission.
    op.execute(
        sa.text(
            "INSERT INTO permissions (code, description) VALUES (:code, :description) "
            "ON CONFLICT (code) DO NOTHING"
        ).bindparams(code=PERMISSION, description=DESCRIPTION)
    )
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT r.id, p.id FROM roles r CROSS JOIN permissions p "
            "WHERE r.code = 'admin' AND r.is_deleted = false AND p.code = :code "
            "AND NOT EXISTS (SELECT 1 FROM role_permissions rp "
            "WHERE rp.role_id = r.id AND rp.permission_id = p.id)"
        ).bindparams(code=PERMISSION)
    )


def downgrade() -> None:
    """Downgrade schema."""
    # role_permissions rows go with the permission (ON DELETE CASCADE).
    op.execute(sa.text("DELETE FROM permissions WHERE code = :code").bindparams(code=PERMISSION))
    op.drop_index('ix_user_activity_logs_actor_occurred', table_name='user_activity_logs')
    op.drop_index('ix_user_activity_logs_entity', table_name='user_activity_logs')
    op.drop_index(op.f('ix_user_activity_logs_is_deleted'), table_name='user_activity_logs')
    op.drop_index(op.f('ix_user_activity_logs_created_on'), table_name='user_activity_logs')
    op.drop_index(op.f('ix_user_activity_logs_ip_address'), table_name='user_activity_logs')
    op.drop_index(op.f('ix_user_activity_logs_request_id'), table_name='user_activity_logs')
    op.drop_index(op.f('ix_user_activity_logs_status'), table_name='user_activity_logs')
    op.drop_index(op.f('ix_user_activity_logs_action'), table_name='user_activity_logs')
    op.drop_index(op.f('ix_user_activity_logs_actor_type'), table_name='user_activity_logs')
    op.drop_index(op.f('ix_user_activity_logs_occurred_on'), table_name='user_activity_logs')
    op.drop_table('user_activity_logs')
