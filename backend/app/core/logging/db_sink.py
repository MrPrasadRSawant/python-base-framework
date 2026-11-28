"""Non-blocking, batched writers for the log tables
(exception_log, request_logs, service_call_logs, user_activity_logs).

Requests never wait on the database to record a log row, and a database
outage never breaks a request:

    logging handler --enqueue()--> bounded asyncio.Queue --worker--> INSERT (batched)

* ``enqueue`` is synchronous and never raises: it can be called from the
  event loop or from threadpool threads (sync endpoints).
* When the queue is full, rows are dropped and counted (and a warning goes to
  the log files) instead of piling up in memory.
* Failed batches are retried one row at a time, so one bad row doesn't sink
  the rest. Failures are written to the log files only, never back to a
  sink, which avoids an infinite loop when the database itself is down.
* ``stop`` flushes whatever is queued before shutdown.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

Writer = Callable[[Sequence[Any]], Awaitable[None]]

# Records from this logger are never persisted (loop guard in the DB handlers).
SINK_LOGGER_NAME = "app.db_log_sink"
logger = logging.getLogger(SINK_LOGGER_NAME)

_STOP = object()


class DBLogSink:
    def __init__(
        self,
        name: str,
        writer: Writer,
        *,
        max_queue: int = 10_000,
        batch_size: int = 50,
        flush_interval: float = 1.0,
    ) -> None:
        self.name = name
        self._writer = writer
        self.max_queue = max_queue
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._queue: asyncio.Queue | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task | None = None
        self.dropped = 0
        self.written = 0
        self.failed = 0

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    # ------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        if self.running:
            return
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue(maxsize=self.max_queue)
        self._task = asyncio.create_task(self._run(), name=f"{self.name}-sink")
        logger.info("%s sink started", self.name)

    async def stop(self, timeout: float = 5.0) -> None:
        if not self.running:
            return
        assert self._queue is not None and self._task is not None
        await self._queue.put(_STOP)
        try:
            await asyncio.wait_for(self._task, timeout)
        except TimeoutError:
            self._task.cancel()
            logger.warning("%s sink did not flush within %.1fs", self.name, timeout)
        logger.info(
            "%s sink stopped (written=%d failed=%d dropped=%d)",
            self.name,
            self.written,
            self.failed,
            self.dropped,
        )
        self._task = None
        self._queue = None
        self._loop = None

    # -------------------------------------------------------------- producer
    def enqueue(self, row: Any) -> None:
        loop = self._loop
        if loop is None or not self.running:
            self.dropped += 1
            return
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        if running_loop is loop:
            self._put(row)
        else:  # called from a worker thread
            loop.call_soon_threadsafe(self._put, row)

    def _put(self, row: Any) -> None:
        if self._queue is None:
            self.dropped += 1
            return
        try:
            self._queue.put_nowait(row)
        except asyncio.QueueFull:
            self.dropped += 1
            if self.dropped % 100 == 1:
                logger.warning("%s queue full; dropped %d row(s)", self.name, self.dropped)

    # -------------------------------------------------------------- consumer
    async def _run(self) -> None:
        assert self._queue is not None
        queue = self._queue
        stopping = False
        while not stopping:
            first = await queue.get()
            if first is _STOP:
                break
            batch: list[Any] = [first]
            deadline = asyncio.get_running_loop().time() + self.flush_interval
            while len(batch) < self.batch_size:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), remaining)
                except TimeoutError:
                    break
                if item is _STOP:
                    stopping = True
                    break
                batch.append(item)
            await self._write(batch)

        # Flush anything still queued at shutdown.
        leftovers = []
        while not queue.empty():
            item = queue.get_nowait()
            if item is not _STOP:
                leftovers.append(item)
        for start in range(0, len(leftovers), self.batch_size):
            await self._write(leftovers[start : start + self.batch_size])

    async def _write(self, batch: list[Any]) -> None:
        try:
            await self._writer(batch)
            self.written += len(batch)
            return
        except Exception:
            if len(batch) == 1:
                self.failed += 1
                logger.warning("Failed to persist %s row", self.name, exc_info=True)
                return
        # Batch failed: retry row by row so one bad row doesn't lose the others.
        for row in batch:
            try:
                await self._writer([row])
                self.written += 1
            except Exception:
                self.failed += 1
                logger.warning("Failed to persist %s row", self.name, exc_info=True)


# --------------------------------------------------------------------- writers
# Lazy imports avoid a cycle (logging is set up before the DB layer loads).
# Each batch uses its own session: the request's may have been rolled back.
# Tracking is suppressed so saving log rows never creates service_call_logs rows.


async def _save(service_path: str, service_class: str, rows: Sequence[Any]) -> None:
    import importlib

    from app.core.service_tracking import suppress_service_tracking
    from app.db.session import SessionLocal

    service = getattr(importlib.import_module(service_path), service_class)
    with suppress_service_tracking():
        async with SessionLocal() as session:
            await service(session).create_many(list(rows))


async def _write_exception_logs(rows: Sequence[Any]) -> None:
    await _save("app.services.exception_log", "ExceptionLogService", rows)


async def _write_request_logs(rows: Sequence[Any]) -> None:
    await _save("app.services.request_log", "RequestLogService", rows)


async def _write_service_call_logs(rows: Sequence[Any]) -> None:
    await _save("app.services.service_call_log", "ServiceCallLogService", rows)


async def _write_user_activity_logs(rows: Sequence[Any]) -> None:
    await _save("app.services.user_activity_log", "UserActivityLogService", rows)


exception_log_sink = DBLogSink("exception_log", _write_exception_logs)
request_log_sink = DBLogSink("request_logs", _write_request_logs)
service_call_log_sink = DBLogSink("service_call_logs", _write_service_call_logs)
user_activity_log_sink = DBLogSink("user_activity_logs", _write_user_activity_logs)
ALL_SINKS = (exception_log_sink, request_log_sink, service_call_log_sink, user_activity_log_sink)
