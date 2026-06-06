// Thin client for the Ella web backend.
const j = (r) => r.json();

export const api = {
  modules: () => fetch("/api/modules").then(j),
  knowledgeGraph: () => fetch("/api/knowledge/graph").then(j),
  feeds: () => fetch("/api/feeds").then(j),
  feedEntries: (limit = 20) => fetch(`/api/feeds/entries?limit=${limit}`).then(j),
  feedClusters: () => fetch("/api/feeds/clusters").then(j),
  subscribeFeed: (url) =>
    fetch("/api/feeds/subscribe", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ url }),
    }).then(j),
  processFeeds: (limit = 15) =>
    fetch(`/api/feeds/process?limit=${limit}`, { method: "POST" }).then(j),
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
  tts: (text) =>
    fetch("/api/tts", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text }),
    }).then((r) => (r.ok ? r.blob() : Promise.reject(new Error("tts failed")))),
  stt: (blob) => {
    const fd = new FormData();
    fd.append("file", blob, "recording.webm");
    return fetch("/api/stt", { method: "POST", body: fd })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("stt failed"))));
  },
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
