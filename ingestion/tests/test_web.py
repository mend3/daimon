import os
import uuid

import pytest
from fastapi.testclient import TestClient

from ella_web.app import app

client = TestClient(app)

BRANCH_WF = {
    "id": "", "name": "branch-test",
    "nodes": [
        {"id": "t", "type": "trigger.manual"},
        {"id": "iff", "type": "logic.if", "config": {"operator": "contains", "value": "urgent"}},
        {"id": "yes", "type": "output.return"},
        {"id": "no", "type": "output.return"},
    ],
    "edges": [
        {"id": "e1", "source": "t", "source_port": "out", "target": "iff", "target_port": "in"},
        {"id": "e2", "source": "iff", "source_port": "true", "target": "yes", "target_port": "in"},
        {"id": "e3", "source": "iff", "source_port": "false", "target": "no", "target_port": "in"},
    ],
}


def test_modules():
    r = client.get("/api/modules")
    assert r.status_code == 200
    ids = {m["id"] for m in r.json()}
    assert {"workflows", "knowledge"} <= ids


def test_catalog():
    r = client.get("/api/catalog")
    assert r.status_code == 200
    types = {n["type"] for n in r.json()}
    assert {"agent.ella", "trigger.manual", "logic.if", "output.return"} <= types


def test_workflow_crud_and_run():
    wf = dict(BRANCH_WF, id=f"wf_{uuid.uuid4().hex[:8]}")
    assert client.post("/api/workflows", json=wf).status_code == 200
    assert any(w["id"] == wf["id"] for w in client.get("/api/workflows").json())

    ex = client.post("/api/run", json={"workflow": wf, "payload": {"text": "this is urgent"}}).json()
    assert ex["status"] == "success"
    assert ex["runs"]["yes"]["state"] == "success"
    assert ex["runs"]["no"]["state"] == "idle"

    assert client.delete(f"/api/workflows/{wf['id']}").json()["deleted"] is True


def test_ws_run_streams_states():
    wf = dict(BRANCH_WF, id=f"wf_{uuid.uuid4().hex[:8]}")
    with client.websocket_connect("/ws/run") as ws:
        ws.send_json({"workflow": wf, "payload": {"text": "not important"}})
        seen_states, done = [], None
        while True:
            msg = ws.receive_json()
            if msg["type"] == "node":
                seen_states.append((msg["node"]["node_id"], msg["node"]["state"]))
            elif msg["type"] == "done":
                done = msg["execution"]
                break
    assert done["status"] == "success"
    assert done["runs"]["no"]["state"] == "success"   # false branch taken
    assert ("iff", "running") in seen_states and ("iff", "success") in seen_states


@pytest.mark.skipif(os.environ.get("ELLA_KB_IT") != "1", reason="needs live Ollama")
def test_chat_live():
    r = client.post("/api/chat", json={"message": "Say hi in one word.", "use_knowledge": False})
    assert r.status_code == 200 and r.json()["reply"].strip()
