"""Resource nodes attach to an agent's slots (dotted edges) rather than the main
chain. They expose a `value` the agent uses: a model choice, a knowledge lookup, a
web search tool. This is the "tools are dependencies, not steps" principle."""
from __future__ import annotations

from ..registry import node
from ..spec import ExecContext, FieldSpec, NodeHandler, NodeResult, NodeType


@node
class ModelResource(NodeHandler):
    node_type = NodeType(
        type="resource.model", category="Tools", label="Chat Model", icon="🧠",
        is_resource=True, flow_inputs=[], flow_outputs=[],
        description="The local model the agent thinks with.",
        config_fields=[FieldSpec(key="model", label="Model", type="select",
                                 default="gpt-oss:20b", options=["gpt-oss:20b"])],
    )

    def run(self, ctx: ExecContext) -> NodeResult:
        return NodeResult(value={"kind": "model", "model": ctx.config.get("model", "gpt-oss:20b")})


@node
class KnowledgeResource(NodeHandler):
    node_type = NodeType(
        type="resource.knowledge", category="Tools", label="Knowledge", icon="📚",
        is_resource=True, flow_inputs=[], flow_outputs=[],
        description="Recall relevant passages from Daimon's memory to ground the answer.",
        config_fields=[FieldSpec(key="scope", label="Scope (source types, comma-sep)", type="text",
                                 placeholder="files,urls,chat")],
    )

    def run(self, ctx: ExecContext) -> NodeResult:
        scope = [s.strip() for s in (ctx.config.get("scope") or "").split(",") if s.strip()] or None
        query = _text(ctx.payload)
        hits = []
        if ctx.services.kb and query:
            hits = ctx.services.kb.recall(query, scope=scope, top_k=5)
        context = "\n\n".join(f"[{i}] {h.title} — {h.uri or h.source_type}\n{h.text}"
                              for i, h in enumerate(hits, 1))
        return NodeResult(value={"kind": "knowledge", "context": context,
                                 "citations": [{"title": h.title, "uri": h.uri} for h in hits]})


@node
class WebSearchResource(NodeHandler):
    node_type = NodeType(
        type="resource.web_search", category="Tools", label="Web Search", icon="🔎",
        is_resource=True, flow_inputs=[], flow_outputs=[],
        description="Search the web (local SearXNG) to ground the answer.",
        config_fields=[FieldSpec(key="max_results", label="Max results", type="number", default=3)],
    )

    def run(self, ctx: ExecContext) -> NodeResult:
        query = _text(ctx.payload)
        url = ctx.services.env.get("SEARXNG_URL", "http://searxng:8080")
        results = []
        if ctx.services.http and query:
            try:
                r = ctx.services.http.get(f"{url}/search",
                                          params={"q": query, "format": "json"}, timeout=10)
                r.raise_for_status()
                n = int(ctx.config.get("max_results", 3))
                results = [{"title": x.get("title"), "url": x.get("url"), "content": x.get("content")}
                           for x in r.json().get("results", [])[:n]]
            except Exception:
                results = []
        context = "\n\n".join(f"{x['title']} — {x['url']}\n{x.get('content','')}" for x in results)
        return NodeResult(value={"kind": "web_search", "context": context, "results": results})


def _text(payload) -> str:
    if isinstance(payload, dict):
        return payload.get("text") or payload.get("query") or ""
    return payload or ""
