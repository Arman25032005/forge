"""The tools an agent run may invoke.

Each tool wraps an existing, independently-tested capability (the SQL
tool, retrieval search, the knowledge graph) rather than introducing new
data-access logic — the agent runtime's job is orchestration and
permission enforcement, not reimplementing those.
"""

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission
from app.services import knowledge_graph, retrieval
from app.services.sql_tool import SQLValidationError, execute_sql_tool


class ToolExecutionError(Exception):
    """A tool ran but failed for a reason the caller (and the agent) should
    see, e.g. invalid arguments — distinct from a permission failure."""


class ToolRunner(Protocol):
    async def __call__(
        self, db: AsyncSession, organization_id: uuid.UUID, arguments: dict[str, Any]
    ) -> Any: ...


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    permission: str
    run: ToolRunner


async def _run_sql_query(
    db: AsyncSession, organization_id: uuid.UUID, arguments: dict[str, Any]
) -> Any:
    sql = arguments.get("sql")
    if not isinstance(sql, str) or not sql.strip():
        raise ToolExecutionError("'sql' argument is required")
    try:
        return await execute_sql_tool(db, raw_sql=sql, organization_id=organization_id)
    except SQLValidationError as exc:
        raise ToolExecutionError(str(exc)) from exc


async def _run_retrieval_search(
    db: AsyncSession, organization_id: uuid.UUID, arguments: dict[str, Any]
) -> Any:
    query = arguments.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ToolExecutionError("'query' argument is required")
    customer_id_raw = arguments.get("customer_id")
    customer_id = uuid.UUID(customer_id_raw) if customer_id_raw else None
    results = await retrieval.search_chunks(
        db,
        organization_id=organization_id,
        query=query,
        top_k=int(arguments.get("top_k", 5)),
        customer_id=customer_id,
    )
    return [r.model_dump(mode="json") for r in results]


async def _run_knowledge_graph_lookup(
    db: AsyncSession, organization_id: uuid.UUID, arguments: dict[str, Any]
) -> Any:
    entity_type = arguments.get("entity_type")
    entity_id_raw = arguments.get("entity_id")
    if entity_type not in knowledge_graph.ENTITY_TYPES or not entity_id_raw:
        raise ToolExecutionError("'entity_type' and 'entity_id' are required")
    try:
        entity_id = uuid.UUID(str(entity_id_raw))
    except ValueError as exc:
        raise ToolExecutionError(f"invalid entity_id: {entity_id_raw}") from exc

    graph = await knowledge_graph.get_neighborhood(
        db,
        organization_id,
        entity_type,
        entity_id,
        depth=int(arguments.get("depth", 1)),
    )
    if graph is None:
        raise ToolExecutionError(f"no {entity_type} found with id {entity_id}")
    return {
        "nodes": [vars(n) for n in graph.nodes.values()],
        "edges": [vars(e) for e in graph.edges],
    }


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="sql_query",
        description=(
            "Run a read-only SQL SELECT against the organization's enterprise data "
            "(customers, products, subscriptions, transactions, support_tickets, "
            "contracts, invoices, employees, documents). Automatically scoped to "
            "the caller's own tenant."
        ),
        input_schema={
            "type": "object",
            "properties": {"sql": {"type": "string", "description": "A single SELECT statement"}},
            "required": ["sql"],
        },
        permission=Permission.DATA_QUERY,
        run=_run_sql_query,
    ),
    ToolSpec(
        name="retrieval_search",
        description="Semantic search over ingested documents for the caller's tenant.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
                "customer_id": {"type": "string", "description": "Optional customer UUID filter"},
            },
            "required": ["query"],
        },
        permission=Permission.DOCUMENT_READ,
        run=_run_retrieval_search,
    ),
    ToolSpec(
        name="knowledge_graph_lookup",
        description=(
            "Look up the entities connected to a given customer, subscription, "
            "product, transaction, support_ticket, contract, invoice, or document."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "entity_type": {"type": "string", "enum": sorted(knowledge_graph.ENTITY_TYPES)},
                "entity_id": {"type": "string"},
                "depth": {"type": "integer", "default": 1},
            },
            "required": ["entity_type", "entity_id"],
        },
        permission=Permission.DATA_QUERY,
        run=_run_knowledge_graph_lookup,
    ),
]

TOOLS_BY_NAME: dict[str, ToolSpec] = {tool.name: tool for tool in TOOLS}
