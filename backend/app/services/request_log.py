from app.models import RequestLog
from app.schemas.search import SortDirection
from app.services.base import AUDIT_FIELDS, BaseService


class RequestLogService(BaseService):
    model = RequestLog
    filter_fields = (
        "method",
        "route",
        "endpoint",
        "status_code",
        "duration_ms",
        "started_on",
        *AUDIT_FIELDS,
    )
    sort_fields = ("started_on", "duration_ms", "status_code", "route")
    search_fields = ("route", "endpoint")
    default_sort = (("started_on", SortDirection.DESC),)
