from pydantic import BaseModel


class GraphNode(BaseModel):
    type: str
    id: str
    label: str


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
