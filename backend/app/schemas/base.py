"""Base classes for table schemas. Every table follows the same naming:

    <Entity>Create    request body for POST        (inherits CreateSchema)
    <Entity>Update    request body for PATCH       (inherits UpdateSchema)
    <Entity>Response  one record in any response   (inherits ResponseSchema)

POST /search uses the shared ``SearchRequest`` from schemas/search.py.

Responses are always wrapped in the standard envelopes from schemas/responses.py:
``RecordResponse[<Entity>Response]`` or ``ListResponse[<Entity>Response]``.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CreateSchema(BaseModel):
    """Input for creating a record. Unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class UpdateSchema(BaseModel):
    """Input for partially updating a record.

    Declare every field optional (``name: str | None = None``). Only the fields
    the client actually sent are applied (``model_dump(exclude_unset=True)``).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResponseSchema(BaseModel):
    """Output for one record. Read from ORM objects; includes the common columns."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_by: str
    created_on: datetime
    updated_by: str | None = None
    updated_on: datetime | None = None
