import { useRef, useState } from "react";
import { api } from "../api";

// Embedded Build/Test/Observe chat — talk to Ella without leaving the editor.
// Ella's replies can be spoken via the local TTS engine (🔊 per message, or
// auto-speak).
export default function Chat() {
  const [messages, setMessages] = useState([
    { role: "ella", text: "Hi — I'm Ella. Ask me anything, or build a workflow on the canvas." },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(false);
  const [speaking, setSpeaking] = useState(null);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const recorderRef = useRef(null);

  const toggleRecord = async () => {
    if (recording) {
      recorderRef.current?.stop();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      const chunks = [];
      rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setRecording(false);
        setTranscribing(true);
        try {
          const { text } = await api.stt(new Blob(chunks, { type: "audio/webm" }));
          if (text) setInput((cur) => (cur ? cur + " " : "") + text);
        } catch {
          /* ignore — leave input as-is */
        } finally {
          setTranscribing(false);
        }
      };
      recorderRef.current = rec;
      rec.start();
      setRecording(true);
    } catch {
      setTranscribing(false);
    }
  };

  const speak = async (i, text) => {
    try {
      setSpeaking(i);
      const blob = await api.tts(text);
      const audio = new Audio(URL.createObjectURL(blob));
      audio.onended = () => setSpeaking(null);
      await audio.play();
    } catch {
      setSpeaking(null);
    }
  };

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "you", text }]);
    setBusy(true);
    try {
      const { reply, citations } = await api.chat(text);
      setMessages((m) => {
        const next = [...m, { role: "ella", text: reply, citations }];
        if (autoSpeak) speak(next.length - 1, reply);
        return next;
      });
    } catch {
      setMessages((m) => [...m, { role: "ella", text: "Something went wrong reaching the model." }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="chat">
      <div className="chat-head">
        Chat with Ella
        <label className="auto-speak" title="Speak Ella's replies aloud">
          <input type="checkbox" checked={autoSpeak} onChange={(e) => setAutoSpeak(e.target.checked)} />
          🔊 Auto
        </label>
      </div>
      <div className="chat-log">
        {messages.map((m, i) => (
          <div key={i} className={`msg msg-${m.role}`}>
            <div className="msg-text">{m.text}</div>
            {m.role === "ella" && (
              <button className="speak-btn" disabled={speaking === i}
                      onClick={() => speak(i, m.text)} title="Play">
                {speaking === i ? "▶ …" : "🔊"}
              </button>
            )}
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
        <button className={`mic-btn${recording ? " rec" : ""}`} onClick={toggleRecord}
                disabled={transcribing} title={recording ? "Stop & transcribe" : "Record a voice message"}>
          {recording ? "⏺" : transcribing ? "…" : "🎙"}
        </button>
        <input value={input}
               placeholder={transcribing ? "Transcribing…" : "Message Ella…"}
               onChange={(e) => setInput(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && send()} />
        <button onClick={send} disabled={busy}>Send</button>
      </div>
    </div>
  );
}
