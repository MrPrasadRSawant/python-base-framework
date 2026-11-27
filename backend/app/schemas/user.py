from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.base import CreateSchema, ResponseSchema, UpdateSchema

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128  # argon2 handles any length; this stops huge bodies
USERNAME_PATTERN = r"^[A-Za-z][A-Za-z0-9_]{1,63}$"


def normalize_email(value: str) -> str:
    return value.strip().lower()


class UserRegister(CreateSchema):
    """New account (self-registration)."""

    username: str = Field(
        min_length=2,
        max_length=64,
        pattern=USERNAME_PATTERN,
        description="Unique sign-in name; case-insensitive, separate from email and display name",
        examples=["Developer"],
    )
    email: EmailStr = Field(
        max_length=255,
        description="Sign-in email; stored lower-cased",
        examples=["alice@example.com"],
    )
    full_name: str = Field(min_length=1, max_length=255, examples=["Alice Smith"])
    password: str = Field(
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        description=f"{PASSWORD_MIN_LENGTH} to {PASSWORD_MAX_LENGTH} characters",
        examples=["correct-horse-battery"],
    )

    _email = field_validator("email")(normalize_email)


class UserAdminCreate(UserRegister):
    """New account created by an admin, optionally with roles."""

    roles: list[str] = Field(
        default_factory=list,
        max_length=100,
        description="Role codes to assign (see `GET /roles`)",
        examples=[["support_agent"]],
    )


class UserCreate(CreateSchema):
    # Internal: the row to insert, built by the endpoint, never sent by a client.
    username: str = Field(min_length=2, max_length=64, pattern=USERNAME_PATTERN)
    email: str = Field(max_length=255)
    full_name: str = Field(max_length=255)
    password_hash: str = Field(max_length=255)


class UserUpdate(UpdateSchema):
    """Fields to change; omitted fields keep their value."""

    username: str | None = Field(None, min_length=2, max_length=64, pattern=USERNAME_PATTERN)
    full_name: str | None = Field(None, min_length=1, max_length=255)
    is_active: bool | None = Field(
        None, description="`false` disables sign-in and ends the user's sessions"
    )


class UserLockUpdate(BaseModel):
    """Persistent administrator lock, separate from enabled/disabled status."""

    model_config = ConfigDict(extra="forbid")

    locked: bool = Field(description="true blocks sign-in until an administrator unlocks")


class UserResponse(ResponseSchema):
    """A user account."""

    username: str = Field(description="Unique case-insensitive sign-in name")
    email: str = Field(description="Sign-in email (lower case)")
    full_name: str
    is_active: bool = Field(description="`false` = disabled: cannot sign in")
    is_locked: bool = Field(description="Persistent administrator lock")
    locked_until: datetime | None = Field(description="Temporary failed-login lockout (UTC)")
    last_login_on: datetime | None = Field(description="Last successful sign-in (UTC)")


class UserDetailResponse(UserResponse):
    """A user account with its access."""

    roles: list[str] = Field(description="Assigned role codes", examples=[["admin"]])
    permissions: list[str] = Field(
        description="Effective permission codes from all roles", examples=[["users:read"]]
    )
