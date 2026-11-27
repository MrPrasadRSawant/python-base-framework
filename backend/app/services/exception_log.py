from app.models import ExceptionLog
from app.schemas.search import SortDirection
from app.services.base import AUDIT_FIELDS, BaseService


class ExceptionLogService(BaseService):
    model = ExceptionLog
    filter_fields = (
        "request_id",
        "status_code",
        "error_code",
        "exception_type",
        "level",
        "logger",
        "method",
        "path",
        "route",
        "endpoint",
        "environment",
        "hostname",
        "occurred_on",
        *AUDIT_FIELDS,
    )
    sort_fields = ("occurred_on", "created_on", "status_code", "error_code", "exception_type")
    search_fields = ("message", "path", "exception_type", "error_code")
    default_sort = (("occurred_on", SortDirection.DESC),)
