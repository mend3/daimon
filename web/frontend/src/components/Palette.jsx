import { useMemo, useState } from "react";

// Sidebar of node types grouped by category, with instant search. Click to add.
export default function Palette({ catalog, onAdd }) {
  const [q, setQ] = useState("");
  const groups = useMemo(() => {
    const filtered = catalog.filter(
      (n) =>
        n.label.toLowerCase().includes(q.toLowerCase()) ||
        n.type.toLowerCase().includes(q.toLowerCase())
    );
    const by = {};
    for (const n of filtered) (by[n.category] ||= []).push(n);
    return by;
  }, [catalog, q]);

  return (
    <aside className="palette">
      <input
        className="search"
        placeholder="Search nodes…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      {Object.entries(groups).map(([cat, nodes]) => (
        <div key={cat} className="palette-group">
          <div className="palette-cat">{cat}</div>
          {nodes.map((n) => (
            <button key={n.type} className="palette-item" onClick={() => onAdd(n)} title={n.description}>
              <span className="palette-icon">{n.icon}</span>
              {n.label}
            </button>
          ))}
        </div>
      ))}
    </aside>
  );
}
