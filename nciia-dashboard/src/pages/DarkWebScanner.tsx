import { useState, useCallback } from 'react';
import { Search, AlertTriangle, Loader, ExternalLink, Globe } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

interface DarkWebHit { source: string; title: string; url: string; snippet: string; onion: string; }
interface DarkWebResult { query: string; total_found: number; risk_level: string; sources_hit: string[]; hits: DarkWebHit[]; errors: string[]; }

const RISK_COLOR = (r: string) =>
  r.includes('Critical') ? '#ef4444' : r.includes('High') ? '#f97316' : r.includes('Medium') ? '#eab308' : '#22c55e';

export default function DarkWebScanner() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<DarkWebResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const scan = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true); setError(null); setResult(null);
    try {
      const r = await fetch(`${API_BASE}/api/osint/darkweb`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query.trim() }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setResult(await r.json());
    } catch (e) { setError(e instanceof Error ? e.message : 'Scan failed'); }
    finally { setLoading(false); }
  }, [query]);

  return (
    <div className="page-container">
      <header className="page-header">
        <div>
          <h2 className="page-header__title"><Globe size={22} className="icon--error" /> Dark Web Scanner</h2>
          <p className="page-header__sub">Search Ahmia · DarkSearch · IntelX · Paste sites — no Tor browser required</p>
        </div>
      </header>

      <div className="card">
        <div style={{ display: 'flex', gap: 10 }}>
          <div className="filter-bar__search" style={{ flex: 1 }}>
            <Search size={15} className="filter-bar__search-icon" />
            <input className="input" style={{ paddingLeft: 32 }}
              placeholder="Phone number, email, username, or full name…"
              value={query} onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && scan()} />
          </div>
          <button className="btn btn--primary" onClick={scan} disabled={loading || !query.trim()}>
            {loading ? <><Loader size={14} className="spin" /> Scanning dark web…</> : <><Search size={14} /> Scan</>}
          </button>
        </div>
        <p className="text-muted text-xs" style={{ marginTop: 8 }}>Searches 4 dark web index services in parallel. May take 15-30 seconds.</p>
      </div>

      {error && <div className="alert-banner alert-banner--error"><AlertTriangle size={14} /> {error}</div>}

      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Summary */}
          <div className="card" style={{ borderColor: RISK_COLOR(result.risk_level), borderWidth: 2 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 20, flexWrap: 'wrap' }}>
              <div>
                <div style={{ fontSize: 28, fontWeight: 800, color: RISK_COLOR(result.risk_level) }}>{result.risk_level}</div>
                <div className="text-muted text-xs" style={{ marginTop: 4 }}>for "{result.query}"</div>
              </div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <span className="badge badge--neutral">{result.total_found} results found</span>
                {result.sources_hit.map(s => <span key={s} className="tag">{s}</span>)}
              </div>
            </div>
          </div>

          {/* Hits */}
          {result.hits.length === 0 ? (
            <div className="card"><div className="empty-state"><Globe size={28} className="icon--muted" /><p>No dark web mentions found — this is a good sign.</p></div></div>
          ) : (
            <div className="card">
              <div className="card__header"><h3 className="card__title">Dark Web Mentions ({result.hits.length})</h3></div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 8 }}>
                {result.hits.map((hit, i) => (
                  <div key={i} style={{ padding: 14, background: 'rgba(239,68,68,0.05)', borderRadius: 8, border: '1px solid rgba(239,68,68,0.15)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                      <div>
                        <span className="badge badge--neutral" style={{ marginRight: 8 }}>{hit.source}</span>
                        {hit.onion && <span className="tag" style={{ color: '#ef4444', fontSize: 11 }}>🧅 .onion</span>}
                      </div>
                      <a href={hit.url} target="_blank" rel="noopener noreferrer" className="btn btn--ghost btn--sm">
                        <ExternalLink size={12} /> View
                      </a>
                    </div>
                    <div style={{ fontWeight: 600, marginBottom: 4 }}>{hit.title || hit.url}</div>
                    {hit.snippet && <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5 }}>{hit.snippet}</p>}
                    <code style={{ fontSize: 10, color: 'var(--text-muted)', display: 'block', marginTop: 4, wordBreak: 'break-all' }}>{hit.url}</code>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
