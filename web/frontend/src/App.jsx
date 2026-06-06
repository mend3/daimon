import { useEffect, useState } from "react";
import { api } from "./api";
import Chat from "./components/Chat.jsx";
import Workflows from "./modules/Workflows.jsx";
import Knowledge from "./modules/Knowledge.jsx";

// Plug-and-play modules: the backend decides which are enabled (future: per tier /
// user). The shell renders a rail for the enabled ones and the active module; the
// Chat panel is always present.
const REGISTRY = { workflows: Workflows, knowledge: Knowledge };

export default function App() {
  const [modules, setModules] = useState([]);
  const [active, setActive] = useState(null);

  useEffect(() => {
    api.modules().then((m) => {
      setModules(m);
      setActive((a) => a || m[0]?.id || null);
    });
  }, []);

  return (
    <div className="app">
      <nav className="module-rail">
        <div className="brand" title="Ella">E</div>
        {modules.map((m) => (
          <button key={m.id} className={`rail-btn${active === m.id ? " on" : ""}`}
                  title={m.label} onClick={() => setActive(m.id)}>{m.icon}</button>
        ))}
      </nav>
      <div className="module-main">
        {modules.length === 0 && <div className="kg-empty">No modules enabled.</div>}
        {modules.map((m) => {
          const Comp = REGISTRY[m.id];
          if (!Comp) return null;
          // Keep every module mounted (hidden when inactive) so in-progress state —
          // e.g. an unsaved workflow draft — survives switching modules.
          return (
            <div key={m.id} className="module-pane"
                 style={{ display: active === m.id ? "flex" : "none" }}>
              <Comp />
            </div>
          );
        })}
      </div>
      <Chat />
    </div>
  );
}
