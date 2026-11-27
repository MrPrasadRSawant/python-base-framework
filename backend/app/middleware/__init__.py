"""Middleware registration. The order here is deliberate.

``add_middleware`` wraps the app, so the *last* one added is the outermost.
The resulting request flow (outer -> inner):

    RequestContextMiddleware    assigns the request id, captures the body, sets the response header
      AuthenticationMiddleware  Bearer token -> request.state.principal + current actor
        AccessLogMiddleware     one log line per request, with status and duration
          CORSMiddleware        CORS headers on every response, 500s included
            UnhandledExceptionMiddleware   unhandled error -> logged 500 JSON
              ExceptionMiddleware (Starlette)  runs the handlers in core/exceptions
                router -> endpoint

Authentication sits outside the access log so the log line (and the requests
row built from it) carries the caller as created_by.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings
from app.middleware.access_log import AccessLogMiddleware
from app.middleware.authentication import AuthenticationMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.middleware.unhandled_exception import UnhandledExceptionMiddleware


def register_middleware(app: FastAPI, settings: Settings) -> None:
    # innermost first
    app.add_middleware(UnhandledExceptionMiddleware, expose_details=settings.DEBUG)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[settings.REQUEST_ID_HEADER],
    )
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(AuthenticationMiddleware)
    app.add_middleware(
        RequestContextMiddleware,
        header_name=settings.REQUEST_ID_HEADER,
        capture_body=settings.LOG_REQUEST_BODY_ON_ERROR,
        max_body_bytes=settings.LOG_MAX_BODY_BYTES,
    )


__all__ = [
    "AccessLogMiddleware",
    "AuthenticationMiddleware",
    "RequestContextMiddleware",
    "UnhandledExceptionMiddleware",
    "register_middleware",
]
