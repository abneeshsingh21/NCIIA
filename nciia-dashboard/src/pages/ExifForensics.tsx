import { useState, useCallback, useRef } from 'react';
import { Upload, MapPin, Camera, Clock, AlertTriangle, Image, Loader, ExternalLink } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

interface ExifResult {
  filename: string; file_size_kb: number;
  image_width: number; image_height: number;
  gps_lat: number | null; gps_lon: number | null; gps_altitude: number | null; gps_maps_url: string;
  camera_make: string; camera_model: string; camera_serial: string; lens_model: string;
  date_taken: string; date_modified: string; software: string;
  photoshop_detected: boolean; edited: boolean; original_format: string; whatsapp_compressed: boolean;
  raw_exif: Record<string, Record<string, string>>;
  errors: string[];
}

function InfoRow({ label, value, highlight }: { label: string; value?: React.ReactNode; highlight?: 'warn' | 'ok' }) {
  if (!value && value !== 0) return null;
  return (
    <div className="info-row">
      <span className="info-row__label">{label}</span>
      <span style={{ color: highlight === 'warn' ? '#f97316' : highlight === 'ok' ? '#22c55e' : undefined }}>{value}</span>
    </div>
  );
}

export default function ExifForensics() {
  const [result, setResult] = useState<ExifResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const analyze = useCallback(async (file: File) => {
    setLoading(true); setError(null); setResult(null);
    setPreview(URL.createObjectURL(file));
    const form = new FormData();
    form.append('file', file);
    try {
      const r = await fetch(`${API_BASE}/api/osint/exif`, { method: 'POST', body: form });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setResult(await r.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed');
    } finally { setLoading(false); }
  }, []);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) analyze(file);
  }, [analyze]);

  return (
    <div className="page-container">
      <header className="page-header">
        <div>
          <h2 className="page-header__title"><Image size={22} className="icon--warning" /> EXIF & Photo Forensics</h2>
          <p className="page-header__sub">Extract hidden GPS location, camera details, and editing history from any image</p>
        </div>
      </header>

      {/* Drop Zone */}
      {!result && (
        <div className="card"
          style={{ border: `2px dashed ${dragging ? 'var(--accent-primary)' : 'rgba(255,255,255,0.12)'}`, textAlign: 'center', padding: 48, cursor: 'pointer', transition: 'all 0.2s', background: dragging ? 'rgba(0,255,136,0.04)' : undefined }}
          onDrop={onDrop} onDragOver={e => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)}
          onClick={() => inputRef.current?.click()}>
          <input ref={inputRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={e => e.target.files?.[0] && analyze(e.target.files[0])} />
          {loading ? <><Loader size={40} className="spin icon--muted" style={{ marginBottom: 12 }} /><p>Analyzing EXIF metadata…</p></>
            : <><Upload size={40} className="icon--muted" style={{ marginBottom: 12 }} />
              <p style={{ fontWeight: 600, fontSize: 16 }}>Drop a photo here or click to browse</p>
              <p className="text-muted text-xs" style={{ marginTop: 8 }}>Supports JPEG, PNG, TIFF, HEIC · Max 50MB</p>
              <p className="text-muted text-xs">Photos from WhatsApp, screenshots, and social media will be analyzed for hidden GPS and device data</p></>}
        </div>
      )}

      {error && <div className="alert-banner alert-banner--error"><AlertTriangle size={14} /> {error}</div>}

      {result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <button className="btn btn--ghost btn--sm" onClick={() => { setResult(null); setPreview(null); }}>← Analyze another</button>
            <span className="text-muted text-xs">{result.filename} · {result.file_size_kb} KB · {result.image_width}×{result.image_height}px</span>
          </div>

          <div className="enrich-grid">
            {/* GPS Location - most important */}
            <div className="card" style={{ borderColor: result.gps_lat ? '#22c55e' : 'rgba(255,255,255,0.06)', borderWidth: result.gps_lat ? 2 : 1 }}>
              <div className="card__header">
                <h3 className="card__title"><MapPin size={14} className={result.gps_lat ? 'icon--success' : 'icon--muted'} /> GPS Location</h3>
                {result.gps_lat ? <span className="badge badge--success">Found ✓</span> : <span className="badge badge--neutral">Not Found</span>}
              </div>
              {result.gps_lat ? (
                <>
                  <div style={{ fontWeight: 700, fontSize: 18, color: '#22c55e', marginBottom: 8 }}>📍 Exact Location Extracted!</div>
                  <InfoRow label="Latitude"   value={result.gps_lat} />
                  <InfoRow label="Longitude"  value={result.gps_lon} />
                  {result.gps_altitude && <InfoRow label="Altitude" value={`${result.gps_altitude}m`} />}
                  <a href={result.gps_maps_url} target="_blank" rel="noopener noreferrer"
                    className="btn btn--primary" style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <MapPin size={14} /> Open Exact Location in Google Maps <ExternalLink size={12} />
                  </a>
                </>
              ) : (
                <p className="text-muted" style={{ fontSize: 13 }}>No GPS coordinates found. The photo may have been taken with location disabled or stripped by WhatsApp/social media.</p>
              )}
            </div>

            {/* Camera / Device */}
            <div className="card">
              <div className="card__header"><h3 className="card__title"><Camera size={14} className="icon--primary" /> Camera & Device</h3></div>
              <InfoRow label="Make"   value={result.camera_make}  />
              <InfoRow label="Model"  value={result.camera_model} />
              {result.camera_serial && <InfoRow label="Serial" value={<span style={{ color: '#f97316', fontWeight: 600 }}>{result.camera_serial}</span>} highlight="warn" />}
              <InfoRow label="Lens"   value={result.lens_model}   />
              <InfoRow label="Format" value={result.original_format} />
              {result.whatsapp_compressed && (
                <div className="tag" style={{ marginTop: 10, color: '#eab308' }}>
                  ⚠ WhatsApp-compressed — GPS data likely stripped
                </div>
              )}
            </div>

            {/* Timestamp */}
            <div className="card">
              <div className="card__header"><h3 className="card__title"><Clock size={14} className="icon--warning" /> Timestamps</h3></div>
              <InfoRow label="Date Taken"     value={result.date_taken}     highlight={result.date_taken ? 'ok' : undefined} />
              <InfoRow label="Date Modified"  value={result.date_modified}  />
              {result.date_taken && result.date_modified && result.date_taken !== result.date_modified && (
                <div className="tag" style={{ color: '#f97316', marginTop: 8 }}>⚠ Timestamps differ — photo was modified after being taken</div>
              )}
            </div>

            {/* Editing Detection */}
            <div className="card" style={{ borderColor: result.photoshop_detected ? '#ef4444' : result.edited ? '#f97316' : 'rgba(255,255,255,0.06)' }}>
              <div className="card__header">
                <h3 className="card__title"><AlertTriangle size={14} className={result.photoshop_detected ? 'icon--error' : 'icon--muted'} /> Editing Detection</h3>
                {result.photoshop_detected
                  ? <span className="badge badge--critical">EDITED ⚠</span>
                  : result.edited ? <span className="badge badge--warning">Modified</span>
                  : <span className="badge badge--success">Original</span>}
              </div>
              <InfoRow label="Software Used" value={result.software || 'None detected'} highlight={result.software ? 'warn' : undefined} />
              <InfoRow label="Photoshop"      value={result.photoshop_detected ? '⚠ YES — photo has been edited' : '✓ Not detected'} highlight={result.photoshop_detected ? 'warn' : 'ok'} />
              <InfoRow label="Modified"       value={result.edited ? 'Yes — timestamps or software indicate editing' : 'No'} />
              {result.photoshop_detected && (
                <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8 }}>
                  This photo was processed with editing software. Any ID, face, or document shown may have been altered.
                </p>
              )}
            </div>
          </div>

          {/* Preview */}
          {preview && (
            <div className="card">
              <div className="card__header"><h3 className="card__title">Image Preview</h3></div>
              <img src={preview} alt="analyzed" style={{ maxWidth: '100%', maxHeight: 400, objectFit: 'contain', borderRadius: 8 }} />
            </div>
          )}

          {result.errors.length > 0 && (
            <div className="card"><div className="card__header"><h3 className="card__title">Errors</h3></div>
              {result.errors.map((e, i) => <div key={i} className="tag" style={{ color: '#f97316', marginBottom: 4 }}>{e}</div>)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
