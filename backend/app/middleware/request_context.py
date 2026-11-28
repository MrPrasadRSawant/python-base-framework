"""Assigns a request id to every HTTP request.

* Reuses an incoming ``X-Request-ID`` if it is a UUID (so ids flow across
  services), otherwise generates a UUIDv7.
* Exposes it through a ContextVar (for logging) and ``request.state.request_id``.
* Echoes it in the response header, error responses included.
* Keeps a bounded copy of the request body so error logs can include it
  (the body stream can only be read once, and by the time an exception
  handler runs the endpoint has already consumed it).

Pure ASGI (not BaseHTTPMiddleware): no extra task, ContextVars propagate
cleanly, and streaming responses are unaffected.
"""

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.request_context import (
    REQUEST_BODY_STATE_KEY,
    REQUEST_BODY_TRUNCATED_STATE_KEY,
    REQUEST_ID_STATE_KEY,
    generate_request_id,
    parse_request_id,
    reset_call_counter,
    reset_request_id,
    reset_request_scope,
    set_request_id,
    set_request_scope,
    start_call_counter,
)

_CAPTURABLE_CONTENT_TYPES = ("application/json", "application/x-www-form-urlencoded", "text/")


class RequestContextMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        header_name: str = "X-Request-ID",
        capture_body: bool = True,
        max_body_bytes: int = 4096,
    ) -> None:
        self.app = app
        self.header_name = header_name
        self.capture_body = capture_body
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        incoming = headers.get(self.header_name)
        # Reuse a client-sent UUID (normalized), else generate one. The id is also the
        # primary key of this request's row in the `requests` table.
        request_id = parse_request_id(incoming) or generate_request_id()

        state = scope.setdefault("state", {})
        state[REQUEST_ID_STATE_KEY] = request_id

        content_type = headers.get("content-type", "").lower()
        should_capture = self.capture_body and content_type.startswith(_CAPTURABLE_CONTENT_TYPES)
        buffer = bytearray()

        async def receive_wrapper() -> Message:
            message = await receive()
            if should_capture and message["type"] == "http.request":
                chunk = message.get("body", b"")
                room = self.max_body_bytes - len(buffer)
                if room > 0:
                    buffer.extend(chunk[:room])
                    state[REQUEST_BODY_STATE_KEY] = bytes(buffer)
                if len(chunk) > max(room, 0):
                    state[REQUEST_BODY_TRUNCATED_STATE_KEY] = True
            return message

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[self.header_name] = request_id
            await send(message)

        token = set_request_id(request_id)
        counter_token = start_call_counter()  # numbers tracked service calls 1, 2, 3...
        scope_token = set_request_scope(scope)  # route / client IP for the activity log
        try:
            await self.app(scope, receive_wrapper, send_wrapper)
        finally:
            reset_request_scope(scope_token)
            reset_call_counter(counter_token)
            reset_request_id(token)
