import { useEffect, useState } from "react";

// Right-hand properties panel: edits the selected node's config, and offers the
// variables available from upstream nodes (their output schema + last-run samples).
// Clicking a variable inserts `{{ nodeId.field }}` into the focused field.
export default function Properties({ node, variables = [], onChange, onDelete }) {
  const fields = node?.data.spec.config_fields || [];
  const [focused, setFocused] = useState(null);
  useEffect(() => { setFocused(fields[0]?.key || null); }, [node?.id]);

  if (!node) {
    return <aside className="props"><div className="props-empty">Select a node to configure it.</div></aside>;
  }
  const spec = node.data.spec;
  const config = node.data.config || {};
  const set = (k, v) => onChange({ ...config, [k]: v });

  const insertVar = (nodeId, path) => {
    const target = focused || fields[0]?.key;
    if (!target) return;
    set(target, `${config[target] ?? ""}{{ ${nodeId}.${path} }}`);
  };

  // Map each available variable ref -> its type, to validate what fields reference.
  const typeByRef = {};
  for (const g of variables) for (const f of g.fields) typeByRef[`${g.nodeId}.${f.path}`] = f.type;
  const warnFor = (f) => {
    if (!f.expects) return null;
    const bad = refsIn(config[f.key]).filter(
      (r) => typeByRef[r] && !compatible(typeByRef[r], f.expects));
    return bad.length
      ? `Expects ${f.expects} — ${bad.map((r) => `${r} is ${typeByRef[r]}`).join(", ")}`
      : null;
  };

  return (
    <aside className="props">
      <div className="props-head">
        <span>{spec.icon} {spec.label}</span>
        <button className="link-danger" onClick={onDelete}>Delete</button>
      </div>
      <p className="props-desc">{spec.description}</p>

      <label className="field">
        <span>Name</span>
        <input value={node.data.name || ""} placeholder={spec.label}
               onChange={(e) => onChange(config, e.target.value)} />
      </label>

      {fields.map((f) => (
        <div key={f.key} className="field-wrap">
        <label className="field">
          <span>{f.label}{f.expects && <em className="expects"> · {f.expects}</em>}</span>
          {f.type === "textarea" ? (
            <textarea value={config[f.key] ?? f.default ?? ""} placeholder={f.placeholder || ""}
                      rows={4} onFocus={() => setFocused(f.key)}
                      onChange={(e) => set(f.key, e.target.value)} />
          ) : f.type === "select" ? (
            <select value={config[f.key] ?? f.default ?? ""} onFocus={() => setFocused(f.key)}
                    onChange={(e) => set(f.key, e.target.value)}>
              {(f.options || []).map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          ) : f.type === "boolean" ? (
            <input type="checkbox" checked={!!config[f.key]} onChange={(e) => set(f.key, e.target.checked)} />
          ) : (
            <input type={f.type === "number" ? "number" : "text"} value={config[f.key] ?? f.default ?? ""}
                   placeholder={f.placeholder || ""} onFocus={() => setFocused(f.key)}
                   onChange={(e) => set(f.key, e.target.value)} />
          )}
        </label>
        {warnFor(f) && <div className="field-warn">⚠ {warnFor(f)}</div>}
        </div>
      ))}

      {fields.length > 0 && (
        <div className="vars">
          <div className="vars-head">Variables from previous nodes</div>
          {variables.length === 0 && (
            <p className="muted small">Connect a node upstream to use its output here.</p>
          )}
          {variables.map((g) => (
            <div key={g.nodeId} className="vars-group">
              <div className="vars-node">{g.nodeName}</div>
              {g.fields.map((f) => (
                <button key={f.path} className="var-chip" title={`${f.type}${f.sample !== undefined ? " · " + sample(f.sample) : ""}`}
                        onClick={() => insertVar(g.nodeId, f.path)}>
                  {f.path}
                  <span className="var-type">{f.type}</span>
                  {f.sample !== undefined && <em>= {sample(f.sample)}</em>}
                </button>
              ))}
            </div>
          ))}
          <p className="muted small">Inserts into the field you last clicked.</p>
        </div>
      )}
    </aside>
  );
}

function sample(v) {
  if (v === undefined || v === null) return "";
  const s = typeof v === "string" ? v : JSON.stringify(v);
  return s.length > 40 ? s.slice(0, 40) + "…" : s;
}

function refsIn(value) {
  const out = [];
  const re = /\{\{\s*([^}]+?)\s*\}\}/g;
  let m;
  while ((m = re.exec(value || ""))) out.push(m[1].trim());
  return out;
}

function compatible(varType, expects) {
  if (!expects || !varType) return true;
  if (expects === varType) return true;
  if (expects === "string") return true;          // anything stringifies
  if (expects === "media") return ["media", "string"].includes(varType);
  if (expects === "number") return varType === "number";
  if (expects === "boolean") return varType === "boolean";
  return true;                                      // lenient for object/array
}
