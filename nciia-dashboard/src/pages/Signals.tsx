import { useState, useEffect, useCallback } from 'react';
import { Radio, AlertTriangle, RefreshCw, Search, Filter } from 'lucide-react';
import { fetchSignals, type Signal } from '../lib/api';
import { useWebSocket } from '../context/WebSocketContext';

const TYPE_OPTIONS = ['all', 'web', 'forum', 'paste', 'social', 'darkweb', 'threat_feed'] as const;

export default function Signals() {
  const { subscribe } = useWebSocket();
  const [signals, setSignals]   = useState<Signal[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [search, setSearch]     = useState('');
  const [typeFilter, setTypeFilter] = useState('all');

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const data = await fetchSignals({ type: typeFilter !== 'all' ? typeFilter : undefined, limit: 200 });
      setSignals(data);
    } catch (e) { setError(e instanceof Error ? e.message : 'Failed to load signals'); }
    finally { setLoading(false); }
  }, [typeFilter]);

  useEffect(() => { void load(); }, [load]);

  // Auto-append new signals from WS without full reload
  useEffect(() => subscribe('signal_detected', (msg) => {
    const s = msg.data as Signal | undefined;
    if (s) setSignals(prev => [s, ...prev].slice(0, 500));
  }), [subscribe]);

  const filtered = signals.filter(s =>
    !search ||
    s.source_name.toLowerCase().includes(search.toLowerCase()) ||
    s.raw_content.toLowerCase().includes(search.toLowerCase()) ||
    (s.extracted_text ?? '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="page-container">
      <header className="page-header">
        <div>
          <h2 className="page-header__title"><Radio size={24} className="icon--primary" /> Intelligence Signals</h2>
          <p className="page-header__sub">Raw OSINT signals ingested from all sources</p>
        </div>
        <div className="page-header__actions">
          <button className="btn btn--ghost btn--sm" onClick={load} disabled={loading}><RefreshCw size={14} className={loading ? 'spin' : ''} /></button>
          <span className="live-badge"><span className="live-dot" /> Live</span>
        </div>
      </header>

      {error && <div className="alert-banner alert-banner--error"><AlertTriangle size={14} />{error}<button className="btn btn--ghost btn--xs" onClick={load}>Retry</button></div>}

      <div className="filter-bar">
        <div className="filter-bar__search">
          <Search size={14} className="filter-bar__search-icon" />
          <input className="input" placeholder="Search signals…" value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <div className="filter-bar__chips">
          <Filter size={12} className="text-muted" />
          {TYPE_OPTIONS.map(t => (
            <button key={t} className={`chip${typeFilter === t ? ' chip--active' : ''}`} onClick={() => setTypeFilter(t)}>
              {t === 'all' ? 'All Types' : t}
            </button>
          ))}
        </div>
        <span className="text-muted text-xs">{filtered.length.toLocaleString()} signals</span>
      </div>

      <div className="card">
        <table className="data-table">
          <thead>
            <tr><th>Source</th><th>Type</th><th>Content</th><th>Discovered</th><th>Processed</th></tr>
          </thead>
          <tbody>
            {loading && Array.from({ length: 8 }, (_, i) => <tr key={i}><td colSpan={5}><div className="skeleton-row" /></td></tr>)}
            {!loading && filtered.length === 0 && (
              <tr><td colSpan={5} className="text-center text-muted" style={{ padding: '40px 0' }}>No signals found</td></tr>
            )}
            {!loading && filtered.map(s => (
              <tr key={s.id}>
                <td>
                  <span className="font-medium">{s.source_name}</span>
                  {s.source_url && <a href={s.source_url} target="_blank" rel="noopener noreferrer" className="text-muted text-xs block" style={{ marginTop: 2 }}>{s.source_url.slice(0, 40)}…</a>}
                </td>
                <td><span className="badge badge--neutral">{s.type}</span></td>
                <td className="text-muted text-xs" style={{ maxWidth: 300 }}>
                  {(s.extracted_text ?? s.raw_content).slice(0, 100)}{(s.extracted_text ?? s.raw_content).length > 100 ? '…' : ''}
                </td>
                <td className="text-muted text-xs">{new Date(s.discovered_at).toLocaleString()}</td>
                <td>{s.is_processed ? <span className="badge badge--success">Yes</span> : <span className="badge badge--neutral">Pending</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
