"""Developer reports built from requests + service_call_logs + exception_log.

Not a BaseService: a report reads three tables joined on the request id.
The timing maths is a pure function (``build_report``) so it is easy to test.
"""

import uuid
from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.service_tracking import track_service
from app.db.search import SearchResult
from app.models import ExceptionLog, RequestLog, ServiceCallLog
from app.schemas.request_report import (
    FailureReason,
    RequestReport,
    RequestReportSummary,
    ServiceStep,
    TimingSummary,
)
from app.schemas.search import SearchRequest
from app.services.request_log import RequestLogService

EXCEPTIONS_LOGGER = "app.exceptions"  # rows written for the API error response


def _pick_failure(request: RequestLog, exceptions: Sequence[ExceptionLog]) -> FailureReason | None:
    if request.status_code < 400:
        return None
    if not exceptions:
        return None
    # Prefer the row that produced the API error response, else the latest one.
    main = next((e for e in exceptions if e.logger == EXCEPTIONS_LOGGER), exceptions[-1])
    return FailureReason(
        kind="server_error" if request.status_code >= 500 else "client_error",
        error_code=main.error_code,
        exception_type=main.exception_type,
        message=main.message,
        exception_log_id=main.id,
    )


def build_report(
    request: RequestLog,
    calls: Sequence[ServiceCallLog],
    exceptions: Sequence[ExceptionLog],
) -> RequestReport:
    calls = sorted(calls, key=lambda c: (c.call_order is None, c.call_order or 0))
    request_ms = request.duration_ms

    children_ms: dict[int | None, float] = defaultdict(float)
    for call in calls:
        if call.parent_call_order is not None:
            children_ms[call.parent_call_order] += call.duration_ms
    parent_of = {c.call_order: c.parent_call_order for c in calls}

    def depth(order: int | None) -> int:
        level, seen = 0, set()
        while (parent := parent_of.get(order)) is not None and parent not in seen:
            seen.add(parent)
            level, order = level + 1, parent
        return level

    steps = []
    for call in calls:
        self_ms = max(call.duration_ms - children_ms.get(call.call_order, 0.0), 0.0)
        offset_ms = (call.started_on - request.started_on).total_seconds() * 1000
        steps.append(
            ServiceStep(
                call_order=call.call_order,
                parent_call_order=call.parent_call_order,
                depth=depth(call.call_order),
                service_name=call.service_name,
                offset_ms=round(max(offset_ms, 0.0), 3),
                duration_ms=call.duration_ms,
                self_ms=round(self_ms, 3),
                percent_of_request=round(call.duration_ms / request_ms * 100, 1)
                if request_ms
                else 0,
                status=call.status,
                error_type=call.error_type,
                is_slowest=False,
            )
        )

    slowest = max(steps, key=lambda s: s.self_ms, default=None)
    if slowest is not None:
        slowest.is_slowest = True
    in_services = sum(c.duration_ms for c in calls if c.parent_call_order is None)

    return RequestReport(
        request_id=request.id,
        started_on=request.started_on,
        method=request.method,
        route=request.route,
        endpoint=request.endpoint,
        status_code=request.status_code,
        outcome="failed" if request.status_code >= 400 else "succeeded",
        failure=_pick_failure(request, exceptions),
        timing=TimingSummary(
            request_ms=request_ms,
            in_services_ms=round(in_services, 3),
            # Concurrent calls (asyncio.gather) can overlap, so clamp at zero.
            outside_services_ms=round(max(request_ms - in_services, 0.0), 3),
            service_calls=len(calls),
            failed_service_calls=sum(c.status == "failed" for c in calls),
            slowest_service=slowest.service_name if slowest else None,
            slowest_service_ms=slowest.self_ms if slowest else None,
        ),
        services=steps,
    )


def summarize(report: RequestReport) -> RequestReportSummary:
    failure = report.failure
    return RequestReportSummary(
        request_id=report.request_id,
        started_on=report.started_on,
        method=report.method,
        route=report.route,
        status_code=report.status_code,
        outcome=report.outcome,
        failure_reason=(
            f"{failure.error_code or failure.exception_type}: {failure.message}"[:500]
            if failure
            else None
        ),
        duration_ms=report.timing.request_ms,
        service_calls=report.timing.service_calls,
        slowest_service=report.timing.slowest_service,
        slowest_service_ms=report.timing.slowest_service_ms,
    )


class RequestReportService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _related(self, request_ids: list[uuid.UUID]):
        calls = (
            await self.db.scalars(
                select(ServiceCallLog)
                .where(ServiceCallLog.request_id.in_(request_ids))
                .order_by(ServiceCallLog.call_order)
            )
        ).all()
        exceptions = (
            await self.db.scalars(
                select(ExceptionLog)
                .where(ExceptionLog.request_id.in_(request_ids))
                .order_by(ExceptionLog.occurred_on)
            )
        ).all()
        calls_by, exceptions_by = defaultdict(list), defaultdict(list)
        for call in calls:
            calls_by[call.request_id].append(call)
        for exc in exceptions:
            exceptions_by[exc.request_id].append(exc)
        return calls_by, exceptions_by

    @track_service
    async def get_report(self, request_id: uuid.UUID) -> RequestReport | None:
        request = await RequestLogService(self.db).get(request_id)
        if request is None:
            return None
        calls_by, exceptions_by = await self._related([request.id])
        return build_report(request, calls_by[request.id], exceptions_by[request.id])

    @track_service
    async def list_reports(self, search: SearchRequest) -> SearchResult:
        """Same filters/sort/paging as POST /requests/search; records become summaries."""
        request_logs = RequestLogService(self.db)
        result = await request_logs.search(search)
        if search.include_total:
            matching, _ = request_logs.build_query(search)
            matching_requests = matching.subquery()
            average = await self.db.scalar(
                select(func.avg(matching_requests.c.duration_ms)).select_from(matching_requests)
            )
            result.average_duration_ms = float(average) if average is not None else 0.0
        ids = [r.id for r in result.records]
        calls_by, exceptions_by = await self._related(ids) if ids else ({}, {})
        result.records = [
            summarize(build_report(r, calls_by.get(r.id, []), exceptions_by.get(r.id, [])))
            for r in result.records
        ]
        return result
