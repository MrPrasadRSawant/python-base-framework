"""One access-log line per request: method, path, status, duration, client.

Level follows the outcome: INFO for 2xx/3xx, WARNING for 4xx, ERROR for 5xx.
Replaces uvicorn's access log, which knows nothing about request ids.
"""

import logging
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging.request_info import build_request_context

logger = logging.getLogger("app.access")


class AccessLogMiddleware:
    def __init__(self, app: ASGIApp, exclude_paths: tuple[str, ...] = ()) -> None:
        self.app = app
        self.exclude_paths = exclude_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in self.exclude_paths:
            await self.app(scope, receive, send)
            return

        status_code = 500  # if nothing is ever sent, the request failed
        start = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            context = build_request_context(scope)
            context.pop("request_id", None)  # added by RequestIdFilter already
            level = (
                logging.ERROR
                if status_code >= 500
                else logging.WARNING
                if status_code >= 400
                else logging.INFO
            )
            logger.log(
                level,
                "%s %s -> %s (%.2f ms)",
                scope.get("method"),
                scope.get("path"),
                status_code,
                duration_ms,
                extra={"status_code": status_code, "duration_ms": duration_ms, **context},
            )
