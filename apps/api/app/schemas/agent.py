import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentRunCreate(BaseModel):
    question: str = Field(min_length=1, max_length=4_000)


class AgentStepOut(BaseModel):
    step_index: int
    thought: str | None
    tool_name: str | None
    tool_input: dict[str, Any] | None
    tool_output: Any

    model_config = {"from_attributes": True}


class AgentRunOut(BaseModel):
    id: uuid.UUID
    question: str
    status: str
    final_answer: str | None
    created_at: datetime
    steps: list[AgentStepOut] = []

    model_config = {"from_attributes": True}
