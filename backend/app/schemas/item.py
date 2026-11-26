from pydantic import BaseModel

from app.schemas.common import AuditRead


class ItemBase(BaseModel):
    name: str
    description: str | None = None


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ItemRead(AuditRead, ItemBase):
    pass
