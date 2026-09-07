"""A relationship graph over enterprise entities, built on demand.

There is no separate graph store here — nodes and edges are derived
straight from the existing tenant-scoped relational tables (customers,
subscriptions, transactions, support tickets, contracts, invoices,
documents) by walking known foreign keys. That keeps it consistent with
the SQL tool's data by construction and avoids a second copy of the data
to keep in sync, at the cost of not supporting graph-native queries (e.g.
shortest path across many hops) efficiently — this is breadth-first over a
handful of tenant-scoped queries per depth, fine for the small
neighborhoods this is used for (a customer and its handful of related
records), not for whole-graph analytics.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enterprise import (
    Contract,
    Customer,
    Document,
    Invoice,
    Product,
    Subscription,
    SupportTicket,
    Transaction,
)

MAX_NODES = 200

# (entity_type, foreign-key attribute on that entity, entity_type it points to)
_RELATIONS: list[tuple[str, str, str]] = [
    ("subscriptions", "customer_id", "customers"),
    ("subscriptions", "product_id", "products"),
    ("transactions", "customer_id", "customers"),
    ("support_tickets", "customer_id", "customers"),
    ("contracts", "customer_id", "customers"),
    ("invoices", "customer_id", "customers"),
    ("documents", "customer_id", "customers"),
]

_MODELS: dict[str, type[Any]] = {
    "customers": Customer,
    "products": Product,
    "subscriptions": Subscription,
    "transactions": Transaction,
    "support_tickets": SupportTicket,
    "contracts": Contract,
    "invoices": Invoice,
    "documents": Document,
}

ENTITY_TYPES = frozenset(_MODELS)


def _label(entity_type: str, row: Any) -> str:
    for attr in ("name", "title", "subject", "plan"):
        value = getattr(row, attr, None)
        if value is not None:
            return str(value)
    return f"{entity_type}:{row.id}"


@dataclass
class Node:
    type: str
    id: str
    label: str


@dataclass
class Edge:
    source: str
    target: str
    relation: str


@dataclass
class Graph:
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)

    def add_node(self, entity_type: str, row: Any) -> str:
        key = f"{entity_type}:{row.id}"
        if key not in self.nodes:
            self.nodes[key] = Node(type=entity_type, id=str(row.id), label=_label(entity_type, row))
        return key

    def add_edge(self, source: str, target: str, relation: str) -> None:
        self.edges.append(Edge(source=source, target=target, relation=relation))


async def _row_by_id(
    db: AsyncSession, entity_type: str, entity_id: uuid.UUID, organization_id: uuid.UUID
) -> Any | None:
    model = _MODELS[entity_type]
    result: Result[Any] = await db.execute(
        select(model).where(model.id == entity_id, model.organization_id == organization_id)
    )
    return result.scalar_one_or_none()


async def _neighbors(
    db: AsyncSession, entity_type: str, entity_id: uuid.UUID, organization_id: uuid.UUID
) -> list[tuple[str, Any, str]]:
    """Rows directly connected to (entity_type, entity_id), each tagged
    with its entity type and the relation name that connects it."""
    found: list[tuple[str, Any, str]] = []

    for from_type, fk_attr, to_type in _RELATIONS:
        model = _MODELS[from_type]
        if from_type == entity_type:
            # Outgoing edge: this entity -> the thing its FK points at.
            row = await _row_by_id(db, entity_type, entity_id, organization_id)
            if row is not None:
                target_id = getattr(row, fk_attr)
                target_row = await _row_by_id(db, to_type, target_id, organization_id)
                if target_row is not None:
                    found.append((to_type, target_row, fk_attr))
        if to_type == entity_type:
            # Incoming edges: every row of `from_type` whose FK points here.
            result: Result[Any] = await db.execute(
                select(model).where(
                    getattr(model, fk_attr) == entity_id,
                    model.organization_id == organization_id,
                )
            )
            for row in result.scalars().all():
                found.append((from_type, row, fk_attr))

    return found


async def get_neighborhood(
    db: AsyncSession,
    organization_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    depth: int = 1,
) -> Graph | None:
    if entity_type not in _MODELS:
        raise ValueError(f"unknown entity type: {entity_type}")

    root = await _row_by_id(db, entity_type, entity_id, organization_id)
    if root is None:
        return None

    graph = Graph()
    root_key = graph.add_node(entity_type, root)

    frontier = [(entity_type, entity_id)]
    visited = {root_key}

    for _ in range(depth):
        next_frontier: list[tuple[str, uuid.UUID]] = []
        for current_type, current_id in frontier:
            if len(graph.nodes) >= MAX_NODES:
                break
            current_key = f"{current_type}:{current_id}"
            for neighbor_type, neighbor_row, relation in await _neighbors(
                db, current_type, current_id, organization_id
            ):
                neighbor_key = graph.add_node(neighbor_type, neighbor_row)
                graph.add_edge(current_key, neighbor_key, relation)
                if neighbor_key not in visited:
                    visited.add(neighbor_key)
                    next_frontier.append((neighbor_type, neighbor_row.id))
        frontier = next_frontier
        if len(graph.nodes) >= MAX_NODES:
            break

    return graph
