"""Create the local demo users without changing existing accounts.

Run after ``alembic upgrade head`` or enable ``DEV_SEED_ACCOUNTS`` in local
development. Known demo passwords must never be seeded in a production DB.
"""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.request_context import reset_current_actor, set_current_actor
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.schemas.user import UserCreate
from app.services.role import RoleService
from app.services.user import UserService
from app.services.user_role import UserRoleService

logger = logging.getLogger(__name__)

DEMO_ACCOUNTS = (
    ("Admin", "admin@baseframework.com", "Admin", "Admin@123", "admin"),
    ("Developer", "developer@baseframework.com", "Developer", "Developer@123", "developer"),
)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


async def seed_development_accounts(db: AsyncSession) -> None:
    if settings.ENVIRONMENT != "development" or settings.POSTGRES_HOST not in LOCAL_HOSTS:
        raise RuntimeError("Demo accounts can only be seeded in a local development database.")

    actor_token = set_current_actor("system:dev-seed")
    try:
        users = UserService(db)
        roles = RoleService(db)
        user_roles = UserRoleService(db)
        for username, email, full_name, password, role_code in DEMO_ACCOUNTS:
            role = await roles.get_by_code(role_code)
            if role is None:
                raise RuntimeError(f"Required role {role_code!r} is missing. Run migrations first.")
            existing = await users.get_by_email(email)
            if existing is not None:
                logger.info("Demo account %s already exists; leaving its password and roles unchanged", email)
                continue
            if await users.get_by_username(username) is not None:
                raise RuntimeError(f"Demo username {username!r} is already used by another account.")
            user = await users.create(
                UserCreate(
                    username=username,
                    email=email,
                    full_name=full_name,
                    password_hash=hash_password(password),
                )
            )
            await user_roles.replace_for_user(user.id, [role.id])
            logger.info("Created local demo account %s with the %s role", email, role_code)
    finally:
        reset_current_actor(actor_token)


async def _run() -> None:
    async with SessionLocal() as db:
        await seed_development_accounts(db)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_run())
