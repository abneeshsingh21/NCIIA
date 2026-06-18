import React, { useState, useEffect, useRef, Suspense, Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, Users, Radio, TrendingUp, Shield, Zap, Globe, Activity, RefreshCw } from 'lucide-react';
import ThreatMeter from '../components/ThreatMeter';
import NetworkGraph from '../components/NetworkGraph';
import { fetchDashboardStats, fetchAlerts, fetchPersonas, type DashboardStats, type Alert, type Persona } from '../lib/api';
import { useWebSocket } from '../context/WebSocketContext';

const ThreatGlobe = React.lazy(() => import('../components/ThreatGlobe'));

// ─── Error boundary ──────────────────────────────────────────────────────────

class WidgetErrorBoundary extends Component<
  { children: ReactNode; fallback: (err: string) => ReactNode },
  { error: string | null }
> {
  state = { error: null };
  static getDerivedStateFromError(e: Error) { return { error: e.message }; }
  componentDidCatch(e: Error, info: ErrorInfo) { console.error('[Widget]', e, info); }
  render() {
    return this.state.error
      ? this.props.fallback(this.state.error)
      : this.props.children;
  }
}

function WidgetError({ label, error }: { label: string; error?: string }) {
  return (
    <div className="widget-error">
      <Globe size={40} className="widget-error__icon" />
      <span>{error ? `${label}: ${error}` : `Loading ${label}…`}</span>
    </div>
  );
}

// ─── Animated counter ────────────────────────────────────────────────────────

function useAnimatedCounter(target: number, duration = 1200) {
  const [count, setCount] = useState(0);
  const frame = useRef<number>();
  useEffect(() => {
    const start = performance.now();
    const tick = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      setCount(Math.round(p * target));
      if (p < 1) frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => { if (frame.current) cancelAnimationFrame(frame.current); };
  }, [target, duration]);
  return count;
}

// ─── Severity badge ──────────────────────────────────────────────────────────

function SeverityBadge({ level }: { level: string }) {
  return <span className={`badge badge--${level}`}>{level}</span>;
}

// ─── Main dashboard ──────────────────────────────────────────────────────────

export default function Dashboard() {
  const { subscribe } = useWebSocket();

  const [stats, setStats]         = useState<DashboardStats | null>(null);
  const [alerts, setAlerts]       = useState<Alert[]>([]);
  const [personas, setPersonas]   = useState<Persona[]>([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const loadAll = async () => {
    try {
      setLoading(true);
      setError(null);
      const [s, a, p] = await Promise.all([
        fetchDashboardStats(),
        fetchAlerts({ limit: 10 }),
        fetchPersonas({ limit: 20 }),
      ]);
      setStats(s);
      setAlerts(a);
      setPersonas(p);
      setLastRefresh(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  // Initial load
  useEffect(() => { loadAll(); }, []);

  // Real-time: refresh stats when WS pushes a relevant event
  useEffect(() => {
    const unsub = subscribe('threat_update', () => loadAll());
    return unsub;
  }, [subscribe]);

  // ── Animated stat counters ────────────────────────────────────────────────
  const animPersonas     = useAnimatedCounter(stats?.active_personas     ?? 0);
  const animSignals      = useAnimatedCounter(stats?.signals_today        ?? 0);
  const animThreats      = useAnimatedCounter(stats?.critical_threats     ?? 0);
  const animEscalations  = useAnimatedCounter(stats?.escalations_24h      ?? 0);

  const STAT_CARDS = [
    { label: 'Active Personas',  value: animPersonas,    Icon: Users,         mod: '' },
    { label: 'Signals Today',    value: animSignals,     Icon: Radio,         mod: '' },
    { label: 'Critical Threats', value: animThreats,     Icon: AlertTriangle, mod: 'critical' },
    { label: 'Escalations (24h)',value: animEscalations, Icon: Zap,           mod: 'warning' },
  ] as const;

  return (
    <div className="page-container">
      {/* Header */}
      <header className="page-header">
        <div>
          <h2 className="page-header__title">
            <Shield size={28} className="icon--primary" />
            Intelligence Dashboard
          </h2>
          <p className="page-header__sub">Real-time threat monitoring &amp; analysis</p>
        </div>
        <div className="page-header__actions">
          {lastRefresh && (
            <span className="text-muted text-xs">
              Updated {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button className="btn btn--ghost btn--sm" onClick={loadAll} disabled={loading} aria-label="Refresh">
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            Refresh
          </button>
          <div className="live-badge">
            <span className="live-dot" />
            Live Monitoring
          </div>
        </div>
      </header>

      {/* Error banner */}
      {error && (
        <div className="alert-banner alert-banner--error" role="alert">
          <AlertTriangle size={16} />
          {error}
          <button className="btn btn--ghost btn--xs" onClick={loadAll}>Retry</button>
        </div>
      )}

      {/* Stat cards */}
      <div className="stats-grid">
        {STAT_CARDS.map(({ label, value, Icon, mod }) => (
          <div key={label} className="stat-card">
            <div className="stat-card__header">
              <h3 className="stat-card__label">{label}</h3>
              <Icon size={18} className={`icon--${mod || 'primary'} icon--muted`} />
            </div>
            <div className={`stat-value${mod ? ` stat-value--${mod}` : ''}`}>
              {loading ? '—' : value.toLocaleString()}
            </div>
          </div>
        ))}
      </div>

      {/* Globe + Alerts row */}
      <div className="dashboard-grid">
        {/* 3D Threat Globe */}
        <div className="card card--canvas">
          <div className="card__header">
            <h3 className="card__title">
              <Globe size={16} className="icon--primary" />
              Global Threat Map
            </h3>
            <span className="badge badge--success">
              <Activity size={10} /> LIVE
            </span>
          </div>
          <WidgetErrorBoundary fallback={(e) => <WidgetError label="3D Globe" error={e} />}>
            <Suspense fallback={<WidgetError label="3D Globe" />}>
              <ThreatGlobe height="350px" />
            </Suspense>
          </WidgetErrorBoundary>
        </div>

        {/* Live Alerts */}
        <div className="card">
          <div className="card__header">
            <h3 className="card__title">
              <AlertTriangle size={16} className="icon--danger" />
              Recent Alerts
            </h3>
            <span className="text-muted text-xs">Last 24 h</span>
          </div>
          <div className="card__scroll">
            {loading && <div className="skeleton-list" aria-busy="true">{Array.from({ length: 4 }, (_, i) => <div key={i} className="skeleton-row" />)}</div>}
            {!loading && alerts.length === 0 && (
              <div className="empty-state">
                <AlertTriangle size={32} className="icon--muted" />
                <p>No alerts in the last 24 hours</p>
              </div>
            )}
            {!loading && alerts.map((alert) => (
              <div key={alert.id} className="alert-row">
                <div>
                  <div className="alert-row__meta">
                    <SeverityBadge level={alert.level} />
                  </div>
                  <p className="alert-row__msg">{alert.message}</p>
                </div>
                <time className="text-muted text-xs" dateTime={alert.created_at}>
                  {new Date(alert.created_at).toLocaleTimeString()}
                </time>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Network Graph */}
      <div className="card card--canvas">
        <div className="card__header">
          <h3 className="card__title">
            <Users size={16} className="icon--secondary" />
            Threat Nexus Graph
          </h3>
        </div>
        <div className="canvas-frame">
          <WidgetErrorBoundary fallback={(e) => <WidgetError label="Network Graph" error={e} />}>
            <NetworkGraph />
          </WidgetErrorBoundary>
        </div>
      </div>

      {/* Top Threat Personas table — live data */}
      <div className="card" style={{ marginTop: '20px' }}>
        <div className="card__header">
          <h3 className="card__title">
            <TrendingUp size={16} className="icon--warning" />
            Top Threat Personas
          </h3>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Identifier</th>
              <th>Threat Level</th>
              <th>Platforms</th>
              <th>Last Activity</th>
              <th>Watch</th>
            </tr>
          </thead>
          <tbody>
            {loading && Array.from({ length: 3 }, (_, i) => (
              <tr key={i}><td colSpan={5}><div className="skeleton-row" /></td></tr>
            ))}
            {!loading && personas.length === 0 && (
              <tr><td colSpan={5} className="text-center text-muted">No personas found</td></tr>
            )}
            {!loading && personas.map((p) => (
              <tr key={p.id}>
                <td className="font-medium">{p.primary_identifier}</td>
                <td>
                  {p.threat_score
                    ? <ThreatMeter score={Math.round((p.threat_score.score ?? p.threat_score.overall_score ?? 0) * 100)} />
                    : <span className="text-muted">—</span>}
                </td>
                <td className="text-muted">{p.platforms_detected.join(', ') || '—'}</td>
                <td className="text-muted text-xs">
                  {p.last_activity ? new Date(p.last_activity).toLocaleString() : '—'}
                </td>
                <td>
                  {p.is_active_watch
                    ? <span className="badge badge--success">Watching</span>
                    : <span className="badge badge--neutral">Idle</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
