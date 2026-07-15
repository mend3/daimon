"""Trigger nodes start a run. They have no flow input; their output is the trigger
payload (a chat message, a webhook body, etc.)."""
from __future__ import annotations

from ..registry import node
from ..spec import ExecContext, FieldSpec, NodeHandler, NodeResult, NodeType, OutputField


@node
class ManualTrigger(NodeHandler):
    node_type = NodeType(
        type="trigger.manual", category="Triggers", label="Manual / Test", icon="⚡",
        description="Start the workflow with a text input (used by the Test button).",
        flow_inputs=[], flow_outputs=["out"],
        config_fields=[FieldSpec(key="text", label="Test input", type="textarea",
                                 placeholder="Type something to run with…")],
        output_fields=[OutputField(key="text", description="The input text")],
    )

    def run(self, ctx: ExecContext) -> NodeResult:
        p = ctx.payload
        text = p.get("text", "") if isinstance(p, dict) else (str(p) if p else ctx.config.get("text", ""))
        return NodeResult(outputs={"out": {"text": text}})


@node
class WebhookTrigger(NodeHandler):
    node_type = NodeType(
        type="trigger.webhook", category="Triggers", label="Webhook", icon="🌐",
        description="Start when an external service posts JSON.",
        flow_inputs=[], flow_outputs=["out"],
        output_fields=[OutputField(key="text"), OutputField(key="title"), OutputField(key="url")],
    )

    def run(self, ctx: ExecContext) -> NodeResult:
        return NodeResult(outputs={"out": ctx.payload or {}})


@node
class TelegramTrigger(NodeHandler):
    node_type = NodeType(
        type="trigger.telegram", category="Triggers", label="Telegram Message", icon="✈️",
        description="Start when a Telegram message arrives. Exposes who sent it, the "
                    "text, and any media — so downstream nodes can reply to that user.",
        flow_inputs=[], flow_outputs=["out"],
        output_fields=[
            OutputField(key="chat_id", type="string", description="Where to reply"),
            OutputField(key="text", type="string"),
            OutputField(key="from", type="object", description="Sender", fields=[
                OutputField(key="id", type="number"),
                OutputField(key="username", type="string"),
                OutputField(key="name", type="string"),
            ]),
            OutputField(key="media", type="object", fields=[
                OutputField(key="kind", type="string", description="photo|document|voice|none"),
                OutputField(key="url", type="media"),
            ]),
            OutputField(key="timestamp", type="datetime"),
        ],
    )

    def run(self, ctx: ExecContext) -> NodeResult:
        p = ctx.payload if isinstance(ctx.payload, dict) else {"text": ctx.payload or ""}
        out = {
            "chat_id": p.get("chat_id"),
            "text": p.get("text", ""),
            "from": p.get("from") or {"id": p.get("user_id"), "username": p.get("username"),
                                      "name": p.get("name")},
            "media": p.get("media") or {"kind": "none", "url": None},
            "timestamp": p.get("timestamp"),
        }
        return NodeResult(outputs={"out": out})


@node
class ChatTrigger(NodeHandler):
    node_type = NodeType(
        type="trigger.chat", category="Triggers", label="Chat Message", icon="💬",
        description="Start when the user sends a chat message.",
        flow_inputs=[], flow_outputs=["out"],
        output_fields=[OutputField(key="text", description="The user's message")],
    )

    def run(self, ctx: ExecContext) -> NodeResult:
        text = ctx.payload.get("text") if isinstance(ctx.payload, dict) else ctx.payload
        return NodeResult(outputs={"out": {"text": text or ""}})
