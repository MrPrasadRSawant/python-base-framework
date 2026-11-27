"""requests table keyed by request id

* request_logs is renamed to requests, and its id becomes the request id
  (the separate request_id column is dropped). Existing rows are kept.
* exception_log.request_id and service_call_logs.request_id become UUIDs:
  a logical link to requests.id (indexed, not an enforced foreign key).
  Values that are not UUIDs (old custom ids) become NULL.

Written by hand: autogenerate would drop and recreate the table, losing data.

Revision ID: 07_69299a6a71c1
Revises: 06_612fd1052b30
Create Date: 2026-11-27 10:21:50.928468

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '07_69299a6a71c1'
down_revision: Union[str, Sequence[str], None] = '06_612fd1052b30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Accepts "550e8400-e29b-41d4-a716-446655440000" and the 32-hex form without hyphens.
UUID_RE = r"'^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$'"

RENAMED_INDEXES = ("created_on", "is_deleted", "route", "started_on", "status_code")


def _to_uuid(table: str) -> None:
    op.execute(
        f"ALTER TABLE {table} ALTER COLUMN request_id TYPE UUID USING "
        f"CASE WHEN request_id ~* {UUID_RE} THEN request_id::uuid ELSE NULL END"
    )


def upgrade() -> None:
    # --- request_logs -> requests, id = request id -------------------------
    op.execute(f"DELETE FROM request_logs WHERE request_id !~* {UUID_RE}")
    # Keep one row per request id (oldest) so the new primary key is unique.
    op.execute(
        "DELETE FROM request_logs a USING request_logs b "
        "WHERE a.request_id = b.request_id AND (a.created_on, a.id) > (b.created_on, b.id)"
    )
    op.execute("UPDATE request_logs SET id = request_id::uuid")
    op.drop_index("ix_request_logs_request_id", table_name="request_logs")
    op.drop_column("request_logs", "request_id")

    op.rename_table("request_logs", "requests")
    op.execute("ALTER TABLE requests RENAME CONSTRAINT pk_request_logs TO pk_requests")
    for column in RENAMED_INDEXES:
        op.execute(f"ALTER INDEX ix_request_logs_{column} RENAME TO ix_requests_{column}")

    # --- request_id -> UUID in the other log tables ------------------------
    _to_uuid("exception_log")
    _to_uuid("service_call_logs")


def downgrade() -> None:
    op.execute("ALTER TABLE service_call_logs ALTER COLUMN request_id TYPE VARCHAR(128)")
    op.execute("ALTER TABLE exception_log ALTER COLUMN request_id TYPE VARCHAR(128)")

    for column in RENAMED_INDEXES:
        op.execute(f"ALTER INDEX ix_requests_{column} RENAME TO ix_request_logs_{column}")
    op.execute("ALTER TABLE requests RENAME CONSTRAINT pk_requests TO pk_request_logs")
    op.rename_table("requests", "request_logs")

    op.execute("ALTER TABLE request_logs ADD COLUMN request_id VARCHAR(128)")
    op.execute("UPDATE request_logs SET request_id = id::text")
    op.execute("ALTER TABLE request_logs ALTER COLUMN request_id SET NOT NULL")
    op.create_index("ix_request_logs_request_id", "request_logs", ["request_id"])
