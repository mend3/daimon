import { useEffect, useState } from "react";
import { api } from "../api";

// Feeds module: keep a collection of feeds, browse unread items, and let Ella
// categorize them into topics — kept items are ingested into the RAG and become
// available to her everywhere.
export default function Feeds() {
  const [feeds, setFeeds] = useState([]);
  const [entries, setEntries] = useState([]);
  const [clusters, setClusters] = useState([]);
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(null);

  const reload = () => {
    api.feeds().then(setFeeds).catch(() => setFeeds([]));
    api.feedEntries().then(setEntries).catch(() => setEntries([]));
    api.feedClusters().then((c) => setClusters(c.clusters || [])).catch(() => setClusters([]));
  };
  useEffect(reload, []);

  const subscribe = async () => {
    const u = url.trim();
    if (!u) return;
    setUrl("");
    await api.subscribeFeed(u).catch(() => {});
    setTimeout(reload, 1500);
  };

  const process = async () => {
    setBusy(true);
    setNote(null);
    try {
      const r = await api.processFeeds();
      setNote(`Processed ${r.processed} item(s) into memory, skipped ${r.skipped}.`);
      reload();
    } catch {
      setNote("Processing failed — is Miniflux configured?");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="feeds">
      <header className="topbar">
        <span className="wf-name">Feeds</span>
        <span className="muted">{feeds.length} feeds · {entries.length} unread</span>
        <div className="run-box">
          <input value={url} placeholder="https://blog.example/rss.xml"
                 onChange={(e) => setUrl(e.target.value)}
                 onKeyDown={(e) => e.key === "Enter" && subscribe()} />
          <button onClick={subscribe}>Subscribe</button>
          <button className="run-btn" onClick={process} disabled={busy}>
            {busy ? "Processing…" : "✨ Process with AI"}
          </button>
        </div>
      </header>
      {note && <div className="feeds-note">{note}</div>}

      <div className="feeds-body">
        <aside className="feeds-side">
          <div className="feeds-h">Your feeds</div>
          {feeds.length === 0 && <p className="muted small">No feeds yet — subscribe above.</p>}
          {feeds.map((f) => (
            <div key={f.id} className="feed-row" title={f.site_url}>
              <span>{f.title}</span>
              {f.category && <em className="feed-cat">{f.category}</em>}
            </div>
          ))}
          <div className="feeds-h">Unread</div>
          {entries.map((e) => (
            <a key={e.id} className="entry" href={e.url} target="_blank" rel="noreferrer">
              <div className="entry-title">{e.title}</div>
              <div className="muted small">{e.feed}</div>
            </a>
          ))}
        </aside>

        <main className="feeds-main">
          <div className="feeds-h">Themes <span className="muted small">— AI-clustered, in Ella's memory</span></div>
          {clusters.length === 0 && (
            <p className="muted">Nothing processed yet. Subscribe to a feed, then “Process with AI”.</p>
          )}
          <div className="topic-grid">
            {clusters.map((c, ci) => (
              <div key={ci} className="topic-card">
                <div className="topic-head">{c.theme} <span className="muted small">{c.size}</span></div>
                {c.items.slice(0, 10).map((it, i) => (
                  <a key={i} className="topic-item" href={it.uri || "#"} target="_blank" rel="noreferrer"
                     title={it.summary || ""}>
                    {it.title}
                    {it.topic && it.topic !== c.theme && <em className="topic-tag"> · {it.topic}</em>}
                  </a>
                ))}
              </div>
            ))}
          </div>
        </main>
      </div>
    </div>
  );
}
