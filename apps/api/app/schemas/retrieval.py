import uuid

from pydantic import BaseModel, Field


class RetrievalQuery(BaseModel):
    query: str = Field(min_length=1, max_length=2_000)
    top_k: int = Field(default=5, ge=1, le=50)
    customer_id: uuid.UUID | None = None


class RetrievalResult(BaseModel):
    document_id: uuid.UUID
    document_title: str
    chunk_index: int
    content: str
    score: float


class RetrievalResponse(BaseModel):
    results: list[RetrievalResult]
