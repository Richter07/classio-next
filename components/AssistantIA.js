"use client";
import { useState } from 'react';

export default function AssistantIA() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  async function send() {
    if (!input) return;
    setLoading(true);
    const userMsg = { role: "user", text: input };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    const res = await fetch('/api/ai', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userMsg.text })
    });
    const data = await res.json();
    setMessages(prev => [...prev, { role: "ai", text: data.reply }]);
    setLoading(false);
  }

  return (
    <div style={{ border: "1px solid #ddd", borderRadius: 12, padding: 16, marginTop: 20 }}>
      <h3>Assistant Classio (Llama 3.2)</h3>
      <div style={{ minHeight: 150, maxHeight: 300, overflowY: "auto", background: "#f9f9f9", padding: 10, borderRadius: 8 }}>
        {messages.map((m, i) => (
          <p key={i}><strong>{m.role === "user" ? "Toi: " : "IA: "}</strong>{m.text}</p>
        ))}
        {loading && <p>IA réfléchit...</p>}
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
        <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && send()} placeholder="Pose ta question..." style={{ flex: 1, padding: 8 }} />
        <button onClick={send}>Envoyer</button>
      </div>
    </div>
  );
}