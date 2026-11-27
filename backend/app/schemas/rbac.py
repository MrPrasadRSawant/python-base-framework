from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import CreateSchema, ResponseSchema, UpdateSchema

ROLE_CODE_PATTERN = r"^[a-z][a-z0-9_]{1,63}$"


class RoleCreate(CreateSchema):
    """New role (created without permissions)."""

    code: str = Field(
        pattern=ROLE_CODE_PATTERN,
        description="Stable identifier used in assignments: lower case, digits, `_`; "
        "starts with a letter. Cannot be changed.",
        examples=["support_agent"],
    )
    name: str = Field(min_length=1, max_length=128, examples=["Support agent"])
    description: str | None = Field(None, max_length=512, examples=["Handles customer tickets"])


class RoleUpdate(UpdateSchema):
    """Fields to change; omitted fields keep their value."""

    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = Field(None, max_length=512)


class RoleResponse(ResponseSchema):
    """A role: a named set of permissions assigned to users."""

    code: str = Field(examples=["admin"])
    name: str = Field(examples=["Administrator"])
    description: str | None
    is_system: bool = Field(
        description="Built-in role: cannot be deleted and its permissions cannot change"
    )


class RoleDetailResponse(RoleResponse):
    """A role with its permissions."""

    permissions: list[str] = Field(description="Permission codes", examples=[["users:read"]])


class PermissionResponse(ResponseSchema):
    """One permission from the catalog."""

    code: str = Field(description="`resource:action`", examples=["users:read"])
    description: str | None = Field(examples=["View users"])


class AssignRoles(BaseModel):
    """The user's complete set of roles; replaces the current set."""

    model_config = ConfigDict(extra="forbid")
    roles: list[str] = Field(
        max_length=100, description="Role codes (`[]` removes all)", examples=[["support_agent"]]
    )


class AssignPermissions(BaseModel):
    """The complete set of permissions; replaces the current set."""

    model_config = ConfigDict(extra="forbid")
    permissions: list[str] = Field(
        max_length=500,
        description="Permission codes from `GET /permissions` (`[]` removes all)",
        examples=[["users:read", "request_logs:read"]],
    )
