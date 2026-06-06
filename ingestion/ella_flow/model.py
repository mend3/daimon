"""Graph data model: nodes, edges, workflows, and execution records.

Ports come in two kinds. FLOW ports chain execution (Node → Node). RESOURCE ports
attach dependencies to a node without putting them in the main chain
(Tool/Memory/Knowledge → Agent) — this is what keeps the canvas readable as the
agent gains capabilities."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class PortKind(str, Enum):
    FLOW = "flow"
    RESOURCE = "resource"


class NodeState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"


class Position(BaseModel):
    x: float = 0
    y: float = 0


class Node(BaseModel):
    id: str
    type: str                       # matches a NodeType in the catalog
    name: str = ""
    position: Position = Field(default_factory=Position)
    config: dict[str, Any] = Field(default_factory=dict)


class Edge(BaseModel):
    id: str
    source: str                     # source node id
    source_port: str = "out"        # named output port (e.g. "true"/"false" for IF)
    target: str                     # target node id
    target_port: str = "in"         # named input port (e.g. a resource slot)
    kind: PortKind = PortKind.FLOW


class Workflow(BaseModel):
    id: str
    name: str = "Untitled"
    tags: list[str] = Field(default_factory=list)
    active: bool = False
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)

    def node(self, node_id: str) -> Node | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    def flow_edges(self) -> list[Edge]:
        return [e for e in self.edges if e.kind == PortKind.FLOW]

    def resource_edges_into(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.kind == PortKind.RESOURCE and e.target == node_id]


class NodeRun(BaseModel):
    node_id: str
    state: NodeState = NodeState.IDLE
    output: Any = None
    error: str | None = None


class Execution(BaseModel):
    id: str
    workflow_id: str
    status: Literal["running", "success", "error"] = "running"
    started_at: int = 0
    finished_at: int | None = None
    runs: dict[str, NodeRun] = Field(default_factory=dict)
    trigger_payload: Any = None
