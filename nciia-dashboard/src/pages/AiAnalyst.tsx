import { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Bot, User, Trash2, Loader } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  streaming?: boolean;
}

const QUICK_PROMPTS = [
  'What are the top threats detected this week?',
  'Summarize the most active personas on watch list',
  'Generate a threat intelligence report for the latest signals',
  'What MITRE ATT&CK tactics are most active right now?',
  'Are there any critical unprocessed alerts I should know about?',
  'Draft IOC block list from recent high-risk signals',
];

export default function AiAnalyst() {
  const [messages, setMessages]     = useState<Message[]>([]);
  const [input, setInput]           = useState('');
  const [sessionId, setSessionId]   = useState<string | null>(null);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Initialise session on mount
  useEffect(() => {
    fetch(`${API_BASE}/api/advanced/session/new`, { method: 'POST' })
      .then(r => r.json())
      .then(d => setSessionId(d.session_id))
      .catch(() => setSessionId('local'));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || loading) return;
    setError(null);
    setInput('');

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    };

    const assistantMsg: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      streaming: true,
    };

    setMessages(prev => [...prev, userMsg, assistantMsg]);
    setLoading(true);

    try {
      const resp = await fetch(`${API_BASE}/api/advanced/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text, session_id: sessionId }),
      });

      if (!resp.ok) throw new Error(`API error ${resp.status}`);
      if (!resp.body) throw new Error('No response body');

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n').filter(l => l.startsWith('data:'));

        for (const line of lines) {
          const dataStr = line.slice(5).trim();
          try {
            const data = JSON.parse(dataStr);
            if (data.token) {
              accumulated += data.token;
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantMsg.id
                    ? { ...m, content: accumulated }
                    : m
                )
              );
            }
            if (data.done || data.error) break;
          } catch { /* skip malformed */ }
        }
      }

      setMessages(prev =>
        prev.map(m =>
          m.id === assistantMsg.id ? { ...m, streaming: false } : m
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed');
      setMessages(prev => prev.filter(m => m.id !== assistantMsg.id));
    } finally {
      setLoading(false);
    }
  }, [loading, sessionId]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void sendMessage(input);
    }
  };

  const clearChat = async () => {
    setMessages([]);
    const resp = await fetch(`${API_BASE}/api/advanced/session/new`, { method: 'POST' }).catch(() => null);
    if (resp?.ok) {
      const d = await resp.json();
      setSessionId(d.session_id);
    }
  };

  return (
    <div className="ai-analyst-page">
      {/* Header */}
      <header className="page-header">
        <div>
          <h2 className="page-header__title">
            <Bot size={24} className="icon--primary" />
            ARIA — AI Intelligence Analyst
          </h2>
          <p className="page-header__sub">
            Real-time RAG over live database · Powered by Groq LLaMA-3.3-70B
          </p>
        </div>
        <div className="page-header__actions">
          <span className="text-muted text-xs">Session: {sessionId?.slice(0, 8) ?? '…'}</span>
          <button className="btn btn--ghost btn--sm" onClick={clearChat} title="Clear chat">
            <Trash2 size={14} />
          </button>
        </div>
      </header>

      {/* Quick prompts */}
      {messages.length === 0 && (
        <div className="quick-prompts">
          <p className="quick-prompts__label">Suggested queries:</p>
          <div className="quick-prompts__grid">
            {QUICK_PROMPTS.map(p => (
              <button
                key={p}
                className="quick-prompt-card"
                onClick={() => void sendMessage(p)}
              >
                {p}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="chat-messages">
        {messages.map(msg => (
          <div key={msg.id} className={`chat-bubble chat-bubble--${msg.role}`}>
            <div className="chat-bubble__avatar">
              {msg.role === 'user'
                ? <User size={16} />
                : <Bot size={16} className="icon--primary" />}
            </div>
            <div className="chat-bubble__body">
              <div className="chat-bubble__meta">
                <span className="chat-bubble__name">
                  {msg.role === 'user' ? 'You' : 'ARIA'}
                </span>
                <span className="text-muted text-xs">
                  {msg.timestamp.toLocaleTimeString()}
                </span>
                {msg.streaming && <Loader size={12} className="spin icon--primary" />}
              </div>
              <div className="chat-bubble__content markdown-body">
                {msg.content
                  ? <ReactMarkdown>{msg.content}</ReactMarkdown>
                  : msg.streaming
                    ? <span className="cursor-blink">▍</span>
                    : null}
              </div>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {error && (
        <div className="alert-banner alert-banner--error">
          {error}
          <button className="btn btn--ghost btn--xs" onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      {/* Input */}
      <div className="chat-input-bar">
        <textarea
          ref={textareaRef}
          className="chat-input"
          placeholder="Ask ARIA anything about your threat landscape…"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={2}
          disabled={loading}
        />
        <div className="chat-input-bar__actions">
          <span className="text-muted text-xs">Shift+Enter for newline</span>
          <button
            className="btn btn--primary"
            onClick={() => void sendMessage(input)}
            disabled={loading || !input.trim()}
          >
            {loading
              ? <Loader size={16} className="spin" />
              : <Send size={16} />}
            {loading ? 'Thinking…' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
}
