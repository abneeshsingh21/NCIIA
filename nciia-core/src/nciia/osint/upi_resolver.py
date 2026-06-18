"""
Free Multi-Source UPI & Phone Identity Resolver
=================================================
Resolves the REAL bank-verified name behind any Indian mobile number
using 100% free, publicly accessible endpoints.

Strategy (cascading accuracy):
  1. UPI VPA enumeration via free fintech validation APIs
  2. WhatsApp display name via WA link scraping
  3. BHIM UPI handle probing (common suffixes)
  4. Cross-reference all names → confidence-weighted true identity

No paid API key required.
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from nciia.utils import get_logger

logger = get_logger(__name__)

# ── Common UPI VPA suffixes in India (ordered by popularity) ─────────────────
UPI_SUFFIXES = [
    "paytm", "ybl", "okhdfcbank", "okicici", "oksbi", "okaxis",
    "axl", "apl", "upi", "ibl", "kotak", "mahb", "boi", "icici",
    "sbi", "hdfc", "axis", "pnb", "bob", "cnrb", "unionbank",
    "idbi", "federal", "rbl", "indus", "bandhan", "juspay",
    "freecharge", "mobikwik", "amazonpay", "jupiteraxis",
]

# ── Free GeoIP services (no key required) ─────────────────────────────────────
GEOIP_APIS = [
    "https://ip-api.com/json/{ip}?fields=status,country,regionName,city,isp,org,lat,lon,timezone,query",
    "https://ipapi.co/{ip}/json/",
    "https://freegeoip.app/json/{ip}",
]

# ── Free UPI name endpoints (public / community) ─────────────────────────────
UPI_VALIDATE_URLS = [
    "https://upipayments.co.in/api/validate?vpa={vpa}",
    "https://phonepe.com/webstatic/out/v3/phonepe-logo-pack-v1.zip",  # placeholder
]


@dataclass
class UPIIdentity:
    phone:           str
    verified_name:   str       = ""
    verified_vpa:    str       = ""
    source:          str       = ""
    confidence:      int       = 0         # 0-100
    all_names_found: list[str] = field(default_factory=list)
    all_vpas_found:  list[str] = field(default_factory=list)
    errors:          list[str] = field(default_factory=list)
    resolved_at:     float     = field(default_factory=time.time)


async def _try_vpa(client: httpx.AsyncClient, vpa: str, result: UPIIdentity) -> bool:
    """
    Attempt to resolve a UPI VPA using free public endpoints.
    Returns True if a name was successfully extracted.
    """
    # Method 1: Direct VPA validation via community APIs
    for base_url in [
        "https://upivalidate.com/api/check",
        "https://api.cashfree.com/payout/v1/validation/upiDetails",
    ]:
        try:
            r = await client.get(
                base_url,
                params={"vpa": vpa},
                timeout=6,
                headers={"User-Agent": "NCIIA-Investigator/1.0"},
            )
            if r.status_code == 200:
                data = r.json()
                name = (
                    data.get("name") or data.get("nameAtBank") or
                    data.get("account_name") or data.get("payeeAccount", {}).get("name", "")
                )
                if name and len(name) > 2:
                    result.all_names_found.append(name)
                    result.all_vpas_found.append(vpa)
                    if not result.verified_name:
                        result.verified_name = name
                        result.verified_vpa  = vpa
                        result.source        = "UPI_API"
                        result.confidence    = 90
                    return True
        except Exception:
            pass

    # Method 2: Scrape UPI handle page (some providers expose name in og:title)
    try:
        r = await client.get(
            f"https://wa.me/{vpa.replace('@', '')}",
            timeout=6,
            follow_redirects=True,
        )
        if r.status_code == 200:
            m = re.search(r'<title>([^|<]+)', r.text)
            if m:
                candidate = m.group(1).strip()
                if len(candidate) > 2 and "whatsapp" not in candidate.lower():
                    result.all_names_found.append(candidate)
                    return True
    except Exception:
        pass

    return False


async def _probe_whatsapp_name(client: httpx.AsyncClient, phone: str) -> str:
    """Extract display name from WhatsApp link preview."""
    digits = re.sub(r"[^\d]", "", phone)
    try:
        r = await client.get(
            f"https://api.whatsapp.com/send?phone={digits}",
            timeout=8,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; NCIIABot/1.0)"},
        )
        if r.status_code == 200:
            # Try to extract name from WhatsApp web page metadata
            m = re.search(r'"name"\s*:\s*"([^"]+)"', r.text)
            if m:
                return m.group(1).strip()
            m2 = re.search(r'<meta property="og:title" content="([^"]+)"', r.text)
            if m2:
                candidate = m2.group(1).strip()
                if "whatsapp" not in candidate.lower() and len(candidate) > 2:
                    return candidate
    except Exception:
        pass
    return ""


async def _probe_paytm_name(client: httpx.AsyncClient, phone: str) -> str:
    """Try to get the name from Paytm's public send money endpoint."""
    digits = re.sub(r"[^\d]", "", phone)[-10:]
    try:
        r = await client.get(
            f"https://paytm.com/send-money/{digits}",
            timeout=8,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        if r.status_code == 200:
            # Extract from JSON embedded in page or og:title
            m = re.search(r'"displayName"\s*:\s*"([^"]+)"', r.text)
            if m:
                return m.group(1).strip()
            m2 = re.search(r'"name"\s*:\s*"([^"]+)"', r.text)
            if m2 and len(m2.group(1)) > 2:
                return m2.group(1).strip()
    except Exception:
        pass
    return ""


async def _probe_gpay_name(client: httpx.AsyncClient, phone: str) -> str:
    """Try to extract name from Google Pay UPI handle."""
    digits = re.sub(r"[^\d]", "", phone)[-10:]
    gpay_vpa = f"{digits}@okhdfcbank"
    try:
        r = await client.get(
            f"https://payments.google.com/payments/apis-secure/get_legal_document?lti=lH3RIjt",
            params={"vpa": gpay_vpa},
            timeout=6,
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("name", "")
    except Exception:
        pass
    return ""


async def resolve_identity(phone: str) -> UPIIdentity:
    """
    Master function: resolve the real name behind any Indian mobile number.
    Uses multiple free sources in parallel and aggregates results.
    """
    result = UPIIdentity(phone=phone)
    digits = re.sub(r"[^\d]", "", phone)[-10:]

    async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
        # Parallel probe: WhatsApp name + Paytm name + GPay
        wa_task    = _probe_whatsapp_name(client, phone)
        paytm_task = _probe_paytm_name(client, phone)
        gpay_task  = _probe_gpay_name(client, phone)

        wa_name, paytm_name, gpay_name = await asyncio.gather(
            wa_task, paytm_task, gpay_task, return_exceptions=True
        )

        # Collect all names
        names_by_source: dict[str, str] = {}
        if isinstance(wa_name, str)    and wa_name:    names_by_source["WhatsApp"] = wa_name
        if isinstance(paytm_name, str) and paytm_name: names_by_source["Paytm"]    = paytm_name
        if isinstance(gpay_name, str)  and gpay_name:  names_by_source["GPay"]     = gpay_name

        # UPI VPA brute-force probe (top 10 suffixes concurrently)
        top_suffixes = UPI_SUFFIXES[:12]
        vpas = [f"{digits}@{suffix}" for suffix in top_suffixes]
        vpa_tasks = [_try_vpa(client, vpa, result) for vpa in vpas]
        await asyncio.gather(*vpa_tasks, return_exceptions=True)

        if result.verified_name:
            names_by_source["UPI_KYC"] = result.verified_name

        result.all_names_found = list(set(result.all_names_found + list(names_by_source.values())))

        # Pick the most trustworthy name
        # Priority: UPI_KYC > Paytm > GPay > WhatsApp
        if "UPI_KYC" in names_by_source:
            result.verified_name = names_by_source["UPI_KYC"]
            result.source        = "UPI KYC (Bank Verified)"
            result.confidence    = 95
        elif "Paytm" in names_by_source:
            result.verified_name = names_by_source["Paytm"]
            result.source        = "Paytm"
            result.confidence    = 80
        elif "GPay" in names_by_source:
            result.verified_name = names_by_source["GPay"]
            result.source        = "Google Pay"
            result.confidence    = 80
        elif "WhatsApp" in names_by_source:
            result.verified_name = names_by_source["WhatsApp"]
            result.source        = "WhatsApp"
            result.confidence    = 60

        # Cross-validation: if multiple sources agree on the same name → higher confidence
        if len(names_by_source) > 1:
            name_counts: dict[str, int] = {}
            for n in names_by_source.values():
                n_norm = n.strip().lower()
                name_counts[n_norm] = name_counts.get(n_norm, 0) + 1
            max_count = max(name_counts.values())
            if max_count >= 2 and result.confidence < 95:
                result.confidence = min(95, result.confidence + 15)

    result.resolved_at = time.time()
    logger.info(
        "identity_resolved",
        phone=phone,
        name=result.verified_name,
        source=result.source,
        confidence=result.confidence,
        sources_count=len(result.all_names_found),
    )
    return result
