"""The permission catalog: every permission the code checks, in one place.

    @router.get("", dependencies=[Depends(require_permission(Perm.USERS_READ))])

Codes are ``resource:action``. The ``permissions`` table holds the same rows;
they are inserted by migrations, never created from the API. Adding one:
add it here, then add a migration that inserts it (and grants it to ``admin``).
tests/test_rbac.py fails if this list and the table disagree.
"""

from enum import StrEnum


class Perm(StrEnum):
    USERS_READ = "users:read"
    USERS_MANAGE = "users:manage"
    ROLES_READ = "roles:read"
    ROLES_MANAGE = "roles:manage"
    EXCEPTION_LOGS_READ = "exception_logs:read"
    REQUEST_LOGS_READ = "request_logs:read"
    SERVICE_CALL_LOGS_READ = "service_call_logs:read"
    API_CLIENTS_READ = "api_clients:read"
    API_CLIENTS_MANAGE = "api_clients:manage"


DESCRIPTIONS: dict[Perm, str] = {
    Perm.USERS_READ: "View users",
    Perm.USERS_MANAGE: "Create, update, disable and delete users; assign roles",
    Perm.ROLES_READ: "View roles and permissions",
    Perm.ROLES_MANAGE: "Create, update and delete roles; assign permissions",
    Perm.EXCEPTION_LOGS_READ: "View exception logs",
    Perm.REQUEST_LOGS_READ: "View request logs and reports",
    Perm.SERVICE_CALL_LOGS_READ: "View service call logs",
    Perm.API_CLIENTS_READ: "View API clients (server integrations)",
    Perm.API_CLIENTS_MANAGE: "Create, update, rotate secrets of and delete API clients",
}

# Seeded system role: holds every permission, cannot be deleted.
ADMIN_ROLE = "admin"
