import { useState, useCallback } from 'react';
import {
  Search, Phone, User, Mail, AlertTriangle, CheckCircle,
  ExternalLink, Loader, Shield, Globe, Hash
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

// ── Types ─────────────────────────────────────────────────────────────────────

interface PhoneProfileOut {
  raw_input: string; normalized: string;
  country_code: string; country_name: string;
  carrier: string; line_type: string;
  location: string; timezone: string;
  is_valid: boolean;
  whatsapp_active: boolean; telegram_active: boolean;
  spam_score: number; fraud_reports: number;
  spam_labels: string[]; spam_databases: string[];
  errors: Record<string, string>;
}

interface EmailProfileOut {
  email: string; valid_format: boolean; domain: string;
  disposable: boolean; breach_count: number;
  breach_names: string[]; gravatar_url: string;
}

interface SocialHitOut {
  platform: string; username: string; url: string;
  exists: boolean; bio: string; name: string;
}

interface ScammerProfileOut {
  input_phone: string | null; input_username: string | null;
  input_email: string | null; input_name: string | null;
  phone: PhoneProfileOut | null;
  email_profile: EmailProfileOut | null;
  social_hits: SocialHitOut[];
  likely_names: string[]; likely_locations: string[];
  fraud_score: number; fraud_verdict: string;
  fraud_evidence: string[];
  sources_queried: string[];
  enriched_at: number;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const SCORE_COLOR = (s: number) =>
  s >= 75 ? '#ef4444' : s >= 50 ? '#f97316' : s >= 25 ? '#eab308' : '#22c55e';

const PLATFORM_ICONS: Record<string, string> = {
  Instagram: '📸', Twitter: '🐦', 'Twitter/X': '🐦', GitHub: '💻',
  LinkedIn: '💼', Reddit: '🤖', TikTok: '🎵', YouTube: '▶️',
  Telegram: '✈️', Pinterest: '📌', Snapchat: '👻', Facebook: '📘',
  WhatsApp: '📱',
};

function FraudGauge({ score }: { score: number }) {
  const color = SCORE_COLOR(score);
  const pct = Math.min(score, 100);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
      <svg viewBox="0 0 120 70" style={{ width: 140 }}>
        <path d="M10 65 A55 55 0 0 1 110 65" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="12" strokeLinecap="round" />
        <path d="M10 65 A55 55 0 0 1 110 65" fill="none" stroke={color} strokeWidth="12" strokeLinecap="round"
          strokeDasharray={`${(pct / 100) * 172.8} 172.8`} />
        <text x="60" y="58" textAnchor="middle" fontSize="22" fontWeight="800" fill={color}>{score}</text>
      </svg>
      <span style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>
        Fraud Risk Score
      </span>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value?: React.ReactNode }) {
  if (!value && value !== 0) return null;
  return (
    <div className="info-row">
      <span className="info-row__label">{label}</span>
      <span className="info-row__value">{value}</span>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ScamInvestigator() {
  const [phone, setPhone]       = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail]       = useState('');
  const [name, setName]         = useState('');
  const [result, setResult]     = useState<ScammerProfileOut | null>(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);
  const [stage, setStage]       = useState('');

  const investigate = useCallback(async () => {
    if (!phone && !username && !email && !name) {
      setError('Enter at least one identifier — phone, username, email, or name.');
      return;
    }
    setLoading(true); setError(null); setResult(null);

    const stages = ['Querying phone databases…', 'Enumerating social media…', 'Checking breach records…', 'Aggregating fraud evidence…'];
    let i = 0;
    const ticker = setInterval(() => { setStage(stages[i % stages.length]); i++; }, 2000);

    try {
      const resp = await fetch(`${API_BASE}/api/investigate/scammer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone:    phone    || null,
          username: username || null,
          email:    email    || null,
          name:     name     || null,
        }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setResult(await resp.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Investigation failed');
    } finally {
      clearInterval(ticker);
      setLoading(false); setStage('');
    }
  }, [phone, username, email, name]);

  const hasInput = phone || username || email || name;

  return (
    <div className="page-container">
      {/* Header */}
      <header className="page-header">
        <div>
          <h2 className="page-header__title">
            <Shield size={24} className="icon--primary" />
            Scammer &amp; Fraud Investigator
          </h2>
          <p className="page-header__sub">
            Phone OSINT · Social Media Footprint · Breach Records · Fraud Score
          </p>
        </div>
      </header>

      {/* Input Form */}
      <div className="card">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
          <div className="filter-bar__search">
            <Phone size={15} className="filter-bar__search-icon" />
            <input className="input" style={{ paddingLeft: 32 }}
              placeholder="Mobile / Phone number (e.g. +91XXXXXXXXXX)"
              value={phone} onChange={e => setPhone(e.target.value)} />
          </div>
          <div className="filter-bar__search">
            <User size={15} className="filter-bar__search-icon" />
            <input className="input" style={{ paddingLeft: 32 }}
              placeholder="Social media username"
              value={username} onChange={e => setUsername(e.target.value)} />
          </div>
          <div className="filter-bar__search">
            <Mail size={15} className="filter-bar__search-icon" />
            <input className="input" style={{ paddingLeft: 32 }}
              placeholder="Email address"
              value={email} onChange={e => setEmail(e.target.value)} />
          </div>
          <div className="filter-bar__search">
            <Search size={15} className="filter-bar__search-icon" />
            <input className="input" style={{ paddingLeft: 32 }}
              placeholder="Full name or alias"
              value={name} onChange={e => setName(e.target.value)} />
          </div>
        </div>
        <button className="btn btn--primary" style={{ width: '100%', padding: '12px', fontSize: 15 }}
          onClick={investigate} disabled={loading || !hasInput}>
          {loading
            ? <><Loader size={15} className="spin" /> {stage || 'Investigating…'}</>
            : <><Search size={15} /> Investigate Now</>}
        </button>
        <p className="text-muted text-xs" style={{ marginTop: 10, textAlign: 'center' }}>
          For fraud investigation &amp; law-enforcement use only. All queries are logged.
        </p>
      </div>

      {error && (
        <div className="alert-banner alert-banner--error">
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {/* Results */}
      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Fraud verdict banner */}
          <div className="card" style={{ borderColor: SCORE_COLOR(result.fraud_score), borderWidth: 2 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 24, flexWrap: 'wrap' }}>
              <FraudGauge score={result.fraud_score} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 22, fontWeight: 800, color: SCORE_COLOR(result.fraud_score), marginBottom: 8 }}>
                  {result.fraud_verdict}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {result.fraud_evidence.map((ev, i) => (
                    <span key={i} className="tag" style={{ color: SCORE_COLOR(result.fraud_score) }}>
                      ⚠ {ev}
                    </span>
                  ))}
                  {result.fraud_evidence.length === 0 && (
                    <span className="tag" style={{ color: '#22c55e' }}>
                      <CheckCircle size={12} /> No fraud signals detected
                    </span>
                  )}
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 13 }}>
                <span className="badge badge--neutral">
                  🔍 {result.sources_queried.length} sources queried
                </span>
                <span className="badge badge--neutral">
                  🌐 {result.social_hits.length} social profiles found
                </span>
                <span className="text-muted text-xs">
                  {new Date(result.enriched_at * 1000).toLocaleString()}
                </span>
              </div>
            </div>
          </div>

          <div className="enrich-grid">

            {/* Phone Intelligence */}
            {result.phone && (
              <div className="card">
                <div className="card__header">
                  <h3 className="card__title"><Phone size={14} className="icon--primary" /> Phone Intelligence</h3>
                  {result.phone.is_valid
                    ? <span className="badge badge--success">Valid</span>
                    : <span className="badge badge--neutral">Unverified</span>}
                </div>
                <InfoRow label="Number"     value={<code>{result.phone.normalized || result.phone.raw_input}</code>} />
                <InfoRow label="Country"    value={`${result.phone.country_name} (${result.phone.country_code})`} />
                <InfoRow label="Carrier"    value={result.phone.carrier} />
                <InfoRow label="Line Type"  value={
                  <span style={{ color: result.phone.line_type === 'voip' ? '#f97316' : 'inherit', textTransform: 'capitalize' }}>
                    {result.phone.line_type}
                  </span>
                } />
                <InfoRow label="Location"   value={result.phone.location} />
                <InfoRow label="Timezone"   value={result.phone.timezone} />
                <div className="info-row">
                  <span className="info-row__label">Presence</span>
                  <div className="tag-list">
                    {result.phone.whatsapp_active && <span className="tag" style={{ color: '#22c55e' }}>📱 WhatsApp</span>}
                    {result.phone.telegram_active && <span className="tag" style={{ color: '#2ca5e0' }}>✈️ Telegram</span>}
                    {!result.phone.whatsapp_active && !result.phone.telegram_active &&
                      <span className="text-muted text-xs">Not detected</span>}
                  </div>
                </div>
                <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <span className="info-row__label">Spam Score</span>
                    <span style={{ fontWeight: 700, color: SCORE_COLOR(result.phone.spam_score) }}>
                      {result.phone.spam_score}/100
                    </span>
                  </div>
                  <div style={{ height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
                    <div style={{
                      height: '100%', width: `${result.phone.spam_score}%`,
                      background: SCORE_COLOR(result.phone.spam_score),
                      transition: 'width 1s ease', borderRadius: 3,
                    }} />
                  </div>
                  {result.phone.spam_databases.length > 0 && (
                    <div className="tag-list" style={{ marginTop: 8 }}>
                      {result.phone.spam_databases.map(db => (
                        <span key={db} className="tag" style={{ color: '#ef4444' }}>🚨 {db}</span>
                      ))}
                    </div>
                  )}
                  {result.phone.fraud_reports > 0 && (
                    <InfoRow label="Reports" value={
                      <span style={{ color: '#ef4444', fontWeight: 700 }}>{result.phone.fraud_reports} community fraud reports</span>
                    } />
                  )}
                </div>
              </div>
            )}

            {/* Email Intelligence */}
            {result.email_profile && (
              <div className="card">
                <div className="card__header">
                  <h3 className="card__title"><Mail size={14} className="icon--primary" /> Email Intelligence</h3>
                  {result.email_profile.disposable
                    ? <span className="badge badge--critical">Disposable ⚠</span>
                    : <span className="badge badge--success">Permanent</span>}
                </div>
                {result.email_profile.gravatar_url && (
                  <img
                    src={result.email_profile.gravatar_url.replace('?d=404', '?d=identicon')}
                    alt="Gravatar"
                    style={{ width: 64, height: 64, borderRadius: '50%', marginBottom: 12, border: '2px solid rgba(255,255,255,0.1)' }}
                    onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                  />
                )}
                <InfoRow label="Address" value={<code style={{ fontSize: 12 }}>{result.email_profile.email}</code>} />
                <InfoRow label="Domain" value={result.email_profile.domain} />
                <InfoRow label="Disposable" value={
                  result.email_profile.disposable
                    ? <span style={{ color: '#f97316' }}>⚠ Yes — throwaway domain</span>
                    : <span style={{ color: '#22c55e' }}>No</span>
                } />
                {result.email_profile.breach_count > 0 && (
                  <>
                    <InfoRow label="Data Breaches" value={
                      <span style={{ color: '#ef4444', fontWeight: 700 }}>
                        💧 {result.email_profile.breach_count} breaches found
                      </span>
                    } />
                    <div className="tag-list" style={{ marginTop: 8 }}>
                      {result.email_profile.breach_names.slice(0, 10).map(b =>
                        <span key={b} className="tag" style={{ fontSize: 11 }}>{b}</span>
                      )}
                    </div>
                  </>
                )}
                {result.email_profile.breach_count === 0 && (
                  <InfoRow label="Data Breaches" value={
                    <span style={{ color: '#22c55e' }}><CheckCircle size={12} /> Clean — not in known breaches</span>
                  } />
                )}
              </div>
            )}

            {/* Likely Identities */}
            {(result.likely_names.length > 0 || result.likely_locations.length > 0) && (
              <div className="card">
                <div className="card__header">
                  <h3 className="card__title"><Hash size={14} className="icon--warning" /> Possible Real Identity</h3>
                </div>
                {result.likely_names.length > 0 && (
                  <>
                    <span className="info-row__label" style={{ display: 'block', marginBottom: 6 }}>Names / Aliases</span>
                    <div className="tag-list" style={{ marginBottom: 12 }}>
                      {result.likely_names.map(n => <span key={n} className="tag" style={{ fontWeight: 600 }}>{n}</span>)}
                    </div>
                  </>
                )}
                {result.likely_locations.length > 0 && (
                  <>
                    <span className="info-row__label" style={{ display: 'block', marginBottom: 6 }}>Locations</span>
                    <div className="tag-list">
                      {[...new Set(result.likely_locations)].map(loc =>
                        <span key={loc} className="tag"><Globe size={11} /> {loc}</span>
                      )}
                    </div>
                  </>
                )}
              </div>
            )}

          </div>

          {/* Social Media Footprint */}
          {result.social_hits.length > 0 && (
            <div className="card">
              <div className="card__header">
                <h3 className="card__title"><User size={14} className="icon--secondary" /> Social Media Footprint</h3>
                <span className="badge badge--neutral">{result.social_hits.length} platforms</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 10, marginTop: 12 }}>
                {result.social_hits.map(hit => (
                  <a
                    key={hit.platform + hit.url}
                    href={hit.url} target="_blank" rel="noopener noreferrer"
                    style={{
                      display: 'flex', flexDirection: 'column', gap: 4, padding: '12px',
                      background: 'rgba(255,255,255,0.04)', borderRadius: 8,
                      border: '1px solid rgba(255,255,255,0.08)', textDecoration: 'none',
                      transition: 'all 0.2s', cursor: 'pointer',
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(0,255,136,0.06)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.04)')}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontWeight: 600, fontSize: 13 }}>
                        {PLATFORM_ICONS[hit.platform] || '🌐'} {hit.platform}
                      </span>
                      <ExternalLink size={11} style={{ color: 'var(--text-muted)' }} />
                    </div>
                    {hit.name && <span style={{ fontSize: 12, color: 'var(--accent-primary)', fontWeight: 500 }}>{hit.name}</span>}
                    {hit.bio && <span style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.4 }}>{hit.bio.slice(0, 80)}</span>}
                    <code style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>@{hit.username}</code>
                  </a>
                ))}
              </div>
            </div>
          )}

          {result.social_hits.length === 0 && result.input_username && (
            <div className="card">
              <div className="card__header">
                <h3 className="card__title"><User size={14} className="icon--secondary" /> Social Media Footprint</h3>
              </div>
              <div className="empty-state">
                <Shield size={32} className="icon--muted" />
                <p>No social profiles found for <strong>@{result.input_username}</strong> — possible burner/anonymous identity.</p>
              </div>
            </div>
          )}

        </div>
      )}
    </div>
  );
}
