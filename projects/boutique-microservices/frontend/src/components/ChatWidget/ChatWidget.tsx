import React, { useState, useRef, useEffect } from 'react';
import './ChatWidget.css';

interface Message {
  role: 'user' | 'assistant';
  text: string;
}

// In production nginx proxies /ai/ -> ai-assistant:8000.
// In CRA dev, setupProxy.js proxies /ai as well.
const ASK_URL = '/ai/ask';

const ChatWidget: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', text: 'Hi! I can help with product details and pricing. What are you looking for?' },
  ]);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, open]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');
    setMessages((m) => [...m, { role: 'user', text }]);
    setLoading(true);
    try {
      const res = await fetch(ASK_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });
      const data = await res.json();
      setMessages((m) => [...m, { role: 'assistant', text: data.answer ?? 'Sorry, something went wrong.' }]);
    } catch {
      setMessages((m) => [...m, { role: 'assistant', text: 'The assistant is unavailable right now. Please try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="cw-root">
      {open && (
        <div className="cw-panel">
          <div className="cw-header">
            <span>Boutique Assistant</span>
            <button className="cw-close" onClick={() => setOpen(false)} aria-label="Close">×</button>
          </div>
          <div className="cw-messages">
            {messages.map((m, i) => (
              <div key={i} className={`cw-msg cw-${m.role}`}>{m.text}</div>
            ))}
            {loading && <div className="cw-msg cw-assistant cw-typing">…</div>}
            <div ref={endRef} />
          </div>
          <div className="cw-input">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKey}
              placeholder="Ask about a product or price…"
              aria-label="Message"
            />
            <button onClick={send} disabled={loading} aria-label="Send">Send</button>
          </div>
        </div>
      )}
      <button className="cw-fab" onClick={() => setOpen((o) => !o)} aria-label="Chat">
        {open ? '×' : '💬'}
      </button>
    </div>
  );
};

export default ChatWidget;
