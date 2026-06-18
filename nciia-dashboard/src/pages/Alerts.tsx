import { useState, useEffect, useCallback } from 'react';
import { AlertTriangle, RefreshCw, Bell, CheckCircle } from 'lucide-react';
import { fetchAlerts, type Alert } from '../lib/api';
import { useWebSocket } from '../context/WebSocketContext';

const LEVEL_CLS: Record<string, string> = { critical: 'badge--critical', high: 'badge--warning', medium: 'badge--medium', low: 'badge--low' };

export default function Alerts() {
  const { subscribe } = useWebSocket();
  const [alerts, setAlerts]     = useState<Alert[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [filter, setFilter]     = useState<string>('all');

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try { setAlerts(await fetchAlerts({ limit: 200 })); }
    catch (e) { setError(e instanceof Error ? e.message : 'Failed to load alerts'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  // Real-time: reload on new signal or threat events
  useEffect(() => {
    const u1 = subscribe('signal_detected', () => void load());
    const u2 = subscribe('threat_update',   () => void load());
    return () => { u1(); u2(); };
  }, [subscribe, load]);

  const filtered = alerts.filter(a => filter === 'all' || a.level === filter);

  const counts = alerts.reduce<Record<string, number>>((acc, a) => {
    acc[a.level] = (acc[a.level] ?? 0) + 1; return acc;
  }, {});

  return (
    <div className="page-container">
      <header className="page-header">
        <div>
          <h2 className="page-header__title"><Bell size={24} className="icon--danger" /> Alerts</h2>
          <p className="page-header__sub">Real-time threat alerts and detection events</p>
        </div>
        <button className="btn btn--ghost btn--sm" onClick={load} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh
        </button>
      </header>

      {/* Summary chips */}
      <div className="filter-bar">
        {(['all', 'critical', 'high', 'medium', 'low'] as const).map(level => (
          <button
            key={level}
            className={`chip${filter === level ? ' chip--active' : ''}`}
            onClick={() => setFilter(level)}
          >
            {level === 'all' ? `All (${alerts.length})` : `${level.charAt(0).toUpperCase() + level.slice(1)} (${counts[level] ?? 0})`}
          </button>
        ))}
      </div>

      {error && <div className="alert-banner alert-banner--error"><AlertTriangle size={14} />{error}<button className="btn btn--ghost btn--xs" onClick={load}>Retry</button></div>}

      <div className="card">
        {loading && <div className="skeleton-list">{Array.from({ length: 8 }, (_, i) => <div key={i} className="skeleton-row" />)}</div>}
        {!loading && filtered.length === 0 && (
          <div className="empty-state">
            <CheckCircle size={40} className="icon--success" />
            <p>No {filter !== 'all' ? filter : ''} alerts</p>
          </div>
        )}
        {!loading && filtered.map(alert => (
          <div key={alert.id} className={`alert-row${alert.is_acknowledged ? ' alert-row--ack' : ''}`}>
            <div className="alert-row__left">
              <span className={`badge ${LEVEL_CLS[alert.level] ?? 'badge--neutral'}`}>{alert.level}</span>
              <p className="alert-row__msg">{alert.message}</p>
            </div>
            <div className="alert-row__right">
              <time className="text-muted text-xs" dateTime={alert.created_at}>
                {new Date(alert.created_at).toLocaleString()}
              </time>
              {alert.is_acknowledged && <CheckCircle size={14} className="icon--success" />}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
