import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=2_000_000)
    source: str = Field(default="upload", max_length=255)
    customer_id: uuid.UUID | None = None


class DocumentOut(BaseModel):
    id: uuid.UUID
    title: str
    source: str
    customer_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
