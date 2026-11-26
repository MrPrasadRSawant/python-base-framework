"""Last line of defence: any exception no handler claimed -> logged 500.

Why a middleware and not ``app.add_exception_handler(Exception, ...)``?
Starlette runs the ``Exception`` handler in ``ServerErrorMiddleware``, which
sits *outside* every user middleware. There the request-id ContextVar is
already reset, CORS headers are missing, the handler is skipped completely
when ``debug=True``, and the error is re-raised afterwards, so uvicorn logs
it a second time. Catching it here, inside RequestContextMiddleware, avoids
all of that.
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.exceptions.reporting import report_exception
from app.core.exceptions.responses import error_response
from app.core.request_context import request_id_from_scope


class UnhandledExceptionMiddleware:
    def __init__(self, app: ASGIApp, expose_details: bool = False) -> None:
        self.app = app
        self.expose_details = expose_details

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            report_exception(scope, exc, status_code=500, error_code="internal_server_error")
            if response_started:
                # Headers already sent (e.g. a failing stream): nothing safe to send.
                raise
            details = (
                {"exception_type": type(exc).__name__, "exception_message": str(exc)}
                if self.expose_details
                else None
            )
            response = error_response(
                status_code=500,
                code="internal_server_error",
                message=(
                    "An unexpected error occurred. "
                    "Please quote the request id when reporting it."
                ),
                request_id=request_id_from_scope(scope),
                details=details,
            )
            await response(scope, receive, send)
