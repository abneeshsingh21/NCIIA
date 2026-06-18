import { useState, useEffect, useCallback } from 'react';
import { Shield, RefreshCw, Download, AlertTriangle } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

interface TechniqueEntry {
  technique_id: string;
  name: string;
  tactic: string;
  count?: number;
  score?: number;
}

interface TacticSummary {
  [tactic: string]: number;
}

interface TaggedSignal {
  signal_id: string;
  source: string;
  techniques: TechniqueEntry[];
}

const TACTIC_ORDER = [
  'Reconnaissance', 'Resource Development', 'Initial Access', 'Execution',
  'Persistence', 'Privilege Escalation', 'Defense Evasion', 'Credential Access',
  'Discovery', 'Lateral Movement', 'Collection', 'Command and Control',
  'Exfiltration', 'Impact',
];

const TACTIC_COLOR: Record<string, string> = {
  'Reconnaissance':        '#6366f1',
  'Resource Development':  '#8b5cf6',
  'Initial Access':        '#ec4899',
  'Execution':             '#ef4444',
  'Persistence':           '#f97316',
  'Privilege Escalation':  '#f59e0b',
  'Defense Evasion':       '#eab308',
  'Credential Access':     '#84cc16',
  'Discovery':             '#22c55e',
  'Lateral Movement':      '#10b981',
  'Collection':            '#06b6d4',
  'Command and Control':   '#0ea5e9',
  'Exfiltration':          '#3b82f6',
  'Impact':                '#a855f7',
};

export default function AttackMap() {
  const [tacticSummary, setTacticSummary] = useState<TacticSummary>({});
  const [taggedSignals, setTaggedSignals]  = useState<TaggedSignal[]>([]);
  const [total, setTotal]                  = useState(0);
  const [withTech, setWithTech]            = useState(0);
  const [loading, setLoading]              = useState(true);
  const [error, setError]                  = useState<string | null>(null);
  const [selected, setSelected]            = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const resp = await fetch(`${API_BASE}/api/attack/signals/tagged?limit=200`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setTacticSummary(data.tactic_summary ?? {});
      setTaggedSignals(data.tagged_signals ?? []);
      setTotal(data.total_signals ?? 0);
      setWithTech(data.signals_with_techniques ?? 0);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load ATT&CK data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const downloadLayer = async () => {
    const resp = await fetch(`${API_BASE}/api/attack/navigator/layer`);
    const json = await resp.json();
    const blob = new Blob([JSON.stringify(json, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'nciia-attack-layer.json'; a.click();
    URL.revokeObjectURL(url);
  };

  const maxCount = Math.max(...Object.values(tacticSummary), 1);

  // Signals for selected tactic
  const filteredSignals = selected
    ? taggedSignals.filter(s => s.techniques.some(t => t.tactic === selected))
    : taggedSignals;

  return (
    <div className="page-container">
      <header className="page-header">
        <div>
          <h2 className="page-header__title">
            <Shield size={24} className="icon--danger" />
            MITRE ATT&amp;CK Coverage Map
          </h2>
          <p className="page-header__sub">
            {withTech} / {total} signals mapped to {Object.keys(tacticSummary).length} tactics
          </p>
        </div>
        <div className="page-header__actions">
          <button className="btn btn--ghost btn--sm" onClick={load} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
          </button>
          <button className="btn btn--primary btn--sm" onClick={downloadLayer}>
            <Download size={14} /> Navigator Layer
          </button>
        </div>
      </header>

      {error && <div className="alert-banner alert-banner--error"><AlertTriangle size={14} />{error}</div>}

      {/* Tactic heatmap */}
      <div className="card">
        <div className="card__header">
          <h3 className="card__title">Tactic Coverage Heatmap</h3>
          {selected && (
            <button className="btn btn--ghost btn--xs" onClick={() => setSelected(null)}>
              Clear filter
            </button>
          )}
        </div>
        <div className="attack-heatmap">
          {TACTIC_ORDER.map(tactic => {
            const count = tacticSummary[tactic] ?? 0;
            const intensity = count / maxCount;
            const color = TACTIC_COLOR[tactic] ?? '#6b7280';
            const isSelected = selected === tactic;

            return (
              <div
                key={tactic}
                className={`attack-tactic-cell${count > 0 ? ' attack-tactic-cell--active' : ''}${isSelected ? ' attack-tactic-cell--selected' : ''}`}
                style={{
                  backgroundColor: count > 0
                    ? `${color}${Math.round(intensity * 180 + 40).toString(16).padStart(2, '0')}`
                    : undefined,
                  borderColor: isSelected ? color : undefined,
                }}
                onClick={() => count > 0 && setSelected(isSelected ? null : tactic)}
                title={`${tactic}: ${count} technique(s)`}
              >
                <span className="attack-tactic-cell__name">{tactic}</span>
                <span className="attack-tactic-cell__count" style={{ color: count > 0 ? color : undefined }}>
                  {count > 0 ? count : '—'}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Tagged signals table */}
      <div className="card">
        <div className="card__header">
          <h3 className="card__title">
            Mapped Signals
            {selected && <span className="badge badge--primary" style={{ marginLeft: 8 }}>{selected}</span>}
            <span className="text-muted text-xs" style={{ marginLeft: 8 }}>({filteredSignals.length})</span>
          </h3>
        </div>
        {filteredSignals.length === 0 ? (
          <div className="empty-state">
            <Shield size={36} className="icon--muted" />
            <p>No signals mapped to ATT&amp;CK techniques yet</p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr><th>Source</th><th>Techniques Detected</th><th>Top Tactic</th></tr>
            </thead>
            <tbody>
              {filteredSignals.slice(0, 50).map(s => (
                <tr key={s.signal_id}>
                  <td className="font-medium text-sm">{s.source}</td>
                  <td>
                    <div className="tag-list">
                      {s.techniques.slice(0, 4).map(t => (
                        <a
                          key={t.technique_id}
                          href={`https://attack.mitre.org/techniques/${t.technique_id}/`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="tag tag--link"
                          title={t.name}
                        >
                          {t.technique_id}
                        </a>
                      ))}
                      {s.techniques.length > 4 && (
                        <span className="tag">+{s.techniques.length - 4}</span>
                      )}
                    </div>
                  </td>
                  <td>
                    <span
                      className="badge"
                      style={{
                        background: `${TACTIC_COLOR[s.techniques[0]?.tactic] ?? '#6b7280'}22`,
                        color: TACTIC_COLOR[s.techniques[0]?.tactic] ?? '#6b7280',
                        border: `1px solid ${TACTIC_COLOR[s.techniques[0]?.tactic] ?? '#6b7280'}44`,
                      }}
                    >
                      {s.techniques[0]?.tactic ?? '—'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
