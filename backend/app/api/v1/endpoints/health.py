import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    try:
        await db.execute(text("SELECT 1"))
        database = "ok"
    except Exception as exc:
        # Health checks report DB state instead of failing; still log why.
        logger.warning("Database health check failed: %s", exc, exc_info=True)
        database = "unavailable"
    return {"status": "ok", "database": database}
