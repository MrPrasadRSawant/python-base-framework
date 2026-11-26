from collections.abc import Sequence
from typing import Any

from app.db.session import SessionLocal
from app.models.exception_log import ExceptionLog


async def insert_exception_logs(rows: Sequence[dict[str, Any]]) -> None:
    """Insert a batch of exception rows in their own session/transaction.

    Uses its own session, independent of the request's (which may have been
    rolled back because of the very error being recorded).
    """
    async with SessionLocal() as session:
        session.add_all(ExceptionLog(**row) for row in rows)
        await session.commit()
