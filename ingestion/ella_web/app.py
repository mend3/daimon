"""FastAPI app: node catalog, workflow CRUD, live run (WebSocket), executions, and
chat-with-Ella. The frontend (React Flow canvas) talks to these."""
from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ella_flow.executor import execute
from ella_flow.model import Workflow
from ella_flow.registry import catalog
from ella_flow.store import FlowStore

app = FastAPI(title="Ella Web")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
store = FlowStore()


# ----- node catalog (the palette + properties schema) -----
@app.get("/api/catalog")
def get_catalog() -> list[dict]:
    return [nt.model_dump(mode="json") for nt in catalog()]


# ----- workflows CRUD -----
@app.get("/api/workflows")
def list_workflows() -> list[dict]:
    return [w.model_dump(mode="json") for w in store.list_workflows()]


@app.get("/api/workflows/{wf_id}")
def get_workflow(wf_id: str) -> dict | None:
    wf = store.get_workflow(wf_id)
    return wf.model_dump(mode="json") if wf else None


@app.post("/api/workflows")
def save_workflow(wf: Workflow) -> dict:
    if not wf.id:
        wf.id = "wf_" + uuid.uuid4().hex[:12]
    store.save_workflow(wf)
    return wf.model_dump(mode="json")


@app.delete("/api/workflows/{wf_id}")
def delete_workflow(wf_id: str) -> dict:
    return {"deleted": store.delete_workflow(wf_id)}


@app.get("/api/workflows/{wf_id}/executions")
def list_executions(wf_id: str) -> list[dict]:
    return [e.model_dump(mode="json") for e in store.list_executions(wf_id)]


# ----- run a workflow once (non-streaming) -----
class RunReq(BaseModel):
    workflow: Workflow
    payload: Any = None


@app.post("/api/run")
def run_once(req: RunReq) -> dict:
    ex = execute(req.workflow, req.payload)
    store.save_execution(ex)
    return ex.model_dump(mode="json")


# ----- run with live per-node state streaming -----
@app.websocket("/ws/run")
async def ws_run(ws: WebSocket) -> None:
    await ws.accept()
    try:
        req = await ws.receive_json()
        wf = Workflow(**req["workflow"])
        payload = req.get("payload")
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def on_event(_ex_id: str, run) -> None:
            loop.call_soon_threadsafe(
                queue.put_nowait, {"type": "node", "node": run.model_dump(mode="json")})

        async def runner() -> None:
            ex = await asyncio.to_thread(execute, wf, payload, on_event)
            store.save_execution(ex)
            await queue.put({"type": "done", "execution": ex.model_dump(mode="json")})

        task = asyncio.create_task(runner())
        while True:
            msg = await queue.get()
            await ws.send_json(msg)
            if msg["type"] == "done":
                break
        await task
    except WebSocketDisconnect:
        pass


# ----- chat with Ella (grounded by her knowledge base) -----
class ChatReq(BaseModel):
    message: str
    use_knowledge: bool = True


@app.post("/api/chat")
def chat(req: ChatReq) -> dict:
    from ella_flow.chat_client import OllamaChat, soul_prompt

    citations, grounding = [], ""
    if req.use_knowledge:
        try:
            from ella_kb.service import KnowledgeBase
            hits = KnowledgeBase().recall(req.message, top_k=5)
            grounding = "\n\n".join(f"[{i}] {h.title} — {h.uri or h.source_type}\n{h.text}"
                                    for i, h in enumerate(hits, 1))
            citations = [{"title": h.title, "uri": h.uri} for h in hits]
        except Exception:
            pass
    prompt = req.message
    if grounding:
        prompt = (f"Use this from the user's memory; cite when you rely on it:\n{grounding}\n\n"
                  f"Question: {req.message}")
    reply = OllamaChat().complete(prompt, system=soul_prompt())
    return {"reply": reply, "citations": citations}


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


# ----- serve the built frontend if present -----
_static = os.environ.get("ELLA_WEB_STATIC")
if _static and Path(_static).is_dir():
    app.mount("/", StaticFiles(directory=_static, html=True), name="static")


def main() -> None:
    import uvicorn
    uvicorn.run(app, host=os.environ.get("ELLA_WEB_HOST", "0.0.0.0"),
                port=int(os.environ.get("ELLA_WEB_PORT", "8099")))


if __name__ == "__main__":
    main()
