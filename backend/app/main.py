import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.logging.db_sink import (
    exception_log_sink,
    request_log_sink,
    service_call_log_sink,
)
from app.db.session import SessionLocal, engine
from app.middleware import register_middleware
from app.scripts.seed_development_accounts import seed_development_accounts

setup_logging(settings)

# ---- API docs (Swagger /docs, ReDoc /redoc) --------------------------------
API_VERSION = "1.0.0"
API_DESCRIPTION = (Path(__file__).parent / "api" / "api_description.md").read_text("utf-8")
OPENAPI_TAGS = [
    {
        "name": "auth",
        "description": "Sign in, renew and end sessions, OAuth2 tokens for tools and API "
        "clients, and the current user.",
    },
    {"name": "users", "description": "User administration: accounts, status and roles."},
    {
        "name": "roles",
        "description": "Roles (named sets of permissions assigned to users) and the "
        "read-only permission catalog.",
    },
    {
        "name": "api clients",
        "description": "Server-to-server integrations (OAuth2 client credentials): "
        "credentials, permissions, IP allowlist and secret rotation.",
    },
    {
        "name": "exception logs",
        "description": "Stored API errors and server exceptions, for support and debugging.",
    },
    {
        "name": "requests",
        "description": "One row per HTTP request (route, status, duration) and developer "
        "reports that join service calls and errors.",
    },
    {
        "name": "service call logs",
        "description": "Timing and outcome of each tracked service call within a request.",
    },
    {"name": "health", "description": "Liveness and database status, for monitoring."},
]
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    logger.info("Starting %s (%s)", settings.APP_NAME, settings.ENVIRONMENT)
    if settings.ENVIRONMENT == "development" and settings.DEV_SEED_ACCOUNTS:
        async with SessionLocal() as db:
            await seed_development_accounts(db)
    if settings.EXCEPTION_LOG_DB_ENABLED:
        await exception_log_sink.start()
    if settings.REQUEST_LOG_DB_ENABLED:
        await request_log_sink.start()
    if settings.SERVICE_CALL_LOG_DB_ENABLED:
        await service_call_log_sink.start()
    yield
    # Flush queued log rows before closing the DB pool.
    await service_call_log_sink.stop()
    await request_log_sink.stop()
    await exception_log_sink.stop()
    await engine.dispose()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    # debug stays False: in debug mode Starlette shows its own traceback page
    # instead of our handlers. settings.DEBUG controls error detail instead.
    app = FastAPI(
        title=settings.APP_NAME,
        version=API_VERSION,
        description=API_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        debug=False,
        lifespan=lifespan,
        # Keep the Swagger "Authorize" token across page reloads.
        swagger_ui_parameters={"persistAuthorization": True},
    )

    register_middleware(app, settings)
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"message": f"{settings.APP_NAME} is running", "docs": "/docs"}

    return app


app = create_app()
