import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DecisionOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    conclusion: str
    confidence: float
    evidence: list[dict[str, Any]]
    recommended_actions: list[str]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
