import { useState, useEffect, useCallback } from 'react';
import { Briefcase, AlertTriangle, RefreshCw, Search, Plus, Filter } from 'lucide-react';
import { fetchCases, type Case } from '../lib/api';

const STATUS_OPTIONS = ['all', 'open', 'active', 'closed', 'archived'] as const;
const PRIORITY_CLS: Record<string, string> = { critical: 'badge--critical', high: 'badge--warning', medium: 'badge--medium', low: 'badge--low' };
const STATUS_CLS: Record<string, string>   = { open: 'badge--success', active: 'badge--primary', closed: 'badge--neutral', archived: 'badge--neutral' };

export default function Cases() {
  const [cases, setCases]       = useState<Case[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [search, setSearch]     = useState('');
  const [status, setStatus]     = useState<string>('all');

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const data = await fetchCases({ status: status !== 'all' ? status : undefined, limit: 200 });
      setCases(data);
    } catch (e) { setError(e instanceof Error ? e.message : 'Failed to load cases'); }
    finally { setLoading(false); }
  }, [status]);

  useEffect(() => { void load(); }, [load]);

  const filtered = cases.filter(c =>
    !search || c.name.toLowerCase().includes(search.toLowerCase()) ||
    (c.description ?? '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="page-container">
      <header className="page-header">
        <div>
          <h2 className="page-header__title"><Briefcase size={24} className="icon--primary" /> Investigation Cases</h2>
          <p className="page-header__sub">Manage active and historical intelligence investigations</p>
        </div>
        <div className="page-header__actions">
          <button className="btn btn--ghost btn--sm" onClick={load} disabled={loading}><RefreshCw size={14} className={loading ? 'spin' : ''} /></button>
          <button className="btn btn--primary btn--sm"><Plus size={14} /> New Case</button>
        </div>
      </header>

      {error && <div className="alert-banner alert-banner--error"><AlertTriangle size={14} />{error}<button className="btn btn--ghost btn--xs" onClick={load}>Retry</button></div>}

      <div className="filter-bar">
        <div className="filter-bar__search">
          <Search size={14} className="filter-bar__search-icon" />
          <input className="input" placeholder="Search cases…" value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <div className="filter-bar__chips">
          <Filter size={12} className="text-muted" />
          {STATUS_OPTIONS.map(s => (
            <button key={s} className={`chip${status === s ? ' chip--active' : ''}`} onClick={() => setStatus(s)}>
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
        <span className="text-muted text-xs">{filtered.length} case{filtered.length !== 1 ? 's' : ''}</span>
      </div>

      <div className="card">
        <table className="data-table">
          <thead>
            <tr><th>Name</th><th>Status</th><th>Priority</th><th>Personas</th><th>Analyst</th><th>Created</th><th>Updated</th></tr>
          </thead>
          <tbody>
            {loading && Array.from({ length: 5 }, (_, i) => <tr key={i}><td colSpan={7}><div className="skeleton-row" /></td></tr>)}
            {!loading && filtered.length === 0 && <tr><td colSpan={7} className="text-center text-muted" style={{ padding: '40px 0' }}>No cases found</td></tr>}
            {!loading && filtered.map(c => (
              <tr key={c.id}>
                <td>
                  <span className="font-medium">{c.name}</span>
                  {c.description && <p className="text-muted text-xs" style={{ margin: '2px 0 0' }}>{c.description.slice(0, 80)}{c.description.length > 80 ? '…' : ''}</p>}
                </td>
                <td><span className={`badge ${STATUS_CLS[c.status] ?? 'badge--neutral'}`}>{c.status}</span></td>
                <td><span className={`badge ${PRIORITY_CLS[c.priority] ?? 'badge--neutral'}`}>{c.priority}</span></td>
                <td className="text-muted">{c.persona_ids.length}</td>
                <td className="text-muted text-xs">{c.analyst_id ?? '—'}</td>
                <td className="text-muted text-xs">{new Date(c.created_at).toLocaleDateString()}</td>
                <td className="text-muted text-xs">{new Date(c.updated_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
