// Thin client for the Ella web backend.
const j = (r) => r.json();

export const api = {
  catalog: () => fetch("/api/catalog").then(j),
  listWorkflows: () => fetch("/api/workflows").then(j),
  saveWorkflow: (wf) =>
    fetch("/api/workflows", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(wf),
    }).then(j),
  executions: (id) => fetch(`/api/workflows/${id}/executions`).then(j),
  chat: (message, useKnowledge = true) =>
    fetch("/api/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ message, use_knowledge: useKnowledge }),
    }).then(j),
};

// Run a workflow over the WebSocket, streaming per-node states.
export function runWorkflow(workflow, payload, { onNode, onDone, onError }) {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/run`);
  ws.onopen = () => ws.send(JSON.stringify({ workflow, payload }));
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "node") onNode?.(msg.node);
    else if (msg.type === "done") {
      onDone?.(msg.execution);
      ws.close();
    }
  };
  ws.onerror = () => onError?.();
  return ws;
}
