"""FastAPI app: node catalog, workflow CRUD, live run (WebSocket), executions, and
chat-with-Ella. The frontend (React Flow canvas) talks to these."""
from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from typing import Any

import httpx
import yaml
from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
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


# ----- speak: turn text into audio via the local TTS engine -----
def _tts_settings() -> dict:
    """Reuse Hermes' tts.openai config (synced into ~/.hermes/config.yaml) so the
    web voice matches Telegram's; fall back to the local Kokoro defaults."""
    cfg = {"base_url": "http://host.docker.internal:8880/v1", "model": "kokoro",
           "voice": "af_sky", "api_key": "local"}
    p = Path("~/.hermes/config.yaml").expanduser()
    if p.exists():
        try:
            tts = (yaml.safe_load(p.read_text()) or {}).get("tts", {}).get("openai", {})
            cfg.update({k: tts[k] for k in ("base_url", "model", "voice", "api_key") if k in tts})
        except Exception:
            pass
    return cfg


class TtsReq(BaseModel):
    text: str


@app.post("/api/tts")
def tts(req: TtsReq) -> Response:
    s = _tts_settings()
    r = httpx.post(f"{s['base_url'].rstrip('/')}/audio/speech",
                   headers={"authorization": f"Bearer {s['api_key']}"},
                   json={"model": s["model"], "voice": s["voice"],
                         "input": req.text[:4000], "response_format": "mp3"}, timeout=120)
    r.raise_for_status()
    return Response(content=r.content, media_type="audio/mpeg")


# ----- listen: transcribe a recorded clip with the local STT (faster-whisper) -----
_whisper = None


def _stt_model():
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        root = os.path.expanduser("~/.hermes/cache/whisper")
        os.makedirs(root, exist_ok=True)
        _whisper = WhisperModel(os.environ.get("STT_MODEL", "base"),
                                device="cpu", compute_type="int8", download_root=root)
    return _whisper


@app.post("/api/stt")
async def stt(file: UploadFile = File(...)) -> dict:
    import tempfile
    data = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(data)
        path = tmp.name

    def _transcribe() -> str:
        segments, _info = _stt_model().transcribe(path, vad_filter=True)
        return "".join(s.text for s in segments).strip()

    try:
        text = await asyncio.to_thread(_transcribe)
    finally:
        os.unlink(path)
    return {"text": text}


# ----- modules: which features are enabled (plug-and-play, future per tier/user) -----
_MODULE_META = {
    "workflows": {"id": "workflows", "label": "Workflows", "icon": "🧩"},
    "knowledge": {"id": "knowledge", "label": "Knowledge", "icon": "🕸"},
    "feeds": {"id": "feeds", "label": "Feeds", "icon": "📰"},
}


@app.get("/api/modules")
def modules() -> list[dict]:
    enabled = [m.strip() for m in
               os.environ.get("ELLA_MODULES", "workflows,knowledge,feeds").split(",") if m.strip()]
    return [_MODULE_META[m] for m in enabled if m in _MODULE_META]


# ----- feeds: collection, browsing, and AI categorization into the RAG -----
@app.get("/api/feeds")
def feeds_list() -> list[dict]:
    from .feeds import MinifluxClient
    try:
        return MinifluxClient().feeds()
    except Exception:
        return []


@app.get("/api/feeds/entries")
def feeds_entries(limit: int = 20) -> list[dict]:
    from .feeds import MinifluxClient, _HTML
    try:
        return [{"id": e["id"], "title": e.get("title"), "url": e.get("url"),
                 "feed": (e.get("feed") or {}).get("title"),
                 "preview": _HTML.sub(" ", e.get("content", "")).strip()[:240]}
                for e in MinifluxClient().unread(limit)]
    except Exception:
        return []


class SubscribeReq(BaseModel):
    url: str


@app.post("/api/feeds/subscribe")
def feeds_subscribe(req: SubscribeReq) -> dict:
    from .feeds import MinifluxClient
    try:
        return MinifluxClient().subscribe(req.url)
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


@app.post("/api/feeds/process")
async def feeds_process(limit: int = 15) -> dict:
    from .feeds import process
    return await asyncio.to_thread(process, limit)


@app.get("/api/feeds/clusters")
def feeds_clusters() -> dict:
    from .feeds import clusters
    return clusters()


# ----- knowledge graph: sources as nodes, semantic neighbours as edges -----
@app.get("/api/knowledge/graph")
def knowledge_graph(neighbors: int = 4, min_score: float = 0.6, limit: int = 400) -> dict:
    from ella_kb.service import KnowledgeBase
    return KnowledgeBase().graph(neighbors=neighbors, min_score=min_score, limit=limit)


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
