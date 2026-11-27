from datetime import timedelta

from sqlalchemy import select

from app.core.service_tracking import track_service
from app.db.mixins import utc_now
from app.models import User
from app.services.base import AUDIT_FIELDS, BaseService


class UserService(BaseService):
    model = User
    filter_fields = ("email", "full_name", "is_active", "last_login_on", *AUDIT_FIELDS)
    sort_fields = ("email", "full_name", "created_on", "last_login_on")
    search_fields = ("email", "full_name")

    @track_service
    async def get_by_email(self, email: str) -> User | None:
        """Non-deleted user with this (already lower-cased) email."""
        query = select(User).where(User.email == email, User.is_deleted.is_(False))
        return await self.db.scalar(query)

    @track_service
    async def record_login_failure(
        self, user: User, *, max_failed: int, lock_minutes: int
    ) -> None:
        """Count a wrong password; lock the account once the limit is reached."""
        user.failed_login_count += 1
        if user.failed_login_count >= max_failed:
            user.locked_until = utc_now() + timedelta(minutes=lock_minutes)
            user.failed_login_count = 0
        await self.db.commit()

    @track_service
    async def record_login_success(self, user: User) -> None:
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_on = utc_now()
        await self.db.commit()
