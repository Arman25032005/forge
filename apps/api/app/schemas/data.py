from pydantic import BaseModel, Field


class SQLQueryRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=10_000)


class SQLQueryResponse(BaseModel):
    rows: list[dict]
    row_count: int
