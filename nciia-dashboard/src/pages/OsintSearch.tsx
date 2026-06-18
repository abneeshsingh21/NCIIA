import { useState, useEffect, useRef, useCallback } from 'react';
import { Search, Terminal as TerminalIcon, Activity, AlertTriangle } from 'lucide-react';
import { searchOsint, type OsintSearchResponse } from '../lib/api';
import { useWebSocket } from '../context/WebSocketContext';

interface LogEntry {
  id: string;
  timestamp: string;
  source: string;
  content: string;
  type: 'info' | 'warning' | 'alert';
}

export default function OsintSearch() {
  const { subscribe } = useWebSocket();

  const [query, setQuery]           = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults]       = useState<OsintSearchResponse | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [logs, setLogs]             = useState<LogEntry[]>([]);
  const logsEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll terminal
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const addLog = useCallback((source: string, content: string, type: LogEntry['type'] = 'info') => {
    setLogs(prev => [...prev.slice(-200), {
      id: `${Date.now()}-${Math.random()}`,
      timestamp: new Date().toLocaleTimeString(),
      source,
      content,
      type,
    }]);
  }, []);

  // Subscribe to live signals via the shared WS connection (no duplicate socket)
  useEffect(() => {
    addLog('SYSTEM', 'N-CIIA intercept daemon v1.0.0 initialised', 'info');
    addLog('SYSTEM', 'Subscribing to live signal feed…', 'info');

    const unsub = subscribe('signal_detected', (msg) => {
      const signal = msg.data as Record<string, string> | undefined;
      if (!signal) return;
      const actor = (signal.actor ?? 'UNKNOWN').toUpperCase();
      const stage = (signal.stage ?? 'detection').toUpperCase();
      const content = signal.content ?? signal.raw_content ?? JSON.stringify(signal).slice(0, 120);
      addLog(signal.source_name ?? 'FEED', `[${actor}] ${stage}: ${content}`,
        stage === 'C2' || stage === 'EXFILTRATION' ? 'alert' : 'info');
    });

    const unsubPersona = subscribe('persona_activity', (msg) => {
      const d = msg.data as Record<string, string> | undefined;
      if (!d) return;
      addLog('PERSONA', `Activity detected: ${d.primary_identifier ?? d.id ?? 'unknown'}`, 'warning');
    });

    return () => { unsub(); unsubPersona(); };
  }, [subscribe, addLog]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;

    setIsSearching(true);
    setSearchError(null);
    setResults(null);
    addLog('SEARCH', `Initiating deep scan for target: ${q}`, 'warning');

    try {
      const data = await searchOsint(q);
      setResults(data);
      addLog('SEARCH', `Scan complete — ${data.signals_found} signals found`, 'info');
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Search failed';
      setSearchError(msg);
      addLog('ERROR', msg, 'alert');
    } finally {
      setIsSearching(false);
    }
  };

  const LOG_COLOR: Record<LogEntry['type'], string> = {
    info: '#c9d1d9', warning: '#d2a8ff', alert: '#ff7b72',
  };

  return (
    <div className="page-container osint-container">
      <header className="page-header">
        <div>
          <h2 className="page-header__title">
            <Search size={24} className="icon--primary" />
            OSINT Search &amp; Intercept
          </h2>
          <p className="page-header__sub">Unified intelligence gathering · Live signal interception</p>
        </div>
        <span className="badge badge--success">
          <Activity size={12} className="spin-slow" />
          ACTIVE INTERCEPT
        </span>
      </header>

      {/* Search form */}
      <form onSubmit={handleSearch} className="osint-searchbar">
        <div className="osint-searchbar__input-wrap">
          <Search size={18} className="osint-searchbar__icon" />
          <input
            type="text"
            className="input osint-searchbar__input"
            placeholder="Enter IOC, persona identifier, username, email, IP…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            autoFocus
          />
        </div>
        <button type="submit" className="btn btn--primary" disabled={isSearching || !query.trim()}>
          {isSearching ? 'Scanning…' : 'EXECUTE SCAN'}
        </button>
      </form>

      {searchError && (
        <div className="alert-banner alert-banner--error" role="alert">
          <AlertTriangle size={14} /> {searchError}
        </div>
      )}

      {/* Results */}
      {results && (
        <div className="osint-results">
          <div className="card">
            <div className="card__header">
              <h3 className="card__title">
                <Search size={16} className="icon--primary" />
                Discovered Signals ({results.signals_found})
              </h3>
            </div>
            {results.signals.length === 0 ? (
              <div className="empty-state"><p>No signals matched &ldquo;{results.query}&rdquo;</p></div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Source</th>
                    <th>Type</th>
                    <th>Content Preview</th>
                  </tr>
                </thead>
                <tbody>
                  {results.signals.map((s: OsintSearchResponse['signals'][number]) => (
                    <tr key={s.id}>
                      <td className="font-medium">{s.source}</td>
                      <td><span className="badge badge--neutral">{s.type}</span></td>
                      <td className="text-muted text-xs">{s.content_preview}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* Live terminal */}
      <div className="terminal-window">
        <div className="terminal-header">
          <TerminalIcon size={13} className="terminal-header__icon" />
          <span className="terminal-header__title">nciia_intercept.log --tail -f</span>
          <span className="terminal-header__count">{logs.length} entries</span>
        </div>
        <div className="terminal-body">
          {logs.map(log => (
            <div key={log.id} className="terminal-line">
              <span className="terminal-line__ts">[{log.timestamp}]</span>
              {' '}
              <span className="terminal-line__src">{log.source}</span>
              {' '}
              <span className="terminal-line__arrow">➜</span>
              {' '}
              <span style={{ color: LOG_COLOR[log.type], fontWeight: log.type === 'alert' ? 700 : 400 }}>
                {log.content}
              </span>
            </div>
          ))}
          {logs.length === 0 && (
            <div className="terminal-line text-muted">Waiting for signals…</div>
          )}
          <div ref={logsEndRef} />
        </div>
      </div>
    </div>
  );
}
