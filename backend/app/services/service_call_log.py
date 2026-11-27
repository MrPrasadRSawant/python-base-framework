from app.models import ServiceCallLog
from app.schemas.search import SortDirection
from app.services.base import AUDIT_FIELDS, BaseService


class ServiceCallLogService(BaseService):
    model = ServiceCallLog
    filter_fields = (
        "request_id",
        "call_order",
        "parent_call_order",
        "service_name",
        "started_on",
        "duration_ms",
        "status",
        "error_type",
        *AUDIT_FIELDS,
    )
    sort_fields = ("started_on", "call_order", "duration_ms", "service_name")
    search_fields = ("service_name", "error_type")
    default_sort = (("started_on", SortDirection.DESC),)
