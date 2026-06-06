import { useState } from "react";
import { api } from "../api";

// Embedded Build/Test/Observe chat — talk to Ella without leaving the editor.
export default function Chat() {
  const [messages, setMessages] = useState([
    { role: "ella", text: "Hi — I'm Ella. Ask me anything, or build a workflow on the canvas." },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "you", text }]);
    setBusy(true);
    try {
      const { reply, citations } = await api.chat(text);
      setMessages((m) => [...m, { role: "ella", text: reply, citations }]);
    } catch {
      setMessages((m) => [...m, { role: "ella", text: "Something went wrong reaching the model." }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="chat">
      <div className="chat-head">Chat with Ella</div>
      <div className="chat-log">
        {messages.map((m, i) => (
          <div key={i} className={`msg msg-${m.role}`}>
            <div className="msg-text">{m.text}</div>
            {m.citations?.length > 0 && (
              <div className="msg-cites">
                {m.citations.map((c, j) => (
                  <a key={j} href={c.uri || "#"} target="_blank" rel="noreferrer">{c.title}</a>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="msg msg-ella"><div className="msg-text">…</div></div>}
      </div>
      <div className="chat-input">
        <input value={input} placeholder="Message Ella…" onChange={(e) => setInput(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && send()} />
        <button onClick={send} disabled={busy}>Send</button>
      </div>
    </div>
  );
}
