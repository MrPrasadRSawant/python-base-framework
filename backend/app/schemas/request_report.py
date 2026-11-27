"""Developer report: what happened in a request, why it failed, where time went."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Outcome = Literal["succeeded", "failed"]


class FailureReason(BaseModel):
    """Why the request failed, from exception_log (redacted)."""

    kind: Literal["client_error", "server_error"]  # 4xx / 5xx
    error_code: str | None
    exception_type: str | None
    message: str
    exception_log_id: uuid.UUID  # GET /api/v1/exception-logs/{id} for the traceback


class ServiceStep(BaseModel):
    """One tracked service call inside the request."""

    call_order: int | None
    parent_call_order: int | None  # NULL = called directly by the endpoint
    depth: int  # 0 = top level, 1 = called by a top-level service, ...
    service_name: str
    offset_ms: float  # when it started, relative to the request start
    duration_ms: float  # total, including services it called
    self_ms: float  # own time: duration minus the services it called
    percent_of_request: float
    status: str  # success / failed
    error_type: str | None
    is_slowest: bool  # highest self_ms in this request


class TimingSummary(BaseModel):
    request_ms: float
    in_services_ms: float  # sum of top-level service calls
    outside_services_ms: float  # routing, validation, endpoint code, serialization
    service_calls: int
    failed_service_calls: int
    slowest_service: str | None  # by own time
    slowest_service_ms: float | None


class RequestReport(BaseModel):
    """GET /api/v1/requests/{request_id}/report"""

    request_id: uuid.UUID
    started_on: datetime
    method: str
    route: str | None
    endpoint: str | None
    status_code: int
    outcome: Outcome
    failure: FailureReason | None
    timing: TimingSummary
    services: list[ServiceStep]  # in call order


class RequestReportSummary(BaseModel):
    """One row of POST /api/v1/requests/report"""

    request_id: uuid.UUID
    started_on: datetime
    method: str
    route: str | None
    status_code: int
    outcome: Outcome
    failure_reason: str | None  # "not_found: Exception log not found"
    duration_ms: float
    service_calls: int
    slowest_service: str | None
    slowest_service_ms: float | None
