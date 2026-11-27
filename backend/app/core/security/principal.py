"""Who is calling: the result of authenticating a request.

Built from the access token by AuthenticationMiddleware and read by the
dependencies in core/security/dependencies.py.
"""

from dataclasses import dataclass, field
from typing import Literal

PrincipalType = Literal["user", "service"]

PRINCIPAL_STATE_KEY = "principal"
AUTH_ERROR_STATE_KEY = "auth_error"  # why a sent token was rejected, for the 401


@dataclass(frozen=True, slots=True)
class Principal:
    id: str  # user id, or client_id for a service
    type: PrincipalType
    permissions: frozenset[str] = field(default_factory=frozenset)

    @property
    def actor(self) -> str:
        """Value written to created_by / updated_by and the log tables."""
        return f"{self.type}:{self.id}"

    def has_permissions(self, *codes: str) -> bool:
        return all(code in self.permissions for code in codes)
