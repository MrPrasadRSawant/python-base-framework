from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.user import PASSWORD_MAX_LENGTH, normalize_email


class LoginRequest(BaseModel):
    """Email + password sign-in."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr = Field(max_length=255, examples=["alice@example.com"])
    password: str = Field(
        min_length=1, max_length=PASSWORD_MAX_LENGTH, examples=["correct-horse-battery"]
    )

    _email = field_validator("email")(normalize_email)


class TokenResponse(BaseModel):
    """An access token. Send it as `Authorization: Bearer <access_token>`."""

    access_token: str = Field(description="JWT access token")
    token_type: Literal["bearer"] = Field("bearer", description="Always `bearer`")
    expires_in: int = Field(description="Seconds until the access token expires", examples=[900])
