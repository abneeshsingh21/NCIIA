import { useState, useEffect, useCallback } from 'react';
import { Users, AlertTriangle, RefreshCw, Search, Plus } from 'lucide-react';
import { fetchPersonas, type Persona } from '../lib/api';
import { useWebSocket } from '../context/WebSocketContext';

export default function Personas() {
  const { subscribe } = useWebSocket();
  const [personas, setPersonas]   = useState<Persona[]>([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [search, setSearch]       = useState('');
  const [watchOnly, setWatchOnly] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const data = await fetchPersonas({ q: search || undefined, is_active_watch: watchOnly || undefined, limit: 200 });
      setPersonas(data);
    } catch (e) { setError(e instanceof Error ? e.message : 'Failed to load personas'); }
    finally { setLoading(false); }
  }, [search, watchOnly]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => subscribe('persona_activity', () => void load()), [subscribe, load]);

  const LEVEL_CLS: Record<string, string> = { critical: 'badge--critical', high: 'badge--warning', medium: 'badge--medium', low: 'badge--low', minimal: 'badge--neutral' };

  return (
    <div className="page-container">
      <header className="page-header">
        <div>
          <h2 className="page-header__title"><Users size={24} className="icon--primary" /> Personas</h2>
          <p className="page-header__sub">Tracked digital identities &amp; behavioral profiles</p>
        </div>
        <div className="page-header__actions">
          <button className="btn btn--ghost btn--sm" onClick={load} disabled={loading}><RefreshCw size={14} className={loading ? 'spin' : ''} /></button>
          <button className="btn btn--primary btn--sm"><Plus size={14} /> New Persona</button>
        </div>
      </header>

      {error && <div className="alert-banner alert-banner--error" role="alert"><AlertTriangle size={14} />{error}<button className="btn btn--ghost btn--xs" onClick={load}>Retry</button></div>}

      <div className="filter-bar">
        <div className="filter-bar__search">
          <Search size={14} className="filter-bar__search-icon" />
          <input className="input" type="text" placeholder="Search identifier…" value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <label className="filter-bar__toggle">
          <input type="checkbox" checked={watchOnly} onChange={e => setWatchOnly(e.target.checked)} />
          Watch list only
        </label>
        <span className="text-muted text-xs">{personas.length} result{personas.length !== 1 ? 's' : ''}</span>
      </div>

      <div className="card">
        <table className="data-table">
          <thead>
            <tr><th>Identifier</th><th>Type</th><th>Platforms</th><th>Threat Level</th><th>Activity Count</th><th>Last Active</th><th>Watch</th></tr>
          </thead>
          <tbody>
            {loading && Array.from({ length: 6 }, (_, i) => (
              <tr key={i}><td colSpan={7}><div className="skeleton-row" /></td></tr>
            ))}
            {!loading && personas.length === 0 && (
              <tr><td colSpan={7} className="text-center text-muted" style={{ padding: '40px 0' }}>No personas found</td></tr>
            )}
            {!loading && personas.map(p => (
              <tr key={p.id}>
                <td className="font-medium">{p.primary_identifier}</td>
                <td className="text-muted">{p.identifier_type}</td>
                <td className="text-muted text-xs">{p.platforms_detected.slice(0, 3).join(', ') || '—'}{p.platforms_detected.length > 3 ? ` +${p.platforms_detected.length - 3}` : ''}</td>
                <td>{p.threat_score ? <span className={`badge ${LEVEL_CLS[p.threat_score.level ?? 'unknown'] ?? 'badge--neutral'}`}>{p.threat_score.level ?? 'unknown'}</span> : <span className="text-muted">—</span>}</td>
                <td className="text-muted">{p.activity_count.toLocaleString()}</td>
                <td className="text-muted text-xs">{p.last_activity ? new Date(p.last_activity).toLocaleString() : '—'}</td>
                <td>{p.is_active_watch ? <span className="badge badge--success">Active</span> : <span className="badge badge--neutral">Idle</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
