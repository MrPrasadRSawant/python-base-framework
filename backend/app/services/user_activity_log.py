from app.models import UserActivityLog
from app.schemas.search import SortDirection
from app.services.base import AUDIT_FIELDS, BaseService


class UserActivityLogService(BaseService):
    model = UserActivityLog
    filter_fields = (
        "occurred_on",
        "actor",
        "actor_type",
        "actor_id",
        "action",
        "status",
        "entity_type",
        "entity_id",
        "request_id",
        "method",
        "route",
        "ip_address",
        *AUDIT_FIELDS,
    )
    sort_fields = ("occurred_on", "action", "actor", "entity_type", "status")
    search_fields = ("actor", "action", "entity_type", "entity_id", "route", "ip_address")
    search_cast_fields = ("request_id",)
    default_sort = (("occurred_on", SortDirection.DESC),)
