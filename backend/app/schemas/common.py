import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditRead(BaseModel):
    """Common read fields for every table using AuditMixin."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_by: str
    created_on: datetime
    updated_by: str | None = None
    updated_on: datetime | None = None
