import { useState, useEffect, useCallback } from 'react';
import { Bot, Play, Square, RefreshCw, AlertTriangle, CheckCircle, Clock, Cpu } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

interface AgentStat {
  agent: string;
  description: string;
  running: boolean;
  run_count: number;
  last_run: number | null;
  findings_count: number;
  interval_seconds: number;
}

interface Finding {
  id: string;
  agent_name: string;
  title: string;
  description: string;
  severity: string;
  iocs: string[];
  related_persona_ids: string[];
  evidence: Record<string, unknown>[];
  attack_techniques: string[];
  created_at: number;
}

const SEVERITY_CLS: Record<string, string> = {
  critical: 'badge--critical', high: 'badge--warning',
  medium: 'badge--medium', low: 'badge--low',
};

const AGENT_ICONS: Record<string, string> = {
  PivotHunter: '🔗',
  PatternHunter: '📊',
  DarkWebMonitor: '🌑',
  AttributionHunter: '🎯',
};

export default function HunterAgents() {
  const [agents, setAgents]     = useState<AgentStat[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const loadAll = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [statsResp, findingsResp] = await Promise.all([
        fetch(`${API_BASE}/api/advanced/hunters/stats`),
        fetch(`${API_BASE}/api/advanced/hunters/findings?limit=50`),
      ]);
      if (!statsResp.ok) throw new Error(`Stats: HTTP ${statsResp.status}`);
      if (!findingsResp.ok) throw new Error(`Findings: HTTP ${findingsResp.status}`);

      setAgents(await statsResp.json());
      const fd = await findingsResp.json();
      setFindings(fd.findings ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load hunter data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadAll(); }, [loadAll]);

  // Auto-refresh every 60s
  useEffect(() => {
    const t = setInterval(() => void loadAll(), 60_000);
    return () => clearInterval(t);
  }, [loadAll]);

  const toggleAll = async (action: 'start' | 'stop') => {
    setActionLoading(true);
    try {
      await fetch(`${API_BASE}/api/advanced/hunters/${action}`, { method: 'POST' });
      await loadAll();
    } finally { setActionLoading(false); }
  };

  const anyRunning = agents.some(a => a.running);
  const totalFindings = agents.reduce((s, a) => s + a.findings_count, 0);

  return (
    <div className="page-container">
      <header className="page-header">
        <div>
          <h2 className="page-header__title">
            <Bot size={24} className="icon--primary" />
            Autonomous Hunter Agents
          </h2>
          <p className="page-header__sub">
            Self-directed AI agents that proactively discover threats without analyst intervention
          </p>
        </div>
        <div className="page-header__actions">
          <button className="btn btn--ghost btn--sm" onClick={loadAll} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
          </button>
          {anyRunning ? (
            <button className="btn btn--danger btn--sm" onClick={() => void toggleAll('stop')} disabled={actionLoading}>
              <Square size={14} /> Stop All
            </button>
          ) : (
            <button className="btn btn--primary btn--sm" onClick={() => void toggleAll('start')} disabled={actionLoading}>
              <Play size={14} /> Start All
            </button>
          )}
        </div>
      </header>

      {error && <div className="alert-banner alert-banner--error"><AlertTriangle size={14} />{error}</div>}

      {/* Stats summary */}
      <div className="stats-grid">
        {[
          { label: 'Active Agents',    value: agents.filter(a => a.running).length },
          { label: 'Total Findings',   value: totalFindings },
          { label: 'Agents Running',   value: `${agents.filter(a => a.running).length} / ${agents.length}` },
          { label: 'Total Hunt Runs',  value: agents.reduce((s, a) => s + a.run_count, 0) },
        ].map(({ label, value }) => (
          <div key={label} className="stat-card">
            <div className="stat-card__label">{label}</div>
            <div className="stat-value">{value}</div>
          </div>
        ))}
      </div>

      {/* Agent cards */}
      <div className="hunter-agents-grid">
        {loading && !agents.length
          ? Array.from({ length: 4 }, (_, i) => <div key={i} className="card skeleton-card" />)
          : agents.map(agent => (
            <div key={agent.agent} className={`card hunter-agent-card${agent.running ? ' hunter-agent-card--running' : ''}`}>
              <div className="hunter-agent-card__header">
                <div className="hunter-agent-card__icon">
                  {AGENT_ICONS[agent.agent] ?? '🤖'}
                </div>
                <div className="hunter-agent-card__info">
                  <h3 className="hunter-agent-card__name">{agent.agent}</h3>
                  <p className="hunter-agent-card__desc text-muted text-xs">{agent.description}</p>
                </div>
                <div>
                  {agent.running
                    ? <span className="badge badge--success"><span className="live-dot" /> Running</span>
                    : <span className="badge badge--neutral">Idle</span>}
                </div>
              </div>
              <div className="hunter-agent-card__stats">
                <div className="hunter-stat">
                  <Cpu size={12} className="text-muted" />
                  <span>{agent.run_count} runs</span>
                </div>
                <div className="hunter-stat">
                  <CheckCircle size={12} className="icon--success" />
                  <span>{agent.findings_count} findings</span>
                </div>
                <div className="hunter-stat">
                  <Clock size={12} className="text-muted" />
                  <span>Every {Math.round(agent.interval_seconds / 60)}m</span>
                </div>
              </div>
              {agent.last_run && (
                <div className="text-muted text-xs" style={{ marginTop: 8 }}>
                  Last run: {new Date(agent.last_run * 1000).toLocaleString()}
                </div>
              )}
            </div>
          ))}
      </div>

      {/* Findings feed */}
      <div className="card">
        <div className="card__header">
          <h3 className="card__title">Recent Findings ({findings.length})</h3>
          <span className="badge badge--success"><span className="live-dot" /> Auto-updating</span>
        </div>

        {findings.length === 0 && !loading ? (
          <div className="empty-state">
            <Bot size={40} className="icon--muted" />
            <p>No findings yet — agents are hunting…</p>
          </div>
        ) : (
          <div className="findings-feed">
            {findings.map(finding => (
              <div key={finding.id} className="finding-card">
                <div className="finding-card__header">
                  <div className="finding-card__meta">
                    <span className={`badge ${SEVERITY_CLS[finding.severity] ?? 'badge--neutral'}`}>
                      {finding.severity}
                    </span>
                    <span className="badge badge--neutral">{finding.agent_name}</span>
                    <span className="text-muted text-xs">
                      {new Date(finding.created_at * 1000).toLocaleString()}
                    </span>
                  </div>
                  <h4 className="finding-card__title">{finding.title}</h4>
                  <p className="finding-card__desc text-muted text-sm">{finding.description}</p>
                </div>

                {finding.iocs.length > 0 && (
                  <div className="finding-card__section">
                    <span className="text-muted text-xs">IOCs</span>
                    <div className="tag-list">
                      {finding.iocs.slice(0, 5).map(ioc => (
                        <code key={ioc} className="tag" style={{ fontFamily: 'monospace' }}>{ioc}</code>
                      ))}
                    </div>
                  </div>
                )}

                {finding.attack_techniques.length > 0 && (
                  <div className="finding-card__section">
                    <span className="text-muted text-xs">ATT&amp;CK Techniques</span>
                    <div className="tag-list">
                      {finding.attack_techniques.map(tid => (
                        <a key={tid} href={`https://attack.mitre.org/techniques/${tid}/`}
                          target="_blank" rel="noopener noreferrer" className="tag tag--link">
                          {tid}
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
