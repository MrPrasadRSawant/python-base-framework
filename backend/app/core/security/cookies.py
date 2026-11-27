"""The refresh-token cookie: HttpOnly (no JavaScript access), Secure, SameSite,
and scoped to the /auth routes so it is not sent with every API call."""

from fastapi import Response

from app.core.config import settings


def _cookie_path() -> str:
    return f"{settings.API_V1_PREFIX}/auth"


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        token,
        max_age=settings.REFRESH_TOKEN_TTL_DAYS * 24 * 3600,
        path=_cookie_path(),
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        settings.REFRESH_COOKIE_NAME,
        path=_cookie_path(),
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )
