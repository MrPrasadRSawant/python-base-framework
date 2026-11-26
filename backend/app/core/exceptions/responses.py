from datetime import UTC, datetime
from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.schemas.error import ErrorBody, ErrorResponse
from app.schemas.responses import ResponseMetadata


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: str | None,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build the standard error envelope. The request id is in the body *and* header."""
    body = ErrorResponse(
        metadata=ResponseMetadata(request_id=request_id, timestamp=datetime.now(UTC)),
        error=ErrorBody(code=code, message=message, details=details),
    )
    response_headers = dict(headers or {})
    if request_id:
        response_headers[settings.REQUEST_ID_HEADER] = request_id
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(body, exclude_none=True),
        headers=response_headers,
    )
