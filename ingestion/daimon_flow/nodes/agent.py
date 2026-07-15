"""The Daimon agent node — the centerpiece. It thinks with a model and is grounded by
whatever resources are attached to its slots (knowledge, web search, …). Resources
are dependencies injected here, not steps in the chain."""
from __future__ import annotations

from ..chat_client import soul_prompt
from ..registry import node
from ..spec import (ExecContext, FieldSpec, NodeHandler, NodeResult, NodeType,
                    OutputField, ResourceSlot)


@node
class DaimonAgent(NodeHandler):
    node_type = NodeType(
        type="agent.daimon", category="Agents", label="Daimon", icon="🤖",
        description="Daimon reasons over the input, grounded by her attached capabilities.",
        flow_inputs=["in"], flow_outputs=["out"],
        resource_slots=[
            ResourceSlot(name="model", label="Chat Model", accepts=["resource.model"]),
            ResourceSlot(name="knowledge", label="Knowledge", accepts=["resource.knowledge"]),
            ResourceSlot(name="tools", label="Tools", accepts=["resource.web_search"]),
        ],
        config_fields=[
            FieldSpec(key="instruction", label="Instruction", type="textarea",
                      placeholder="e.g. Summarize this for a busy reader and flag any risks."),
        ],
        output_fields=[
            OutputField(key="text", type="string", description="Daimon's answer"),
            OutputField(key="citations", type="array", description="Sources used", fields=[
                OutputField(key="title", type="string"),
                OutputField(key="uri", type="string"),
            ]),
        ],
    )

    def run(self, ctx: ExecContext) -> NodeResult:
        text = ctx.payload.get("text") if isinstance(ctx.payload, dict) else (ctx.payload or "")
        instruction = ctx.config.get("instruction", "").strip()

        grounding, citations = [], []
        for value in ctx.resources.values():
            if not isinstance(value, dict):
                continue
            if value.get("context"):
                grounding.append(value["context"])
            citations.extend(value.get("citations", []))

        model = next((v.get("model") for v in ctx.resources.values()
                      if isinstance(v, dict) and v.get("kind") == "model"), None)

        parts = []
        if instruction:
            parts.append(instruction)
        if grounding:
            parts.append("Use this context; cite sources when you rely on them:\n"
                         + "\n\n".join(grounding))
        parts.append(f"Input:\n{text}")
        prompt = "\n\n".join(parts)

        answer = ctx.services.chat.complete(prompt, system=soul_prompt(), model=model)
        return NodeResult(outputs={"out": {"text": answer, "citations": citations}})
