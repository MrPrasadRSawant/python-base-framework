# Import every model here so Alembic autogenerate can discover them.
from app.models.exception_log import ExceptionLog
from app.models.request_log import RequestLog

__all__ = ["ExceptionLog", "RequestLog"]
