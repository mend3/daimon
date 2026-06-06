# Ella web layer

A browser/mobile canvas to build workflows and chat with Ella — the Telegram bot
stays; this deepens the experience. Backend is FastAPI (`ella_web`, in
`ingestion/`); frontend is React + React Flow (`web/frontend`).

Nodes are Ella's capabilities. **Solid** edges carry execution (Node → Node);
**dotted** edges attach dependencies (model, knowledge, tools) to the agent — so the
canvas stays clean as Ella gains abilities.

## Run (recommended — no local Node/npm)

The frontend builds inside Docker; you only need Docker and the devcontainer to have
run once (so Ella's config is in the `hermes-data` volume the web service shares):

```bash
make web            # builds + serves the canvas at http://localhost:8099
```

## Run (dev, with hot reload — needs Node on the host)

```bash
ella-web                                           # backend on :8099 (in the devcontainer)
cd web/frontend && npm install && npm run dev      # canvas on :5173, proxies to :8099
```

Single server without the dev proxy:

```bash
cd web/frontend && npm run build
ELLA_WEB_STATIC="$PWD/dist" ella-web
```

## Modules

The app is a shell of plug-and-play **modules**, gated by `GET /api/modules`
(`ELLA_MODULES` env, default `workflows,knowledge`; future per tier/user). A left rail
switches between them; the Chat panel is always present.

- **Workflows** — the node canvas (below).
- **Knowledge** — a 3D graph of the knowledge base: a node per source (colored by
  type), edges to each source's nearest semantic neighbours, with cross-type links
  (e.g. a url relating to a feed item) drawn distinctly. Click a node for details.

A new module is a drop-in: a component in `src/modules/`, an entry in the App
registry, and the `ELLA_MODULES` gate.

## What's in the MVP

- Infinite canvas (pan/zoom/grid), node palette with search, right-side properties.
- Node types from `ella_flow` (triggers, the Ella agent with resource slots, tools,
  IF logic, outputs). The catalog drives the palette and the properties form.
- Run with live per-node states over WebSocket; Executions tab.
- Embedded chat with Ella, grounded by her knowledge base.

New node types are a drop-in in `ingestion/ella_flow/nodes/` (or an `ella_flow.nodes`
entry point) — the palette and properties pick them up automatically.
