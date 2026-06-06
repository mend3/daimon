import { Handle, Position } from "@xyflow/react";

const STATE_COLOR = {
  idle: "#3a3a44",
  running: "#d9a40a",
  success: "#3fb950",
  error: "#f85149",
  skipped: "#6e7681",
};

// A node renders handles from its catalog spec: a flow input (left), flow output(s)
// (right), resource slots evenly spread along the bottom (target), and — for
// resource nodes — a single output on top.
export default function FlowNode({ data, selected }) {
  const spec = data.spec;
  const state = data.state || "idle";
  const flowOut = spec.flow_outputs || [];
  const slots = spec.resource_slots || [];
  const slotPct = (i) => ((i + 0.5) / slots.length) * 100;

  return (
    <div
      className="flow-node"
      style={{
        minWidth: slots.length ? Math.max(210, slots.length * 96) : 180,
        borderColor: selected ? "#58a6ff" : STATE_COLOR[state],
        boxShadow: state === "running" ? "0 0 0 3px rgba(217,164,10,.25)" : "none",
      }}
    >
      <div className="flow-node-head">
        <span className="flow-node-icon">{spec.icon}</span>
        <span className="flow-node-title">{data.name || spec.label}</span>
        <span className="flow-node-dot" style={{ background: STATE_COLOR[state] }} />
      </div>
      <div className="flow-node-cat">{spec.category}</div>

      {slots.length > 0 && (
        <div className="slot-row">
          {slots.map((slot) => (
            <span key={slot.name} className="slot-label" title={slot.label}>{slot.label}</span>
          ))}
        </div>
      )}

      {spec.flow_inputs?.length > 0 && (
        <Handle type="target" position={Position.Left} id="in" />
      )}

      {flowOut.map((port, i) => (
        <Handle key={port} type="source" position={Position.Right} id={port}
                style={flowOut.length > 1 ? { top: 30 + i * 20 } : undefined}>
          {flowOut.length > 1 && <span className="port-label">{port}</span>}
        </Handle>
      ))}

      {spec.is_resource && <Handle type="source" position={Position.Top} id="res-out" />}

      {slots.map((slot, i) => (
        <Handle key={slot.name} className="slot-handle" type="target" position={Position.Bottom}
                id={`res:${slot.name}`} style={{ left: `${slotPct(i)}%` }} />
      ))}
    </div>
  );
}
