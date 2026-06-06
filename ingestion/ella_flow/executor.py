"""Runs a Workflow. Walks the flow graph from the trigger; for each node it first
resolves the resources attached to its slots (dependencies, not steps), runs the
handler, records per-node state, and follows the activated flow output(s). An
optional on_event callback (Observer) streams state changes to the UI."""
from __future__ import annotations

import os
import re
import time
import uuid
from typing import Any, Callable

import httpx

_VAR = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")
_ROOT = re.compile(r"[^.\[\]]+")
_SEG = re.compile(r"\.([^.\[\]]+)|\[(\d+)\]")


def _walk_path(base: Any, rest: str) -> Any:
    """Follow `.key` and `[index]` segments into nested dicts/lists."""
    for m in _SEG.finditer(rest):
        if base is None:
            return None
        key, idx = m.group(1), m.group(2)
        if key is not None:
            base = base.get(key) if isinstance(base, dict) else None
        else:
            i = int(idx)
            base = base[i] if isinstance(base, list) and -len(base) <= i < len(base) else None
    return base


def _interpolate(config: Any, input_payload: Any, node_outputs: dict[str, Any]) -> Any:
    """Resolve {{ input.field }}, {{ nodeId.a.b }}, and {{ nodeId.list[0].x }} in
    config strings, using the incoming payload and earlier nodes' outputs."""
    def resolve(expr: str) -> str:
        m = _ROOT.match(expr)
        if not m:
            return ""
        root = m.group(0)
        base = input_payload if root == "input" else node_outputs.get(root)
        base = _walk_path(base, expr[m.end():])
        return "" if base is None else (base if isinstance(base, str) else str(base))

    def walk(v: Any) -> Any:
        if isinstance(v, str):
            return _VAR.sub(lambda m: resolve(m.group(1).strip()), v)
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items()}
        if isinstance(v, list):
            return [walk(x) for x in v]
        return v

    return walk(config)

from .chat_client import OllamaChat
from .model import Edge, Execution, NodeRun, NodeState, PortKind, Workflow
from .spec import ExecContext, Services
from .registry import REGISTRY, ensure_loaded, make_handler

EventFn = Callable[[str, NodeRun], None]
_ENV_KEYS = ("SEARXNG_URL", "TELEGRAM_BOT_TOKEN", "QDRANT_URL", "QDRANT_API_KEY", "OLLAMA_URL")


def _build_services() -> Services:
    kb = None
    try:
        from ella_kb.service import KnowledgeBase
        kb = KnowledgeBase()
    except Exception:
        kb = None
    return Services(
        chat=OllamaChat(),
        kb=kb,
        http=httpx.Client(headers={"user-agent": "ella-flow/0.1"}),
        env={k: os.environ[k] for k in _ENV_KEYS if k in os.environ},
    )


def _triggers(wf: Workflow):
    return [n for n in wf.nodes
            if n.type in REGISTRY and not REGISTRY[n.type].node_type.flow_inputs
            and not REGISTRY[n.type].node_type.is_resource]


def execute(wf: Workflow, trigger_payload: Any = None,
            on_event: EventFn | None = None, services: Services | None = None) -> Execution:
    ensure_loaded()
    services = services or _build_services()
    ex = Execution(id="ex_" + uuid.uuid4().hex[:12], workflow_id=wf.id,
                   started_at=int(time.time()), trigger_payload=trigger_payload)
    for n in wf.nodes:
        ex.runs[n.id] = NodeRun(node_id=n.id, state=NodeState.IDLE)

    def emit(node_id: str, state: NodeState, output: Any = None, error: str | None = None):
        run = ex.runs[node_id]
        run.state, run.output, run.error = state, output, error
        if on_event:
            on_event(ex.id, run)

    starts = _triggers(wf)
    if not starts:
        ex.status = "error"
        ex.finished_at = int(time.time())
        return ex

    node_outputs: dict[str, Any] = {}
    queue: list[tuple[str, Any]] = [(starts[0].id, trigger_payload)]
    try:
        while queue:
            node_id, payload = queue.pop(0)
            node = wf.node(node_id)
            if node is None or node.type not in REGISTRY:
                continue
            emit(node_id, NodeState.RUNNING)
            resources = _resolve_resources(wf, node_id, payload, services, emit, node_outputs)
            config = _interpolate(node.config, payload, node_outputs)
            ctx = ExecContext(config=config, payload=payload,
                              resources=resources, services=services)
            try:
                result = make_handler(node.type).run(ctx)
            except Exception as e:  # noqa: BLE001
                emit(node_id, NodeState.ERROR, error=str(e))
                ex.status = "error"
                continue
            emit(node_id, NodeState.SUCCESS, output=result.outputs)
            ports = result.next_ports or REGISTRY[node.type].node_type.flow_outputs[:1]
            node_outputs[node_id] = next(
                (result.outputs[p] for p in ports if p in result.outputs),
                next(iter(result.outputs.values()), None))
            for port in ports:
                for e in _flow_out(wf, node_id, port):
                    queue.append((e.target, result.outputs.get(port)))
    finally:
        services.http.close() if services.http else None

    ex.status = "error" if any(r.state == NodeState.ERROR for r in ex.runs.values()) else "success"
    ex.finished_at = int(time.time())
    return ex


def _flow_out(wf: Workflow, node_id: str, port: str) -> list[Edge]:
    return [e for e in wf.edges if e.kind == PortKind.FLOW
            and e.source == node_id and e.source_port == port]


def _resolve_resources(wf: Workflow, node_id: str, payload: Any,
                       services: Services, emit, node_outputs: dict[str, Any]) -> dict[str, Any]:
    resources: dict[str, Any] = {}
    for e in wf.resource_edges_into(node_id):
        rnode = wf.node(e.source)
        if rnode is None or rnode.type not in REGISTRY:
            continue
        emit(rnode.id, NodeState.RUNNING)
        config = _interpolate(rnode.config, payload, node_outputs)
        ctx = ExecContext(config=config, payload=payload, resources={}, services=services)
        try:
            res = make_handler(rnode.type).run(ctx)
            emit(rnode.id, NodeState.SUCCESS, output=res.value)
            resources[e.target_port] = res.value
        except Exception as ex:  # noqa: BLE001
            emit(rnode.id, NodeState.ERROR, error=str(ex))
    return resources
