import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.logging.db_sink import exception_log_sink, request_log_sink
from app.db.session import engine
from app.middleware import register_middleware

setup_logging(settings)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    logger.info("Starting %s (%s)", settings.APP_NAME, settings.ENVIRONMENT)
    if settings.EXCEPTION_LOG_DB_ENABLED:
        await exception_log_sink.start()
    if settings.REQUEST_LOG_DB_ENABLED:
        await request_log_sink.start()
    yield
    # Flush queued log rows before closing the DB pool.
    await request_log_sink.stop()
    await exception_log_sink.stop()
    await engine.dispose()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    # debug stays False: in debug mode Starlette shows its own traceback page
    # instead of our handlers. settings.DEBUG controls error detail instead.
    app = FastAPI(title=settings.APP_NAME, debug=False, lifespan=lifespan)

    register_middleware(app, settings)
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"message": f"{settings.APP_NAME} is running", "docs": "/docs"}

    return app


app = create_app()
