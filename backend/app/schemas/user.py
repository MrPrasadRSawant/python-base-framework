from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.schemas.base import CreateSchema, ResponseSchema, UpdateSchema

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128  # argon2 handles any length; this stops huge bodies


def normalize_email(value: str) -> str:
    return value.strip().lower()


class UserRegister(CreateSchema):
    """New account (self-registration)."""

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
    email: str = Field(max_length=255)
    full_name: str = Field(max_length=255)
    password_hash: str = Field(max_length=255)


class UserUpdate(UpdateSchema):
    """Fields to change; omitted fields keep their value."""

    full_name: str | None = Field(None, min_length=1, max_length=255)
    is_active: bool | None = Field(
        None, description="`false` disables sign-in and ends the user's sessions"
    )


class UserResponse(ResponseSchema):
    """A user account."""

    email: str = Field(description="Sign-in email (lower case)")
    full_name: str
    is_active: bool = Field(description="`false` = disabled: cannot sign in")
    last_login_on: datetime | None = Field(description="Last successful sign-in (UTC)")


class UserDetailResponse(UserResponse):
    """A user account with its access."""

    roles: list[str] = Field(description="Assigned role codes", examples=[["admin"]])
    permissions: list[str] = Field(
        description="Effective permission codes from all roles", examples=[["users:read"]]
    )
