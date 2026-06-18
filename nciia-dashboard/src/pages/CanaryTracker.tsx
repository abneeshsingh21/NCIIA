import { useState, useCallback, useEffect } from 'react';
import { Link2, Copy, Trash2, Eye, MapPin, Monitor, Wifi, Loader, Plus, RefreshCw, AlertTriangle, CheckCircle, Smartphone, Navigation, Building2, Signal } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

interface TrackingLink { tracking_id: string; label: string; trap_url: string; redirect_url: string; created_at: number; hit_count: number; }
interface GeoData {
  city?: string; regionName?: string; country?: string; countryCode?: string;
  isp?: string; org?: string; as?: string;
  lat?: number; lon?: number;
  timezone?: string;
  zip?: string; postal?: string;
  mobile?: boolean; proxy?: boolean; hosting?: boolean;
  carrier?: string; hostname?: string; anycast?: boolean;
  status?: string;
}
interface GPS { lat: number; lon: number; accuracy?: number; altitude?: number; }
interface Fingerprint { screen?: { w: number; h: number; dpr: number }; tz?: string; lang?: string; gps?: GPS; }
interface Hit { ip: string; timestamp: string; ua: string; referer: string; geo: GeoData; fingerprint: Fingerprint | null; real_ip?: string; real_geo?: GeoData; }
interface HitDetails { tracking_id: string; label: string; trap_url: string; hit_count: number; hits: Hit[]; }

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return <button className="btn btn--ghost btn--sm" onClick={copy} title="Copy">{copied ? <CheckCircle size={13} style={{ color: '#22c55e' }} /> : <Copy size={13} />}</button>;
}

export default function CanaryTracker() {
  const [links, setLinks] = useState<TrackingLink[]>([]);
  const [label, setLabel] = useState('Invoice PDF');
  const [redirect, setRedirect] = useState('https://www.google.com');
  const [publicBase, setPublicBase] = useState('http://localhost:8000');
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState<HitDetails | null>(null);
  const [loadingHits, setLoadingHits] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  // ── Fetch all links ───────────────────────────────────────────────────────
  const fetchLinks = useCallback(async () => {
    try {
      const r = await fetch(`${API_BASE}/api/tracker/links`);
      if (r.ok) {
        const d = await r.json();
        setLinks(d.links || []);
      }
    } catch (_) {}
  }, []);

  // ── Fetch hits for the currently selected link ────────────────────────────
  const fetchSelectedHits = useCallback(async (id: string) => {
    try {
      const r = await fetch(`${API_BASE}/api/tracker/hits/${id}`);
      if (r.ok) setSelected(await r.json());
    } catch (_) {}
  }, []);

  // ── Full refresh: links + selected hits panel ─────────────────────────────
  const refreshAll = useCallback(async () => {
    setRefreshing(true);
    try {
      const r = await fetch(`${API_BASE}/api/tracker/links`);
      if (r.ok) {
        const d = await r.json();
        const updatedLinks: TrackingLink[] = d.links || [];
        setLinks(updatedLinks);

        // Also refresh the detail panel if one is open
        if (selected) {
          const stillExists = updatedLinks.find(l => l.tracking_id === selected.tracking_id);
          if (stillExists) {
            await fetchSelectedHits(selected.tracking_id);
          }
        }
      }
    } catch (_) {}
    setRefreshing(false);
  }, [selected, fetchSelectedHits]);

  // Auto-load links on mount
  useEffect(() => { fetchLinks(); }, [fetchLinks]);

  // Auto-refresh every 10 seconds
  useEffect(() => {
    const interval = setInterval(refreshAll, 10000);
    return () => clearInterval(interval);
  }, [refreshAll]);

  const createLink = useCallback(async () => {
    setCreating(true);
    try {
      const r = await fetch(`${API_BASE}/api/tracker/generate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label, redirect_url: redirect, public_base: publicBase }),
      });
      if (r.ok) { await fetchLinks(); }
    } finally { setCreating(false); }
  }, [label, redirect, publicBase, fetchLinks]);

  const viewHits = useCallback(async (id: string) => {
    setLoadingHits(true);
    try {
      const r = await fetch(`${API_BASE}/api/tracker/hits/${id}`);
      if (r.ok) setSelected(await r.json());
    } finally { setLoadingHits(false); }
  }, []);

  const deleteLink = useCallback(async (id: string) => {
    await fetch(`${API_BASE}/api/tracker/links/${id}`, { method: 'DELETE' });
    if (selected?.tracking_id === id) setSelected(null);
    fetchLinks();
  }, [selected, fetchLinks]);

  const parseUA = (ua: string) => {
    const mobile = /android|iphone|ipad/i.test(ua);
    const os = ua.match(/\(([^)]+)\)/)?.[1]?.split(';')[0] || 'Unknown';
    const browser = ua.match(/(Chrome|Firefox|Safari|Edge|OPR)\/[\d.]+/)?.[0] || 'Unknown';
    return { mobile, os, browser };
  };

  return (
    <div className="page-container">
      <header className="page-header">
        <div>
          <h2 className="page-header__title"><Link2 size={22} className="icon--primary" /> Canary Tracker</h2>
          <p className="page-header__sub">Generate stealth tracking links · Capture real IP, device fingerprint &amp; location even through VPNs</p>
        </div>
        <button className="btn btn--ghost btn--sm" onClick={refreshAll} disabled={refreshing}>
          <RefreshCw size={14} className={refreshing ? 'spin' : ''} /> {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </header>

      {/* Config */}
      <div className="card">
        <h3 className="card__title" style={{ marginBottom: 14 }}>Generate Tracking Link</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
          <div><label className="label">Link Label (internal name)</label>
            <input className="input" value={label} onChange={e => setLabel(e.target.value)} placeholder="e.g. Payment Invoice" /></div>
          <div><label className="label">Redirect URL (where scammer lands)</label>
            <input className="input" value={redirect} onChange={e => setRedirect(e.target.value)} placeholder="https://www.google.com" /></div>
        </div>
        <div style={{ marginBottom: 12 }}>
          <label className="label">Your Public Base URL (Ngrok / Cloudflare tunnel / server IP)</label>
          <input className="input" value={publicBase} onChange={e => setPublicBase(e.target.value)} placeholder="https://xxxx.trycloudflare.com" />
          <p className="text-muted text-xs" style={{ marginTop: 4 }}>
            💡 Run <code style={{ background: 'rgba(255,255,255,0.08)', padding: '1px 6px', borderRadius: 4 }}>cloudflared.exe tunnel --url http://localhost:8000</code> and paste the HTTPS URL above
          </p>
        </div>
        <button className="btn btn--primary" onClick={createLink} disabled={creating} style={{ width: '100%' }}>
          {creating ? <><Loader size={14} className="spin" /> Creating…</> : <><Plus size={14} /> Generate Tracking Link</>}
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: selected ? '1fr 1.5fr' : '1fr', gap: 16 }}>
        {/* Links list */}
        <div className="card">
          <div className="card__header"><h3 className="card__title">Active Links ({links.length})</h3></div>
          {links.length === 0 && (
            <div className="empty-state"><Link2 size={28} className="icon--muted" /><p>No links yet. Generate one above to start tracking.</p></div>
          )}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 8 }}>
            {links.map(link => (
              <div key={link.tracking_id} className="signal-card" style={{ cursor: 'pointer', borderColor: selected?.tracking_id === link.tracking_id ? 'var(--accent-primary)' : undefined }}
                onClick={() => viewHits(link.tracking_id)}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, marginBottom: 4 }}>{link.label}</div>
                    <a href={link.trap_url} target="_blank" rel="noopener noreferrer"
                      style={{ fontSize: 11, color: 'var(--accent-primary)', wordBreak: 'break-all', textDecoration: 'underline' }}
                      onClick={e => e.stopPropagation()}>
                      {link.trap_url}
                    </a>
                  </div>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginLeft: 8 }}>
                    <span className={`badge ${link.hit_count > 0 ? 'badge--critical' : 'badge--low'}`} style={{ fontSize: 12 }}>
                      {link.hit_count} {link.hit_count === 1 ? 'HIT' : 'HITS'}
                    </span>
                    <CopyBtn text={link.trap_url} />
                    <button className="btn btn--ghost btn--sm" onClick={e => { e.stopPropagation(); deleteLink(link.tracking_id); }}><Trash2 size={13} style={{ color: '#ef4444' }} /></button>
                  </div>
                </div>
                <div style={{ marginTop: 6, fontSize: 11, color: 'var(--text-muted)' }}>
                  → {link.redirect_url} · Created {new Date(link.created_at * 1000).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Hit details */}
        {selected && (
          <div className="card" style={{ maxHeight: '70vh', overflowY: 'auto' }}>
            <div className="card__header">
              <h3 className="card__title"><Eye size={14} className="icon--primary" /> {selected.label} — {selected.hit_count} hits</h3>
              <button className="btn btn--ghost btn--sm" onClick={() => setSelected(null)}>✕</button>
            </div>
            {loadingHits && <div className="empty-state"><Loader size={24} className="spin icon--muted" /></div>}
            {selected.hits.length === 0 && !loadingHits && (
              <div className="empty-state"><AlertTriangle size={24} className="icon--muted" /><p>No hits yet. Send the link to the scammer.</p></div>
            )}
            {selected.hits.map((hit, i) => {
              const ua = parseUA(hit.ua);
              const geo = hit.real_geo || hit.geo;
              const ip = hit.real_ip || hit.ip;
              const fp = hit.fingerprint;
              return (
                <div key={i} style={{ marginBottom: 16, padding: 14, background: 'rgba(0,255,136,0.04)', borderRadius: 8, border: '1px solid rgba(0,255,136,0.12)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                    <span style={{ fontWeight: 700, fontSize: 15 }}>Hit #{i + 1}</span>
                    <span className="text-muted text-xs">{new Date(hit.timestamp).toLocaleString()}</span>
                  </div>

                  {/* GPS Exact Location — highest priority */}
                  {fp?.gps && (
                    <div style={{ marginBottom: 10, padding: '10px 12px', background: 'rgba(34,197,94,0.1)', borderRadius: 6, border: '1px solid rgba(34,197,94,0.3)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700, color: '#22c55e', marginBottom: 4 }}>
                        <Navigation size={13} /> 📍 EXACT GPS LOCATION CAPTURED
                      </div>
                      <div style={{ fontSize: 12, marginBottom: 6, color: '#86efac' }}>
                        {fp.gps.lat.toFixed(6)}, {fp.gps.lon.toFixed(6)}
                        {fp.gps.accuracy && <span style={{ marginLeft: 8, color: '#6ee7b7' }}>±{Math.round(fp.gps.accuracy)}m accuracy</span>}
                      </div>
                      <a
                        href={`https://www.google.com/maps?q=${fp.gps.lat},${fp.gps.lon}`}
                        target="_blank" rel="noopener noreferrer"
                        style={{ display: 'inline-block', fontSize: 12, padding: '4px 10px', background: '#22c55e', color: '#000', borderRadius: 4, textDecoration: 'none', fontWeight: 600 }}
                      >
                        🗺 Open in Google Maps
                      </a>
                    </div>
                  )}

                  {/* Location & IP */}
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                    <span className="tag"><MapPin size={11} /> {geo?.city || '?'}, {geo?.regionName || '?'}, {geo?.country || '?'} {geo?.countryCode ? `(${geo.countryCode})` : ''}</span>
                    <span className="tag"><Wifi size={11} /> {ip}</span>
                    {hit.real_ip && hit.real_ip !== hit.ip && <span className="tag" style={{ color: '#ef4444' }}>⚠ VPN Detected! Real IP: {hit.real_ip}</span>}
                    {geo?.proxy && <span className="tag" style={{ color: '#f97316' }}>🔒 Proxy/VPN</span>}
                    {geo?.mobile && <span className="tag" style={{ color: '#a78bfa' }}>📱 Mobile Network</span>}
                    {geo?.hosting && <span className="tag" style={{ color: '#64748b' }}>🖥 Datacenter/VPS</span>}
                  </div>

                  {/* IP Intelligence */}
                  <div className="info-row"><span className="info-row__label"><Building2 size={11} style={{ display: 'inline', marginRight: 4 }} />ISP</span><span style={{ fontWeight: 500 }}>{geo?.isp || '—'}</span></div>
                  {geo?.org && geo.org !== geo?.isp && (
                    <div className="info-row"><span className="info-row__label">Organization</span><span style={{ fontWeight: 500, color: '#fbbf24' }}>{geo.org}</span></div>
                  )}
                  {geo?.carrier && (
                    <div className="info-row"><span className="info-row__label"><Signal size={11} style={{ display: 'inline', marginRight: 4 }} />Carrier</span><span style={{ color: '#a78bfa' }}>{geo.carrier}</span></div>
                  )}
                  {geo?.as && <div className="info-row"><span className="info-row__label">ASN</span><span style={{ fontSize: 11, color: '#94a3b8' }}>{geo.as}</span></div>}
                  {(geo?.zip || geo?.postal) && <div className="info-row"><span className="info-row__label">Postal Code</span><span>{geo.zip || geo.postal}</span></div>}
                  {geo?.hostname && <div className="info-row"><span className="info-row__label">Hostname</span><span style={{ fontSize: 11 }}>{geo.hostname}</span></div>}
                  <div className="info-row"><span className="info-row__label">Timezone</span><span>{typeof geo?.timezone === 'object' ? (geo?.timezone as any)?.id : geo?.timezone || '—'}</span></div>

                  {/* IP-based map link (always available) */}
                  {geo?.lat && geo.lat !== 0 && !fp?.gps && (
                    <div className="info-row"><span className="info-row__label">Approx. Location</span>
                      <a href={`https://www.google.com/maps?q=${geo.lat},${geo.lon}`} target="_blank" rel="noopener noreferrer" className="link">
                        {geo.lat.toFixed(4)}, {geo.lon.toFixed(4)} → Open in Maps (IP-based)
                      </a>
                    </div>
                  )}

                  {/* Device / Browser */}
                  <div className="info-row"><span className="info-row__label">Device</span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      {ua.mobile ? <Smartphone size={12} /> : <Monitor size={12} />} {ua.os}
                    </span>
                  </div>
                  <div className="info-row"><span className="info-row__label">Browser</span><span>{ua.browser}</span></div>
                  {hit.referer && <div className="info-row"><span className="info-row__label">Referrer</span><span style={{ fontSize: 11, wordBreak: 'break-all' }}>{hit.referer}</span></div>}

                  {/* JS Fingerprint extras */}
                  {fp && (
                    <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                      {fp.screen && <div className="info-row"><span className="info-row__label">Screen</span><span>{fp.screen.w}×{fp.screen.h} @{fp.screen.dpr}x</span></div>}
                      {fp.tz && <div className="info-row"><span className="info-row__label">Device Timezone</span><span>{fp.tz}</span></div>}
                      {fp.lang && <div className="info-row"><span className="info-row__label">Language</span><span>{fp.lang}</span></div>}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
