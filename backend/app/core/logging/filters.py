import logging

from app.core.request_context import get_request_id


class RequestIdFilter(logging.Filter):
    """Stamp every record with the current request id (``-`` outside a request).

    Attached to *handlers* (not loggers) so records propagated from any
    library logger are covered too. An explicit ``extra={"request_id": ...}``
    always wins.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            record.request_id = get_request_id() or "-"
        return True
