"""Non-blocking, batched writer for the exception_log table.

Requests never wait on the database to record an error, and a database
outage never breaks a request:

    logging handler --enqueue()--> bounded asyncio.Queue --worker--> INSERT (batched)

* ``enqueue`` is synchronous and never raises: it can be called from the
  event loop or from threadpool threads (sync endpoints).
* When the queue is full, rows are dropped and counted (and a warning goes to
  the log files) instead of piling up in memory.
* Failed batches are retried one row at a time, so one bad row doesn't sink
  the rest. Failures are written to the log files only, never back to this
  sink, which avoids an infinite loop when the database itself is down.
* ``stop`` flushes whatever is queued before shutdown.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

Row = dict[str, Any]
Writer = Callable[[Sequence[Row]], Awaitable[None]]

# Records from this logger are never persisted (see ExceptionLogDBHandler).
SINK_LOGGER_NAME = "app.exception_log_sink"
logger = logging.getLogger(SINK_LOGGER_NAME)

_STOP = object()


async def _default_writer(rows: Sequence[Row]) -> None:
    from app.repositories.exception_log import insert_exception_logs

    await insert_exception_logs(rows)


class ExceptionLogSink:
    def __init__(
        self,
        writer: Writer | None = None,
        *,
        max_queue: int = 10_000,
        batch_size: int = 50,
        flush_interval: float = 1.0,
    ) -> None:
        self._writer = writer or _default_writer
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
        self._task = asyncio.create_task(self._run(), name="exception-log-sink")
        logger.info("Exception log sink started")

    async def stop(self, timeout: float = 5.0) -> None:
        if not self.running:
            return
        assert self._queue is not None and self._task is not None
        await self._queue.put(_STOP)
        try:
            await asyncio.wait_for(self._task, timeout)
        except TimeoutError:
            self._task.cancel()
            logger.warning("Exception log sink did not flush within %.1fs", timeout)
        logger.info(
            "Exception log sink stopped (written=%d failed=%d dropped=%d)",
            self.written,
            self.failed,
            self.dropped,
        )
        self._task = None
        self._queue = None
        self._loop = None

    # -------------------------------------------------------------- producer
    def enqueue(self, row: Row) -> None:
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

    def _put(self, row: Row) -> None:
        if self._queue is None:
            self.dropped += 1
            return
        try:
            self._queue.put_nowait(row)
        except asyncio.QueueFull:
            self.dropped += 1
            if self.dropped % 100 == 1:
                logger.warning(
                    "Exception log queue full; dropped %d row(s) so far", self.dropped
                )

    # -------------------------------------------------------------- consumer
    async def _run(self) -> None:
        assert self._queue is not None
        queue = self._queue
        stopping = False
        while not stopping:
            first = await queue.get()
            if first is _STOP:
                break
            batch: list[Row] = [first]
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

    async def _write(self, batch: list[Row]) -> None:
        try:
            await self._writer(batch)
            self.written += len(batch)
            return
        except Exception:
            if len(batch) == 1:
                self.failed += 1
                logger.warning("Failed to persist exception log row", exc_info=True)
                return
        # Batch failed: retry row by row so one bad row doesn't lose the others.
        for row in batch:
            try:
                await self._writer([row])
                self.written += 1
            except Exception:
                self.failed += 1
                logger.warning("Failed to persist exception log row", exc_info=True)


exception_log_sink = ExceptionLogSink()
