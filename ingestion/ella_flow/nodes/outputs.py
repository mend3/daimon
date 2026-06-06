"""Output (sink) nodes deliver the result: return it to the caller, POST it to an
HTTP endpoint, send it to Telegram, or save it to Ella's knowledge base."""
from __future__ import annotations

from ..registry import node
from ..spec import ExecContext, FieldSpec, NodeHandler, NodeResult, NodeType, OutputField


def _text(payload) -> str:
    if isinstance(payload, dict):
        return payload.get("text") or str(payload)
    return str(payload or "")


@node
class ReturnOutput(NodeHandler):
    node_type = NodeType(
        type="output.return", category="Outputs", label="Return", icon="🏁",
        description="Return the result to whoever ran the workflow.",
        flow_inputs=["in"], flow_outputs=[],
    )

    def run(self, ctx: ExecContext) -> NodeResult:
        return NodeResult(outputs={"result": ctx.payload}, value=ctx.payload)


@node
class HttpOutput(NodeHandler):
    node_type = NodeType(
        type="output.http", category="Outputs", label="HTTP Request", icon="📤",
        description="POST the result to a URL.",
        flow_inputs=["in"], flow_outputs=["out"],
        config_fields=[FieldSpec(key="url", label="URL", type="text", expects="string",
                                 placeholder="https://…")],
        output_fields=[OutputField(key="status", type="number")],
    )

    def run(self, ctx: ExecContext) -> NodeResult:
        url = ctx.config.get("url", "")
        status = None
        if url and ctx.services.http:
            r = ctx.services.http.post(url, json={"text": _text(ctx.payload)}, timeout=15)
            status = r.status_code
        return NodeResult(outputs={"out": {"status": status}})


@node
class TelegramOutput(NodeHandler):
    node_type = NodeType(
        type="output.telegram", category="Outputs", label="Telegram", icon="✈️",
        description="Send a message (optionally with media) to a Telegram chat. Fill "
                    "Chat ID with a variable like {{ trigger.chat_id }} to reply to the sender.",
        flow_inputs=["in"], flow_outputs=["out"],
        config_fields=[
            FieldSpec(key="chat_id", label="Chat ID", type="text", expects="string",
                      placeholder="{{ trigger.chat_id }}"),
            FieldSpec(key="text", label="Message", type="textarea", expects="string",
                      placeholder="Leave empty to send the incoming text"),
            FieldSpec(key="media_url", label="Media URL (optional)", type="text", expects="media",
                      placeholder="{{ trigger.media.url }}"),
        ],
        output_fields=[OutputField(key="sent", type="boolean"),
                       OutputField(key="message_id", type="number")],
    )

    def run(self, ctx: ExecContext) -> NodeResult:
        token = ctx.services.env.get("TELEGRAM_BOT_TOKEN", "")
        chat_id = ctx.config.get("chat_id") or ""
        text = ctx.config.get("text") or _text(ctx.payload)
        media = ctx.config.get("media_url") or ""
        sent, message_id = False, None
        if token and chat_id and ctx.services.http:
            if media:
                r = ctx.services.http.post(
                    f"https://api.telegram.org/bot{token}/sendPhoto",
                    json={"chat_id": chat_id, "photo": media, "caption": text}, timeout=20)
            else:
                r = ctx.services.http.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": text}, timeout=15)
            sent = r.is_success
            if sent:
                message_id = r.json().get("result", {}).get("message_id")
        return NodeResult(outputs={"out": {"sent": sent, "message_id": message_id}})


@node
class SaveOutput(NodeHandler):
    node_type = NodeType(
        type="output.save", category="Outputs", label="Save to Memory", icon="💾",
        description="Save the result to Ella's knowledge base.",
        flow_inputs=["in"], flow_outputs=[],
        config_fields=[FieldSpec(key="title", label="Title", type="text")],
    )

    def run(self, ctx: ExecContext) -> NodeResult:
        saved = False
        if ctx.services.kb:
            ctx.services.kb.capture(text=_text(ctx.payload), title=ctx.config.get("title") or None)
            saved = True
        return NodeResult(outputs={"saved": saved})
