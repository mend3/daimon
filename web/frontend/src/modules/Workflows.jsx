import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ReactFlow, Background, Controls, MiniMap,
  addEdge, useNodesState, useEdgesState, MarkerType,
} from "@xyflow/react";
import { api, runWorkflow } from "../api";
import FlowNode from "../components/FlowNode.jsx";
import Palette from "../components/Palette.jsx";
import Properties from "../components/Properties.jsx";

const nodeTypes = { ella: FlowNode };
let idSeq = 1;

// First port's payload — what a node effectively passes downstream.
const primaryPayload = (outputs) => (outputs ? outputs[Object.keys(outputs)[0]] : undefined);

// Flatten a (possibly nested) output schema into dotted paths with type + sample.
// Object fields recurse (each child is reachable by `nodeId.a.b`); arrays/leaves
// are inserted whole.
function flattenFields(fields, sampleObj, prefix = "") {
  const out = [];
  for (const f of fields || []) {
    const path = prefix ? `${prefix}.${f.key}` : f.key;
    const sample = sampleObj && typeof sampleObj === "object" ? sampleObj[f.key] : undefined;
    if (f.type === "object" && f.fields?.length) {
      out.push(...flattenFields(f.fields, sample, path));
    } else if (f.type === "array" && f.fields?.length) {
      out.push({ path, type: "array", sample });
      const idxs = Array.isArray(sample) && sample.length ? sample.map((_, i) => i).slice(0, 3) : [0];
      for (const i of idxs) {
        const item = Array.isArray(sample) ? sample[i] : undefined;
        out.push(...flattenFields(f.fields, item, `${path}[${i}]`));
      }
    } else {
      out.push({ path, type: f.type, sample });
    }
  }
  return out;
}

// All nodes upstream of `id` via flow edges (closest-first not guaranteed).
function flowAncestors(id, edges) {
  const incoming = (n) =>
    edges.filter((e) => (e.data?.kind || "flow") === "flow" && e.target === n).map((e) => e.source);
  const seen = new Set();
  const stack = [...incoming(id)];
  while (stack.length) {
    const cur = stack.pop();
    if (seen.has(cur)) continue;
    seen.add(cur);
    incoming(cur).forEach((s) => stack.push(s));
  }
  return [...seen];
}

export default function Workflows() {
  const [catalog, setCatalog] = useState([]);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [wf, setWf] = useState({ id: "", name: "Untitled", active: false });
  const [tab, setTab] = useState("editor");
  const [testInput, setTestInput] = useState("Summarize the latest on local AI agents.");
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [executions, setExecutions] = useState([]);
  const [lastOutputs, setLastOutputs] = useState({});   // nodeId -> outputs (last run)
  const specByType = useRef({});

  useEffect(() => {
    api.catalog().then((c) => {
      setCatalog(c);
      specByType.current = Object.fromEntries(c.map((n) => [n.type, n]));
    });
  }, []);

  const addNode = (spec) => {
    const id = `n${idSeq++}`;
    setNodes((ns) => ns.concat({
      id, type: "ella",
      position: { x: 180 + Math.random() * 240, y: 120 + Math.random() * 240 },
      data: { spec, config: {}, name: "", state: "idle" },
    }));
  };

  const onConnect = useCallback((params) => {
    const kind = params.targetHandle?.startsWith("res:") ? "resource" : "flow";
    setEdges((es) => addEdge({
      ...params,
      data: { kind },
      animated: kind === "flow",
      style: kind === "resource"
        ? { stroke: "#8b5cf6", strokeDasharray: "5 4" }
        : { stroke: "#58a6ff" },
      markerEnd: { type: MarkerType.ArrowClosed },
    }, es));
  }, [setEdges]);

  const updateSelected = (config, name) => {
    setNodes((ns) => ns.map((n) =>
      n.id === selectedId
        ? { ...n, data: { ...n.data, config, name: name !== undefined ? name : n.data.name } }
        : n));
  };
  const deleteSelected = () => {
    setNodes((ns) => ns.filter((n) => n.id !== selectedId));
    setEdges((es) => es.filter((e) => e.source !== selectedId && e.target !== selectedId));
    setSelectedId(null);
  };

  const serialize = () => ({
    id: wf.id || "wf_temp", name: wf.name, active: wf.active,
    nodes: nodes.map((n) => ({
      id: n.id, type: n.data.spec.type, name: n.data.name || "",
      position: n.position, config: n.data.config || {},
    })),
    edges: edges.map((e) => {
      const kind = e.data?.kind || "flow";
      return {
        id: e.id, source: e.source, target: e.target, kind,
        source_port: e.sourceHandle || "out",
        target_port: kind === "resource" ? (e.targetHandle || "").slice(4) : (e.targetHandle || "in"),
      };
    }),
  });

  const save = async () => {
    const saved = await api.saveWorkflow(serialize());
    setWf((w) => ({ ...w, id: saved.id }));
  };

  const setNodeState = (nodeId, state) =>
    setNodes((ns) => ns.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, state } } : n)));

  const run = () => {
    setResult(null);
    setRunning(true);
    setNodes((ns) => ns.map((n) => ({ ...n, data: { ...n.data, state: "idle" } })));
    runWorkflow(serialize(), { text: testInput }, {
      onNode: (run) => {
        setNodeState(run.node_id, run.state);
        if (run.output) setLastOutputs((m) => ({ ...m, [run.node_id]: run.output }));
      },
      onDone: (ex) => {
        setRunning(false);
        const ret = Object.values(ex.runs).find((r) => r.output && r.output.result);
        setResult(ret?.output?.result || ex.status);
      },
      onError: () => setRunning(false),
    });
  };

  const openExecutions = async () => {
    setTab("executions");
    if (wf.id) setExecutions(await api.executions(wf.id));
  };

  const selected = nodes.find((n) => n.id === selectedId) || null;

  // Variables a selected node can reference: each upstream node's output fields
  // (from its schema) plus the sample value from the last run, if any.
  const variables = useMemo(() => {
    if (!selectedId) return [];
    return flowAncestors(selectedId, edges)
      .map((id) => {
        const n = nodes.find((x) => x.id === id);
        if (!n) return null;
        const sample = primaryPayload(lastOutputs[id]);
        const fields = flattenFields(n.data.spec.output_fields || [], sample);
        return fields.length ? { nodeId: id, nodeName: n.data.name || n.data.spec.label, fields } : null;
      })
      .filter(Boolean);
  }, [selectedId, edges, nodes, lastOutputs]);

  return (
    <div className="wf">
      <header className="topbar">
        <input className="wf-name" value={wf.name}
               onChange={(e) => setWf((w) => ({ ...w, name: e.target.value }))} />
        <div className="tabs">
          <button className={tab === "editor" ? "on" : ""} onClick={() => setTab("editor")}>Editor</button>
          <button className={tab === "executions" ? "on" : ""} onClick={openExecutions}>Executions</button>
        </div>
        <label className="active-toggle">
          <input type="checkbox" checked={wf.active}
                 onChange={(e) => setWf((w) => ({ ...w, active: e.target.checked }))} />
          {wf.active ? "Active" : "Inactive"}
        </label>
        <div className="run-box">
          <input value={testInput} onChange={(e) => setTestInput(e.target.value)} placeholder="Test input…" />
          <button className="run-btn" onClick={run} disabled={running}>{running ? "Running…" : "▶ Run"}</button>
          <button onClick={save}>Save</button>
        </div>
      </header>

      <div className="wf-body">
        {tab === "editor" && <Palette catalog={catalog} onAdd={addNode} />}

        <main className="canvas">
          {tab === "editor" ? (
            <ReactFlow
              nodes={nodes} edges={edges} nodeTypes={nodeTypes}
              onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
              onSelectionChange={({ nodes: sel }) => setSelectedId(sel?.[0]?.id ?? null)}
              fitView proOptions={{ hideAttribution: true }}>
              <Background variant="dots" gap={18} size={1} />
              <Controls />
              <MiniMap pannable zoomable />
            </ReactFlow>
          ) : (
            <div className="executions">
              <h3>Executions</h3>
              {executions.length === 0 && <p className="muted">No runs yet. Save, then Run.</p>}
              {executions.map((ex) => (
                <div key={ex.id} className={`exec exec-${ex.status}`}>
                  <span>{ex.id}</span><span className="exec-status">{ex.status}</span>
                  <span className="muted">{Object.values(ex.runs).filter((r) => r.state === "success").length} ok</span>
                </div>
              ))}
            </div>
          )}
          {result && <div className="result"><b>Result</b>: {typeof result === "string" ? result : (result.text || JSON.stringify(result))}</div>}
        </main>

        {tab === "editor" && (
          <Properties node={selected} variables={variables}
                      onChange={updateSelected} onDelete={deleteSelected} />
        )}
      </div>
    </div>
  );
}
