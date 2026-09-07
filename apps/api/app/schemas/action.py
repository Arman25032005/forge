import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ActionCreate(BaseModel):
    action_type: str
    description: str = Field(min_length=1, max_length=2_000)
    parameters: dict[str, Any] = Field(default_factory=dict)
    decision_id: uuid.UUID | None = None


class ActionOut(BaseModel):
    id: uuid.UUID
    decision_id: uuid.UUID | None
    action_type: str
    description: str
    parameters: dict[str, Any]
    status: str
    proposed_by: uuid.UUID
    approved_by: uuid.UUID | None
    executed_at: datetime | None
    result: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}
