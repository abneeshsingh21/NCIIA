import { useState, useCallback } from 'react';
import { Search, AlertTriangle, Globe, ExternalLink, RefreshCw, CheckCircle } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

interface EnrichResult {
  ioc: string;
  ioc_type: string;
  risk_score: number;
  risk_level: string;
  tags: string[];
  vt_malicious: number;
  vt_suspicious: number;
  vt_harmless?: number;
  vt_undetected?: number;
  vt_engines_detected: string[];
  vt_categories: string[];
  abuse_confidence: number;
  abuse_country: string;
  abuse_isp: string;
  abuse_usage_type?: string;
  abuse_total_reports: number;
  shodan_ports: number[];
  shodan_vulns: string[];
  shodan_org: string;
  shodan_hostnames: string[];
  whois_registrar: string;
  whois_created: string;
  whois_expires: string;
  whois_name_servers: string[];
  cert_domains: string[];
  cert_issuer: string;
  geo_country: string;
  geo_city: string;
  geo_region?: string;
  geo_asn: string;
  geo_org: string;
  geo_lat: number;
  geo_lon: number;
  is_tor: boolean;
  is_vpn: boolean;
  is_datacenter: boolean;
  breach_count: number;
  breach_names: string[];
  errors: Record<string, string>;
  enriched_at: number;
  from_cache?: boolean;
}

const RISK_COLOR: Record<string, string> = {
  critical: '#ef4444', high: '#f97316', medium: '#eab308',
  low: '#22c55e', minimal: '#6b7280', unknown: '#6b7280',
};

function ScoreGauge({ score, level }: { score: number; level: string }) {
  const color = RISK_COLOR[level] ?? '#6b7280';
  const pct = Math.min(score, 100);
  return (
    <div className="score-gauge">
      <svg viewBox="0 0 100 60" className="score-gauge__svg">
        <path d="M10 55 A45 45 0 0 1 90 55" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="10" strokeLinecap="round" />
        <path d="M10 55 A45 45 0 0 1 90 55" fill="none" stroke={color} strokeWidth="10" strokeLinecap="round"
          strokeDasharray={`${(pct / 100) * 141.4} 141.4`} />
        <text x="50" y="50" textAnchor="middle" fontSize="18" fontWeight="700" fill={color}>{score}</text>
      </svg>
      <span className="score-gauge__label" style={{ color }}>{level.toUpperCase()}</span>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value?: React.ReactNode }) {
  if (value === undefined || value === null || value === '' || value === 0) return null;
  return (
    <div className="info-row">
      <span className="info-row__label">{label}</span>
      <span className="info-row__value">{value}</span>
    </div>
  );
}

export default function EnrichmentExplorer() {
  const [ioc, setIoc]         = useState('');
  const [result, setResult]   = useState<EnrichResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const enrich = useCallback(async (target?: string) => {
    const q = (target ?? ioc).trim();
    if (!q) return;
    setLoading(true); setError(null); setResult(null);
    try {
      const resp = await fetch(`${API_BASE}/api/enrichment/enrich`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ioc: q }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setResult(await resp.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Enrichment failed');
    } finally {
      setLoading(false);
    }
  }, [ioc]);

  const DEMO_IOCS = ['1.1.1.1', 'google.com', 'test@example.com', 'github.com'];

  return (
    <div className="page-container">
      <header className="page-header">
        <div>
          <h2 className="page-header__title">
            <Globe size={24} className="icon--primary" />
            IOC Enrichment Explorer
          </h2>
          <p className="page-header__sub">
            VirusTotal · AbuseIPDB · Shodan · WHOIS · crt.sh · ipinfo.io · HaveIBeenPwned
          </p>
        </div>
      </header>

      {/* Search */}
      <div className="card">
        <form onSubmit={e => { e.preventDefault(); void enrich(); }} className="enrich-form">
          <div className="filter-bar__search" style={{ flex: 1 }}>
            <Search size={16} className="filter-bar__search-icon" />
            <input
              className="input"
              style={{ paddingLeft: 32, fontSize: 15 }}
              placeholder="Enter IP, domain, URL, hash, or email…"
              value={ioc}
              onChange={e => setIoc(e.target.value)}
              autoFocus
            />
          </div>
          <button type="submit" className="btn btn--primary" disabled={loading || !ioc.trim()}>
            {loading ? <><RefreshCw size={14} className="spin" /> Enriching…</> : 'Enrich Now'}
          </button>
        </form>
        <div className="enrich-demo-iocs">
          {DEMO_IOCS.map(d => (
            <button key={d} className="chip" onClick={() => { setIoc(d); void enrich(d); }}>{d}</button>
          ))}
        </div>
      </div>

      {error && <div className="alert-banner alert-banner--error"><AlertTriangle size={14} />{error}</div>}

      {/* Result */}
      {result && (
        <div className="enrich-result">
          <div className="card">
            <div className="enrich-result__ioc-row">
              <div>
                <code className="enrich-result__ioc">{result.ioc}</code>
                <div className="tag-list" style={{ marginTop: 8 }}>
                  <span className="badge badge--neutral">{result.ioc_type}</span>
                  {result.tags.map(t => <span key={t} className="tag">{t}</span>)}
                  {result.from_cache && <span className="badge badge--neutral">cached</span>}
                </div>
              </div>
              <ScoreGauge score={result.risk_score} level={result.risk_level} />
            </div>
          </div>

          <div className="enrich-grid">
            {/* VirusTotal */}
            <div className="card">
              <div className="card__header">
                <h3 className="card__title">🦠 VirusTotal</h3>
                <a href={`https://www.virustotal.com/gui/search/${result.ioc}`} target="_blank" rel="noopener noreferrer" className="btn btn--ghost btn--xs"><ExternalLink size={12} /></a>
              </div>
              <InfoRow label="Malicious"  value={<span style={{ color: '#ef4444', fontWeight: 700 }}>{result.vt_malicious}</span>} />
              <InfoRow label="Suspicious" value={result.vt_suspicious} />
              <InfoRow label="Harmless"   value={result.vt_harmless} />
              {result.vt_engines_detected.length > 0 && (
                <div className="info-row info-row--col">
                  <span className="info-row__label">Detected by</span>
                  <div className="tag-list" style={{ marginTop: 4 }}>
                    {result.vt_engines_detected.slice(0, 8).map(e => (
                      <span key={e} className="tag" style={{ color: '#ef4444' }}>{e}</span>
                    ))}
                  </div>
                </div>
              )}
              <InfoRow label="Categories" value={result.vt_categories.join(', ') || undefined} />
              {result.errors?.virustotal && <p className="text-muted text-xs" style={{ marginTop: 8 }}>⚠ {result.errors.virustotal}</p>}
            </div>

            {/* AbuseIPDB */}
            <div className="card">
              <div className="card__header">
                <h3 className="card__title">🔴 AbuseIPDB</h3>
                <a href={`https://www.abuseipdb.com/check/${result.ioc}`} target="_blank" rel="noopener noreferrer" className="btn btn--ghost btn--xs"><ExternalLink size={12} /></a>
              </div>
              <InfoRow label="Confidence" value={<span style={{ color: result.abuse_confidence > 50 ? '#ef4444' : '#22c55e' }}>{result.abuse_confidence}%</span>} />
              <InfoRow label="Reports"    value={result.abuse_total_reports} />
              <InfoRow label="Country"    value={result.abuse_country} />
              <InfoRow label="ISP"        value={result.abuse_isp} />
              <InfoRow label="Usage"      value={result.abuse_usage_type} />
              {result.errors?.abuseipdb && <p className="text-muted text-xs" style={{ marginTop: 8 }}>⚠ {result.errors.abuseipdb}</p>}
            </div>

            {/* Shodan */}
            <div className="card">
              <div className="card__header"><h3 className="card__title">📡 Shodan</h3></div>
              <InfoRow label="Org"        value={result.shodan_org} />
              <InfoRow label="Open Ports" value={result.shodan_ports.slice(0, 10).join(', ') || undefined} />
              {result.shodan_vulns.length > 0 && (
                <div className="info-row info-row--col">
                  <span className="info-row__label">CVEs ({result.shodan_vulns.length})</span>
                  <div className="tag-list" style={{ marginTop: 4 }}>
                    {result.shodan_vulns.slice(0, 6).map(v => (
                      <a key={v} href={`https://nvd.nist.gov/vuln/detail/${v}`} target="_blank" rel="noopener noreferrer" className="tag tag--link" style={{ color: '#ef4444' }}>{v}</a>
                    ))}
                  </div>
                </div>
              )}
              <InfoRow label="Hostnames" value={result.shodan_hostnames.slice(0, 3).join(', ') || undefined} />
            </div>

            {/* Geolocation */}
            <div className="card">
              <div className="card__header"><h3 className="card__title">🌍 Geolocation & Network</h3></div>
              <InfoRow label="Location" value={[result.geo_city, result.geo_region, result.geo_country].filter(Boolean).join(', ') || undefined} />
              <InfoRow label="Coords"   value={result.geo_lat ? `${result.geo_lat}, ${result.geo_lon}` : undefined} />
              <InfoRow label="ASN"      value={result.geo_asn} />
              <InfoRow label="Org"      value={result.geo_org} />
              <div className="info-row">
                <span className="info-row__label">Privacy</span>
                <div className="tag-list">
                  {result.is_tor && <span className="tag" style={{ color: '#ef4444' }}>TOR EXIT</span>}
                  {result.is_vpn && <span className="tag" style={{ color: '#f97316' }}>VPN</span>}
                  {result.is_datacenter && <span className="tag">DATACENTER</span>}
                  {!result.is_tor && !result.is_vpn && !result.is_datacenter && <span className="tag">Residential</span>}
                </div>
              </div>
            </div>

            {/* WHOIS */}
            <div className="card">
              <div className="card__header"><h3 className="card__title">📋 WHOIS / RDAP</h3></div>
              <InfoRow label="Registrar"   value={result.whois_registrar} />
              <InfoRow label="Created"     value={result.whois_created} />
              <InfoRow label="Expires"     value={result.whois_expires} />
              <InfoRow label="Nameservers" value={result.whois_name_servers.join(', ') || undefined} />
            </div>

            {/* Certificates */}
            <div className="card">
              <div className="card__header">
                <h3 className="card__title">🔒 Certificate Transparency</h3>
                <a href={`https://crt.sh/?q=${result.ioc}`} target="_blank" rel="noopener noreferrer" className="btn btn--ghost btn--xs"><ExternalLink size={12} /></a>
              </div>
              <InfoRow label="Issuer"  value={result.cert_issuer} />
              <InfoRow label="Domains" value={result.cert_domains.length ? `${result.cert_domains.length} found` : undefined} />
              {result.cert_domains.length > 0 && (
                <div className="tag-list" style={{ marginTop: 8 }}>
                  {result.cert_domains.slice(0, 10).map(d => <span key={d} className="tag text-xs">{d}</span>)}
                </div>
              )}
            </div>

            {/* HIBP */}
            {result.ioc_type === 'email' && (
              <div className="card">
                <div className="card__header"><h3 className="card__title">💧 HaveIBeenPwned</h3></div>
                {result.breach_count > 0 ? (
                  <>
                    <InfoRow label="Breaches" value={<span style={{ color: '#ef4444', fontWeight: 700 }}>{result.breach_count}</span>} />
                    <div className="tag-list" style={{ marginTop: 8 }}>
                      {result.breach_names.slice(0, 10).map(b => <span key={b} className="tag">{b}</span>)}
                    </div>
                  </>
                ) : (
                  <div className="info-row" style={{ gap: 8 }}>
                    <CheckCircle size={14} className="icon--success" />
                    <span className="text-muted">Not found in any known breaches</span>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="text-muted text-xs" style={{ textAlign: 'right' }}>
            Enriched at {new Date(result.enriched_at * 1000).toLocaleString()}
          </div>
        </div>
      )}
    </div>
  );
}
