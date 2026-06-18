import { useCallback, useEffect, useMemo, useState } from 'react';
import { Shield, AlertTriangle, Globe, Unlock, RefreshCw, Search, ExternalLink, Activity, Ban } from 'lucide-react';
import { blockThreat, fetchLiveThreats, type Threat, type ThreatStats, unblockThreat } from '../lib/api';
import { useWebSocket } from '../context/WebSocketContext';

export default function ThreatIntelligence() {
  const { subscribe } = useWebSocket();
  const [threats, setThreats]         = useState<Threat[]>([]);
  const [stats, setStats]             = useState<ThreatStats | null>(null);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterSeverity, setFilterSeverity] = useState('all');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const loadThreats = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchLiveThreats(200);
      setThreats(data.threats);
      setStats(data.stats);
      setLastUpdated(new Date(data.fetched_at));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load live threat intelligence');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadThreats(); }, [loadThreats]);

  // Real-time: reload on WS threat_update events
  useEffect(() => subscribe('threat_update', () => void loadThreats()), [subscribe, loadThreats]);

  const handleBlockIOC = async (ioc: string) => {
    setActionLoading(ioc);
    try {
      await blockThreat(ioc, 'Manual block from dashboard');
      setThreats(prev => prev.map(t => t.value === ioc ? { ...t, is_blocked: true } : t));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Block request failed');
    } finally { setActionLoading(null); }
  };

  const handleUnblockIOC = async (ioc: string) => {
    setActionLoading(ioc);
    try {
      await unblockThreat(ioc);
      setThreats(prev => prev.map(t => t.value === ioc ? { ...t, is_blocked: false } : t));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unblock request failed');
    } finally { setActionLoading(null); }
  };

  const filteredThreats = useMemo(() => threats.filter(threat => {
    const q = searchQuery.toLowerCase();
    const matchesSearch = !q
      || threat.value.toLowerCase().includes(q)
      || threat.description.toLowerCase().includes(q)
      || threat.source.toLowerCase().includes(q)
      || threat.tags.some(t => t.toLowerCase().includes(q));
    const matchesSeverity = filterSeverity === 'all' || threat.severity === filterSeverity;
    return matchesSearch && matchesSeverity;
  }), [filterSeverity, searchQuery, threats]);

  const SEVERITY_COLOR: Record<string, string> = {
    critical: '#ef4444', high: '#f97316', medium: '#eab308', low: '#22c55e',
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'malicious_url': return <Globe size={16} />;
      case 'c2_server':    return <AlertTriangle size={16} />;
      case 'malware_hash': return <Shield size={16} />;
      default:             return <Activity size={16} />;
    }
  };

  return (
    <div className="page-container">
      <header className="page-header">
        <div>
          <h2 className="page-header__title">
            <Shield size={28} className="icon--danger" />
            Real-Time Threat Intelligence
          </h2>
          <p className="page-header__sub">
            Live feed from configured threat intelligence providers
            {lastUpdated && ` · Updated ${lastUpdated.toLocaleTimeString()}`}
          </p>
        </div>
        <button className="btn btn--primary btn--sm" onClick={loadThreats} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'spin' : ''} />
          {loading ? 'Fetching…' : 'Refresh'}
        </button>
      </header>

      {/* Stats */}
      {stats && (
        <div className="stats-grid">
          {[
            { label: 'Total Threats',  value: stats.total,                        mod: '' },
            { label: 'Critical',       value: stats.by_severity?.critical ?? 0,   mod: 'critical' },
            { label: 'High',           value: stats.by_severity?.high ?? 0,        mod: 'warning' },
            { label: 'Blocked',        value: stats.blocked,                       mod: '' },
            { label: 'Sources',        value: Object.keys(stats.by_source ?? {}).length, mod: '' },
          ].map(({ label, value, mod }) => (
            <div key={label} className="stat-card">
              <h3 className="stat-card__label">{label}</h3>
              <div className={`stat-value${mod ? ` stat-value--${mod}` : ''}`}>{value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="filter-bar">
        <div className="filter-bar__search">
          <Search size={16} className="filter-bar__search-icon" />
          <input
            type="text"
            className="input"
            placeholder="Search IOCs, descriptions, tags, sources…"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
          />
        </div>
        <select
          className="input input--select"
          value={filterSeverity}
          onChange={e => setFilterSeverity(e.target.value)}
        >
          <option value="all">All Severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      {/* Error */}
      {error && (
        <div className="alert-banner alert-banner--error" role="alert">
          <AlertTriangle size={14} />
          {error}
          <button className="btn btn--ghost btn--xs" onClick={loadThreats}>Retry</button>
        </div>
      )}

      {/* Feed */}
      <div className="card">
        <div className="card__header">
          <h3 className="card__title">Live Threat Feed ({filteredThreats.length})</h3>
          <span className="badge badge--success"><Activity size={10} className="spin-slow" /> LIVE</span>
        </div>

        {loading && threats.length === 0 && (
          <div className="empty-state">
            <RefreshCw size={32} className="spin icon--muted" />
            <p>Fetching live threat intelligence…</p>
          </div>
        )}

        {!loading && filteredThreats.length === 0 && (
          <div className="empty-state">
            <Shield size={40} className="icon--muted" />
            <p>No threats match your criteria</p>
          </div>
        )}

        <div className="threat-feed">
          {filteredThreats.map(threat => (
            <div
              key={threat.id}
              className={`threat-card${threat.is_blocked ? ' threat-card--blocked' : ''}`}
              style={{ borderLeftColor: SEVERITY_COLOR[threat.severity] ?? '#6b7280' }}
            >
              <div className="threat-card__top">
                <div className="threat-card__identity">
                  <div className="threat-card__icon" style={{ color: SEVERITY_COLOR[threat.severity] }}>
                    {getTypeIcon(threat.type)}
                  </div>
                  <div>
                    <div className="threat-card__meta">
                      <span className={`badge badge--${threat.severity}`}>{threat.severity.toUpperCase()}</span>
                      <span className="text-muted text-xs">{threat.source}</span>
                      {threat.is_blocked && <span className="badge badge--success">BLOCKED</span>}
                    </div>
                    <code className="threat-card__ioc">{threat.value}</code>
                  </div>
                </div>

                <div className="threat-card__actions">
                  {threat.type === 'malicious_url' && (
                    <a
                      href={`https://urlhaus.abuse.ch/browse.php?search=${encodeURIComponent(threat.value)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn btn--ghost btn--xs"
                      aria-label="Open in URLhaus"
                    >
                      <ExternalLink size={12} />
                    </a>
                  )}
                  {threat.is_blocked ? (
                    <button
                      className="btn btn--outline btn--xs"
                      onClick={() => void handleUnblockIOC(threat.value)}
                      disabled={actionLoading === threat.value}
                    >
                      <Unlock size={12} /> Unblock
                    </button>
                  ) : (
                    <button
                      className="btn btn--danger btn--xs"
                      onClick={() => void handleBlockIOC(threat.value)}
                      disabled={actionLoading === threat.value}
                    >
                      <Ban size={12} /> Block
                    </button>
                  )}
                </div>
              </div>

              <p className="threat-card__desc">{threat.description}</p>

              {threat.tags.length > 0 && (
                <div className="tag-list">
                  {threat.tags.slice(0, 6).map(tag => (
                    <span key={tag} className="tag">{tag}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
