"""Logic nodes branch the flow. IF routes to its `true` or `false` flow output."""
from __future__ import annotations

import operator

from ..registry import node
from ..spec import ExecContext, FieldSpec, NodeHandler, NodeResult, NodeType, OutputField

_OPS = {
    "contains": lambda a, b: b.lower() in a.lower(),
    "not_contains": lambda a, b: b.lower() not in a.lower(),
    "equals": lambda a, b: a.strip() == b.strip(),
    "not_empty": lambda a, b: bool(a.strip()),
}


@node
class IfNode(NodeHandler):
    node_type = NodeType(
        type="logic.if", category="Logic", label="If", icon="🔀",
        description="Branch on a simple condition over the incoming text.",
        flow_inputs=["in"], flow_outputs=["true", "false"],
        output_fields=[OutputField(key="text", description="The input, passed through")],
        config_fields=[
            FieldSpec(key="operator", label="Condition", type="select", default="contains",
                      options=list(_OPS)),
            FieldSpec(key="value", label="Value", type="text"),
        ],
    )

    def run(self, ctx: ExecContext) -> NodeResult:
        raw = ctx.payload.get("text") if isinstance(ctx.payload, dict) else ctx.payload
        text = str(raw or "")
        op = _OPS.get(ctx.config.get("operator", "contains"), operator.contains)
        result = bool(op(text, ctx.config.get("value", "")))
        port = "true" if result else "false"
        return NodeResult(outputs={port: ctx.payload}, next_ports=[port])
