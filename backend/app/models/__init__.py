# Import every model here so Alembic autogenerate can discover them.
from app.models.api_client import ApiClient, ApiClientPermission
from app.models.exception_log import ExceptionLog
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.refresh_token import RefreshToken
from app.models.request_log import RequestLog
from app.models.service_call_log import ServiceCallLog
from app.models.user import User
from app.models.user_activity_log import UserActivityLog

__all__ = [
    "ApiClient",
    "ApiClientPermission",
    "ExceptionLog",
    "Permission",
    "RefreshToken",
    "RequestLog",
    "Role",
    "RolePermission",
    "ServiceCallLog",
    "User",
    "UserActivityLog",
    "UserRole",
]
