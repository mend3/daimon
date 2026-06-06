"""Node handler contract (Strategy). A handler declares its NodeType (palette
entry: category, ports, config fields) and implements run(). Flow nodes return
outputs + which flow port(s) fire next; resource nodes return a value injected into
the agent that depends on them."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


class FieldSpec(BaseModel):
    """One config field for the properties panel."""
    key: str
    label: str
    type: str = "text"              # text | textarea | number | select | boolean
    default: Any = None
    options: list[str] | None = None
    placeholder: str | None = None
    expects: str | None = None      # variable type this field wants (for UI validation):
    #                                 string|number|boolean|datetime|media|object|array


class ResourceSlot(BaseModel):
    name: str                       # e.g. "model", "memory", "knowledge", "tools"
    label: str
    accepts: list[str] = []         # node categories/types this slot accepts


class OutputField(BaseModel):
    """A field this node emits — used to offer downstream nodes the variables they
    can reference (`{{ node_id.field }}`) when filling their config. `type` is one of
    string|number|boolean|datetime|media|object|array; `object` fields nest via
    `fields` (each child reachable by a dotted path, resolved at run time)."""
    key: str
    type: str = "string"
    description: str = ""
    fields: list["OutputField"] = []   # children for object/array shapes


OutputField.model_rebuild()


class NodeType(BaseModel):
    type: str                       # unique id, e.g. "agent.ella"
    category: str                   # Triggers | Agents | Tools | Logic | Integrations | Outputs
    label: str
    icon: str = "●"
    description: str = ""
    flow_inputs: list[str] = ["in"]     # [] for triggers
    flow_outputs: list[str] = ["out"]   # multiple for branching (e.g. true/false)
    resource_slots: list[ResourceSlot] = []
    is_resource: bool = False           # resource nodes attach to slots, not the chain
    config_fields: list[FieldSpec] = []
    output_fields: list[OutputField] = []   # the shape of this node's output


@dataclass
class NodeResult:
    outputs: dict[str, Any] = field(default_factory=dict)   # port_name -> payload
    next_ports: list[str] | None = None                     # which flow outputs fire
    value: Any = None                                       # for resource nodes


@dataclass
class Services:
    """Shared capabilities injected into handlers (Ella's actual abilities)."""
    chat: Any = None          # OllamaChat
    kb: Any = None            # ella_kb.KnowledgeBase (lazy)
    http: Any = None          # httpx.Client
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class ExecContext:
    config: dict[str, Any]
    payload: Any                       # input from the incoming flow edge
    resources: dict[str, Any]          # slot name -> resolved resource value
    services: Services


class NodeHandler(ABC):
    node_type: NodeType

    @abstractmethod
    def run(self, ctx: ExecContext) -> NodeResult: ...
