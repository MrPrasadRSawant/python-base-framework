"""Create the first admin (or give an existing user the admin role).

    cd backend
    python -m app.scripts.create_admin admin@example.com "Admin Name"

Asks for the password when the user is new. Needs `alembic upgrade head` first.
"""

import argparse
import asyncio
import getpass
import sys

from app.core.request_context import set_current_actor
from app.core.security import hash_password
from app.core.security.permissions import ADMIN_ROLE
from app.db.session import SessionLocal, engine
from app.schemas.user import PASSWORD_MIN_LENGTH, UserCreate, normalize_email
from app.services.role import RoleService
from app.services.user import UserService
from app.services.user_role import UserRoleService


async def create_admin(email: str, full_name: str) -> None:
    set_current_actor("cli:create_admin")
    async with SessionLocal() as db:
        role = await RoleService(db).get_by_code(ADMIN_ROLE)
        if role is None:
            sys.exit("The admin role is missing. Run `alembic upgrade head` first.")
        users = UserService(db)
        user = await users.get_by_email(email)
        if user is None:
            password = getpass.getpass("Password: ")
            if len(password) < PASSWORD_MIN_LENGTH:
                sys.exit(f"Password must be at least {PASSWORD_MIN_LENGTH} characters.")
            if password != getpass.getpass("Repeat password: "):
                sys.exit("Passwords do not match.")
            user = await users.create(
                UserCreate(email=email, full_name=full_name, password_hash=hash_password(password))
            )
            print(f"Created user {email}")
        user_roles = UserRoleService(db)
        codes = set(await user_roles.role_codes_for_user(user.id))
        if ADMIN_ROLE not in codes:
            existing = await RoleService(db).get_by_codes(codes)
            await user_roles.replace_for_user(user.id, [role.id, *(r.id for r in existing)])
        print(f"{email} has the {ADMIN_ROLE} role")
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("email")
    parser.add_argument("full_name", nargs="?", default="Administrator")
    args = parser.parse_args()
    asyncio.run(create_admin(normalize_email(args.email), args.full_name))


if __name__ == "__main__":
    main()
