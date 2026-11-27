"""@track_service: record every call of a service function in service_call_logs.

    class OrderService(BaseService):
        model = Order

        @track_service
        async def mark_paid(self, order_id): ...

    @track_service(name="pricing.calculate")
    def calculate_price(order): ...

Each call records request_id, call_order (1, 2, 3... within the request),
parent_call_order (the tracked call that called it, if any),
service_name, started_on, duration_ms, status (success / failed) and the
exception class on failure. Arguments, return values and error messages are
never stored. Exceptions are re-raised unchanged.

BaseService's CRUD/search methods are already decorated, so every table
service is tracked without extra code. Rows go through the background
writer; when it isn't running (tests, scripts, DB tracking disabled), the
decorator does nothing but call the function.
"""

import functools
import inspect
import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, TypeVar

from app.core.request_context import (
    get_current_actor,
    get_request_id,
    next_call_order,
    request_id_as_uuid,
)

logger = logging.getLogger(__name__)
F = TypeVar("F", bound=Callable[..., Any])

_suppressed: ContextVar[bool] = ContextVar("service_tracking_suppressed", default=False)
# call_order of the tracked call currently running, so nested calls know their parent.
_current_call: ContextVar[int | None] = ContextVar("current_service_call", default=None)


@contextmanager
def suppress_service_tracking() -> Iterator[None]:
    """Don't track calls made inside this block (used by the log writers themselves,
    otherwise saving a tracking row would create another tracking row, forever)."""
    token = _suppressed.set(True)
    try:
        yield
    finally:
        _suppressed.reset(token)


def _sink():
    from app.core.logging.db_sink import service_call_log_sink  # lazy: avoids import cycle

    return service_call_log_sink


def _service_name(func: Callable[..., Any], args: tuple[Any, ...]) -> str:
    # Methods: use the runtime class, so BaseService.search called on
    # ExceptionLogService is recorded as "ExceptionLogService.search".
    if args and not isinstance(args[0], type) and hasattr(type(args[0]), func.__name__):
        return f"{type(args[0]).__name__}.{func.__name__}"
    return func.__qualname__


class _Call:
    __slots__ = ("name", "order", "parent", "token", "request_id", "actor", "started_on", "t0")

    def __init__(self, name: str) -> None:
        self.name = name
        self.order = next_call_order()
        self.parent = _current_call.get()
        self.token = _current_call.set(self.order)  # calls made inside see us as parent
        self.request_id = request_id_as_uuid(get_request_id())
        self.actor = get_current_actor()
        self.started_on = datetime.now(UTC)
        self.t0 = time.perf_counter()

    def finish(self, exc: BaseException | None) -> None:
        _current_call.reset(self.token)
        try:
            from app.schemas.service_call_log import ServiceCallLogCreate

            _sink().enqueue(
                ServiceCallLogCreate(
                    request_id=self.request_id,
                    call_order=self.order,
                    parent_call_order=self.parent,
                    service_name=self.name[:255],
                    started_on=self.started_on,
                    duration_ms=round((time.perf_counter() - self.t0) * 1000, 3),
                    status="failed" if exc is not None else "success",
                    error_type=type(exc).__name__[:255] if exc is not None else None,
                    created_by=self.actor[:255],
                )
            )
        except Exception:  # tracking must never break the real call
            logger.warning("Could not record service call %s", self.name, exc_info=True)


def _start(func: Callable[..., Any], name: str | None, args: tuple[Any, ...]) -> _Call | None:
    if _suppressed.get() or not _sink().running:
        return None
    return _Call(name or _service_name(func, args))


def track_service(func: F | None = None, *, name: str | None = None) -> Any:
    """Decorate a sync or async function. Use bare (@track_service) or with a name."""

    def decorate(fn: F) -> F:
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                call = _start(fn, name, args)
                if call is None:
                    return await fn(*args, **kwargs)
                try:
                    result = await fn(*args, **kwargs)
                except BaseException as exc:
                    call.finish(exc)
                    raise
                call.finish(None)
                return result

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            call = _start(fn, name, args)
            if call is None:
                return fn(*args, **kwargs)
            try:
                result = fn(*args, **kwargs)
            except BaseException as exc:
                call.finish(exc)
                raise
            call.finish(None)
            return result

        return sync_wrapper  # type: ignore[return-value]

    return decorate(func) if func is not None else decorate
