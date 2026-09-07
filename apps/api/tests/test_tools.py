import uuid

import pytest

from app.models.enterprise import Customer, Document, DocumentChunk
from app.services.chunking import chunk_text
from app.services.embeddings import embed
from app.services.tools import TOOLS_BY_NAME, ToolExecutionError


@pytest.mark.asyncio
async def test_sql_query_tool_is_tenant_scoped(db_session) -> None:
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    db_session.add(Customer(organization_id=org_a, name="A Co"))
    db_session.add(Customer(organization_id=org_b, name="B Co"))
    await db_session.commit()

    tool = TOOLS_BY_NAME["sql_query"]
    rows = await tool.run(db_session, org_a, {"sql": "SELECT name FROM customers"})
    assert rows == [{"name": "A Co"}]


@pytest.mark.asyncio
async def test_sql_query_tool_rejects_disallowed_sql(db_session) -> None:
    tool = TOOLS_BY_NAME["sql_query"]
    with pytest.raises(ToolExecutionError):
        await tool.run(db_session, uuid.uuid4(), {"sql": "DROP TABLE customers"})


@pytest.mark.asyncio
async def test_sql_query_tool_requires_sql_argument(db_session) -> None:
    tool = TOOLS_BY_NAME["sql_query"]
    with pytest.raises(ToolExecutionError):
        await tool.run(db_session, uuid.uuid4(), {})


@pytest.mark.asyncio
async def test_retrieval_search_tool_finds_ingested_chunk(db_session) -> None:
    org_id = uuid.uuid4()
    document = Document(organization_id=org_id, title="Notes", content="churn risk analysis")
    db_session.add(document)
    await db_session.flush()
    for index, chunk in enumerate(chunk_text(document.content)):
        db_session.add(
            DocumentChunk(
                organization_id=org_id,
                document_id=document.id,
                chunk_index=index,
                content=chunk,
                embedding=embed(chunk),
            )
        )
    await db_session.commit()

    tool = TOOLS_BY_NAME["retrieval_search"]
    results = await tool.run(db_session, org_id, {"query": "churn risk", "top_k": 3})
    assert len(results) == 1
    assert results[0]["document_id"] == str(document.id)


@pytest.mark.asyncio
async def test_knowledge_graph_tool_requires_valid_entity_type(db_session) -> None:
    tool = TOOLS_BY_NAME["knowledge_graph_lookup"]
    with pytest.raises(ToolExecutionError):
        await tool.run(db_session, uuid.uuid4(), {"entity_type": "bogus", "entity_id": "x"})


@pytest.mark.asyncio
async def test_knowledge_graph_tool_returns_neighborhood(db_session) -> None:
    org_id = uuid.uuid4()
    customer = Customer(organization_id=org_id, name="Acme")
    db_session.add(customer)
    await db_session.commit()

    tool = TOOLS_BY_NAME["knowledge_graph_lookup"]
    result = await tool.run(
        db_session, org_id, {"entity_type": "customers", "entity_id": str(customer.id)}
    )
    assert result["nodes"][0]["id"] == str(customer.id)
