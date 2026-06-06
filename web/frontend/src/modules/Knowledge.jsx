import { useEffect, useRef, useState } from "react";
import ForceGraph3D from "react-force-graph-3d";
import { api } from "../api";

const TYPE_COLOR = {
  files: "#3fb950", urls: "#58a6ff", feeds: "#d9a40a", webhook: "#f0883e", chat: "#8b5cf6",
};

// 3D view of the knowledge base: each source is a node (colored by type), edges
// connect semantically related sources — including across types (a url linking to
// a related feed item), drawn in purple.
export default function Knowledge() {
  const wrapRef = useRef(null);
  const [data, setData] = useState({ nodes: [], links: [] });
  const [selected, setSelected] = useState(null);
  const [dims, setDims] = useState({ w: 800, h: 600 });
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api.knowledgeGraph().then((g) => setData(g)).catch(() => setData({ nodes: [], links: [] }))
      .finally(() => setLoading(false));
  };
  useEffect(load, []);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setDims({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div className="knowledge">
      <header className="topbar">
        <span className="wf-name">Knowledge graph</span>
        <span className="muted">{data.nodes.length} sources · {data.links.length} links</span>
        <div className="run-box"><button onClick={load} disabled={loading}>↻ Refresh</button></div>
      </header>

      <div className="kg-body">
        <div className="kg-canvas" ref={wrapRef}>
          {loading ? (
            <div className="kg-empty">Loading…</div>
          ) : data.nodes.length === 0 ? (
            <div className="kg-empty">
              No knowledge yet — save links, files, or notes and they'll appear here.
            </div>
          ) : (
            <ForceGraph3D
              width={dims.w} height={dims.h}
              graphData={data}
              backgroundColor="#0d1117"
              nodeLabel={(n) => `${n.title} · ${n.type}`}
              nodeColor={(n) => TYPE_COLOR[n.type] || "#8b949e"}
              nodeOpacity={0.95}
              linkColor={(l) => (l.cross_type ? "#8b5cf6" : "#3a3f4b")}
              linkWidth={(l) => (l.score || 0.5) * 2}
              linkOpacity={0.5}
              onNodeClick={(n) => setSelected(n)}
              onBackgroundClick={() => setSelected(null)}
            />
          )}
          <div className="kg-legend">
            {Object.entries(TYPE_COLOR).map(([t, c]) => (
              <span key={t}><i style={{ background: c }} /> {t}</span>
            ))}
            <span><i style={{ background: "#8b5cf6" }} /> cross-type link</span>
          </div>
        </div>

        {selected && (
          <aside className="kg-detail">
            <div className="props-head">
              <span>{selected.title}</span>
              <button className="link-danger" onClick={() => setSelected(null)}>×</button>
            </div>
            <p className="muted small">type: {selected.type}</p>
            {selected.uri && (
              <a className="kg-link" href={selected.uri} target="_blank" rel="noreferrer">{selected.uri}</a>
            )}
            <p className="muted small">
              {data.links.filter((l) => l.source === selected.id || l.target === selected.id
                || l.source?.id === selected.id || l.target?.id === selected.id).length} connections
            </p>
          </aside>
        )}
      </div>
    </div>
  );
}
