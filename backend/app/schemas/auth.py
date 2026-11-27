from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.schemas.user import PASSWORD_MAX_LENGTH


class LoginRequest(BaseModel):
    """Username or email + password sign-in."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    identifier: str = Field(
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("identifier", "email", "username"),
        description="Username or email address; email and username are case-insensitive",
        examples=["Developer"],
    )
    password: str = Field(
        min_length=1, max_length=PASSWORD_MAX_LENGTH, examples=["correct-horse-battery"]
    )

class TokenResponse(BaseModel):
    """An access token. Send it as `Authorization: Bearer <access_token>`."""

    access_token: str = Field(description="JWT access token")
    token_type: Literal["bearer"] = Field("bearer", description="Always `bearer`")
    expires_in: int = Field(description="Seconds until the access token expires", examples=[900])
