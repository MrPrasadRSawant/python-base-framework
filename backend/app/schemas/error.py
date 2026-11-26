from typing import Any

from pydantic import BaseModel

from app.schemas.responses import ResponseMetadata


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    """Shape of every error response: ``{"metadata": {...}, "error": {...}}``."""

    metadata: ResponseMetadata
    error: ErrorBody
