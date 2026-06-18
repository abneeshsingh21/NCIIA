"""
IOC Enrichment Engine — N-CIIA

Automatically enriches every ingested signal/IOC with data from:
  - VirusTotal v3 (malicious votes, AV hits)
  - AbuseIPDB (abuse confidence, ISP)
  - Shodan (open ports, vulns)
  - WHOIS/RDAP (registrar, creation date)
  - crt.sh (certificate transparency)
  - ipinfo.io (ASN, geolocation)
  - HaveIBeenPwned (email breach history)
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from urllib.parse import urlparse

import aiohttp

from nciia.utils import get_logger, get_settings

logger = get_logger(__name__)


# ─── IOC type detection ───────────────────────────────────────────────────────

def detect_ioc_type(value: str) -> str:
    """Detect the type of an IOC string."""
    value = value.strip()

    # IP address
    try:
        ipaddress.ip_address(value)
        return "ip"
    except ValueError:
        pass

    # Email
    if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
        return "email"

    # MD5 / SHA1 / SHA256 hash
    if re.match(r"^[0-9a-fA-F]{32}$", value):
        return "md5"
    if re.match(r"^[0-9a-fA-F]{40}$", value):
        return "sha1"
    if re.match(r"^[0-9a-fA-F]{64}$", value):
        return "sha256"

    # URL
    if value.startswith(("http://", "https://", "ftp://")):
        return "url"

    # Domain
    if re.match(r"^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$", value):
        return "domain"

    return "unknown"


# ─── Enrichment result dataclass ─────────────────────────────────────────────

@dataclass
class EnrichmentResult:
    ioc: str
    ioc_type: str
    enriched_at: float = field(default_factory=time.time)

    # VirusTotal
    vt_malicious: int = 0
    vt_suspicious: int = 0
    vt_harmless: int = 0
    vt_undetected: int = 0
    vt_categories: list[str] = field(default_factory=list)
    vt_engines_detected: list[str] = field(default_factory=list)

    # AbuseIPDB
    abuse_confidence: int = 0
    abuse_country: str = ""
    abuse_isp: str = ""
    abuse_usage_type: str = ""
    abuse_total_reports: int = 0

    # Shodan
    shodan_ports: list[int] = field(default_factory=list)
    shodan_vulns: list[str] = field(default_factory=list)
    shodan_org: str = ""
    shodan_hostnames: list[str] = field(default_factory=list)
    shodan_tags: list[str] = field(default_factory=list)

    # WHOIS
    whois_registrar: str = ""
    whois_created: str = ""
    whois_expires: str = ""
    whois_registrant_org: str = ""
    whois_name_servers: list[str] = field(default_factory=list)

    # crt.sh
    cert_domains: list[str] = field(default_factory=list)
    cert_issuer: str = ""

    # ipinfo
    geo_lat: float = 0.0
    geo_lon: float = 0.0
    geo_city: str = ""
    geo_region: str = ""
    geo_country: str = ""
    geo_asn: str = ""
    geo_org: str = ""
    geo_timezone: str = ""
    is_tor: bool = False
    is_vpn: bool = False
    is_datacenter: bool = False

    # HIBP
    breach_count: int = 0
    breach_names: list[str] = field(default_factory=list)

    # Computed
    risk_score: float = 0.0
    risk_level: str = "unknown"
    tags: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)

    def compute_risk(self) -> None:
        """Compute a composite risk score 0–100 from all enrichment data."""
        score = 0.0

        # VirusTotal (max 50 pts)
        total_vt = self.vt_malicious + self.vt_suspicious + self.vt_harmless + self.vt_undetected
        if total_vt > 0:
            vt_ratio = (self.vt_malicious * 2 + self.vt_suspicious) / max(total_vt, 1)
            score += min(vt_ratio * 50, 50)

        # AbuseIPDB (max 25 pts)
        score += self.abuse_confidence * 0.25

        # Known vulns (max 15 pts)
        score += min(len(self.shodan_vulns) * 5, 15)

        # Tor/VPN/DC (max 10 pts)
        if self.is_tor:       score += 10
        elif self.is_vpn:     score += 5
        elif self.is_datacenter: score += 3

        self.risk_score = min(round(score, 1), 100.0)

        if self.risk_score >= 75:    self.risk_level = "critical"
        elif self.risk_score >= 50:  self.risk_level = "high"
        elif self.risk_score >= 25:  self.risk_level = "medium"
        elif self.risk_score >= 5:   self.risk_level = "low"
        else:                        self.risk_level = "minimal"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─── Individual enrichers ─────────────────────────────────────────────────────

class EnrichmentEngine:
    """Parallel async enrichment from multiple sources."""

    TIMEOUT = aiohttp.ClientTimeout(total=15)

    def __init__(self) -> None:
        self._settings = get_settings()

    async def enrich(self, ioc: str) -> EnrichmentResult:
        ioc = ioc.strip()
        ioc_type = detect_ioc_type(ioc)
        result = EnrichmentResult(ioc=ioc, ioc_type=ioc_type)

        async with aiohttp.ClientSession(timeout=self.TIMEOUT) as session:
            tasks: list[asyncio.Task] = []

            if ioc_type in ("ip",):
                tasks += [
                    asyncio.create_task(self._virustotal(session, ioc, "ip_addresses", result)),
                    asyncio.create_task(self._abuseipdb(session, ioc, result)),
                    asyncio.create_task(self._shodan(session, ioc, result)),
                    asyncio.create_task(self._ipinfo(session, ioc, result)),
                ]

            elif ioc_type == "domain":
                tasks += [
                    asyncio.create_task(self._virustotal(session, ioc, "domains", result)),
                    asyncio.create_task(self._whois(session, ioc, result)),
                    asyncio.create_task(self._crtsh(session, ioc, result)),
                ]

            elif ioc_type in ("url",):
                encoded = hashlib.sha256(ioc.encode()).hexdigest()
                tasks += [
                    asyncio.create_task(self._virustotal(session, encoded, "urls", result)),
                    asyncio.create_task(self._whois(session, urlparse(ioc).netloc, result)),
                ]

            elif ioc_type in ("md5", "sha1", "sha256"):
                tasks += [
                    asyncio.create_task(self._virustotal(session, ioc, "files", result)),
                ]

            elif ioc_type == "email":
                tasks += [
                    asyncio.create_task(self._hibp(session, ioc, result)),
                ]

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        result.compute_risk()
        self._apply_tags(result)
        logger.info("ioc_enriched", ioc=ioc, type=ioc_type, risk=result.risk_level, score=result.risk_score)
        return result

    # ── VirusTotal ──────────────────────────────────────────────────────────

    async def _virustotal(self, session: aiohttp.ClientSession,
                          resource: str, endpoint: str,
                          result: EnrichmentResult) -> None:
        api_key = getattr(self._settings, "virustotal_api_key", None) or \
                  __import__("os").environ.get("NCIIA_VT_API_KEY", "")
        if not api_key:
            result.errors["virustotal"] = "No API key configured"
            return

        try:
            url = f"https://www.virustotal.com/api/v3/{endpoint}/{resource}"
            async with session.get(url, headers={"x-apikey": api_key}) as resp:
                if resp.status == 404:
                    return
                if resp.status != 200:
                    result.errors["virustotal"] = f"HTTP {resp.status}"
                    return
                data = await resp.json()

            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            result.vt_malicious  = stats.get("malicious", 0)
            result.vt_suspicious = stats.get("suspicious", 0)
            result.vt_harmless   = stats.get("harmless", 0)
            result.vt_undetected = stats.get("undetected", 0)

            # Engine names that flagged it
            analyses = data.get("data", {}).get("attributes", {}).get("last_analysis_results", {})
            result.vt_engines_detected = [
                name for name, r in analyses.items()
                if r.get("category") == "malicious"
            ][:20]

            cats = data.get("data", {}).get("attributes", {}).get("categories", {})
            result.vt_categories = list(set(cats.values()))[:10]

        except Exception as exc:
            result.errors["virustotal"] = str(exc)

    # ── AbuseIPDB ───────────────────────────────────────────────────────────

    async def _abuseipdb(self, session: aiohttp.ClientSession,
                         ip: str, result: EnrichmentResult) -> None:
        api_key = __import__("os").environ.get("NCIIA_ABUSEIPDB_API_KEY", "")
        if not api_key:
            result.errors["abuseipdb"] = "No API key configured"
            return

        try:
            url = "https://api.abuseipdb.com/api/v2/check"
            params = {"ipAddress": ip, "maxAgeInDays": 90, "verbose": ""}
            headers = {"Key": api_key, "Accept": "application/json"}
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status != 200:
                    result.errors["abuseipdb"] = f"HTTP {resp.status}"
                    return
                data = (await resp.json()).get("data", {})

            result.abuse_confidence  = data.get("abuseConfidenceScore", 0)
            result.abuse_country     = data.get("countryCode", "")
            result.abuse_isp         = data.get("isp", "")
            result.abuse_usage_type  = data.get("usageType", "")
            result.abuse_total_reports = data.get("totalReports", 0)

        except Exception as exc:
            result.errors["abuseipdb"] = str(exc)

    # ── Shodan ──────────────────────────────────────────────────────────────

    async def _shodan(self, session: aiohttp.ClientSession,
                      ip: str, result: EnrichmentResult) -> None:
        api_key = __import__("os").environ.get("NCIIA_SHODAN_API_KEY", "")
        if not api_key:
            # Use free Shodan InternetDB (no key required)
            await self._shodan_free(session, ip, result)
            return

        try:
            url = f"https://api.shodan.io/shodan/host/{ip}?key={api_key}"
            async with session.get(url) as resp:
                if resp.status == 404:
                    return
                if resp.status != 200:
                    result.errors["shodan"] = f"HTTP {resp.status}"
                    return
                data = await resp.json()

            result.shodan_ports    = data.get("ports", [])
            result.shodan_org      = data.get("org", "")
            result.shodan_hostnames = data.get("hostnames", [])[:10]
            result.shodan_vulns    = list(data.get("vulns", {}).keys())[:20]
            result.shodan_tags     = data.get("tags", [])

        except Exception as exc:
            result.errors["shodan"] = str(exc)

    async def _shodan_free(self, session: aiohttp.ClientSession,
                           ip: str, result: EnrichmentResult) -> None:
        """Use Shodan InternetDB — free, no key required."""
        try:
            async with session.get(f"https://internetdb.shodan.io/{ip}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result.shodan_ports    = data.get("ports", [])
                    result.shodan_hostnames = data.get("hostnames", [])[:10]
                    result.shodan_vulns    = data.get("vulns", [])[:20]
                    result.shodan_tags     = data.get("tags", [])
        except Exception as exc:
            result.errors["shodan_free"] = str(exc)

    # ── WHOIS via RDAP ──────────────────────────────────────────────────────

    async def _whois(self, session: aiohttp.ClientSession,
                     domain: str, result: EnrichmentResult) -> None:
        try:
            async with session.get(f"https://rdap.org/domain/{domain}",
                                   headers={"Accept": "application/json"}) as resp:
                if resp.status != 200:
                    return
                data = await resp.json()

            # Events (creation, expiry)
            for event in data.get("events", []):
                action = event.get("eventAction", "")
                date   = event.get("eventDate", "")
                if action == "registration":  result.whois_created  = date[:10]
                if action == "expiration":    result.whois_expires  = date[:10]

            # Nameservers
            result.whois_name_servers = [
                ns.get("ldhName", "") for ns in data.get("nameservers", [])
            ][:6]

            # Registrant
            for entity in data.get("entities", []):
                roles = entity.get("roles", [])
                if "registrar" in roles:
                    vcard = entity.get("vcardArray", [])
                    if isinstance(vcard, list) and len(vcard) > 1:
                        for entry in vcard[1]:
                            if entry[0] == "fn":
                                result.whois_registrar = entry[3]
                                break

        except Exception as exc:
            result.errors["whois"] = str(exc)

    # ── crt.sh ──────────────────────────────────────────────────────────────

    async def _crtsh(self, session: aiohttp.ClientSession,
                     domain: str, result: EnrichmentResult) -> None:
        try:
            url = f"https://crt.sh/?q={domain}&output=json"
            async with session.get(url) as resp:
                if resp.status != 200:
                    return
                certs = await resp.json()

            domains: set[str] = set()
            issuers: set[str] = set()
            for cert in certs[:100]:
                name = cert.get("name_value", "")
                for d in name.split("\n"):
                    d = d.strip().lstrip("*.")
                    if d:
                        domains.add(d)
                issuer = cert.get("issuer_name", "")
                if "CN=" in issuer:
                    cn = issuer.split("CN=")[-1].split(",")[0].strip()
                    issuers.add(cn)

            result.cert_domains = sorted(domains)[:50]
            result.cert_issuer  = ", ".join(sorted(issuers)[:3])

        except Exception as exc:
            result.errors["crtsh"] = str(exc)

    # ── ipinfo.io ───────────────────────────────────────────────────────────

    async def _ipinfo(self, session: aiohttp.ClientSession,
                      ip: str, result: EnrichmentResult) -> None:
        token = __import__("os").environ.get("NCIIA_IPINFO_TOKEN", "")
        url = f"https://ipinfo.io/{ip}/json"
        if token:
            url += f"?token={token}"

        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return
                data = await resp.json()

            loc = data.get("loc", "0,0").split(",")
            result.geo_lat     = float(loc[0]) if len(loc) == 2 else 0.0
            result.geo_lon     = float(loc[1]) if len(loc) == 2 else 0.0
            result.geo_city    = data.get("city", "")
            result.geo_region  = data.get("region", "")
            result.geo_country = data.get("country", "")
            result.geo_asn     = data.get("org", "").split(" ")[0]
            result.geo_org     = " ".join(data.get("org", "").split(" ")[1:])
            result.geo_timezone = data.get("timezone", "")

            # Privacy flags
            privacy = data.get("privacy", {})
            result.is_tor         = bool(privacy.get("tor", False))
            result.is_vpn         = bool(privacy.get("vpn", False))
            result.is_datacenter  = bool(privacy.get("hosting", False))

        except Exception as exc:
            result.errors["ipinfo"] = str(exc)

    # ── HaveIBeenPwned ──────────────────────────────────────────────────────

    async def _hibp(self, session: aiohttp.ClientSession,
                    email: str, result: EnrichmentResult) -> None:
        api_key = __import__("os").environ.get("NCIIA_HIBP_API_KEY", "")
        if not api_key:
            result.errors["hibp"] = "No API key configured"
            return

        try:
            url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
            headers = {"hibp-api-key": api_key, "User-Agent": "N-CIIA/1.0"}
            async with session.get(url, headers=headers) as resp:
                if resp.status == 404:  # Not found = not breached
                    return
                if resp.status != 200:
                    result.errors["hibp"] = f"HTTP {resp.status}"
                    return
                breaches = await resp.json()

            result.breach_count = len(breaches)
            result.breach_names = [b.get("Name", "") for b in breaches[:20]]

        except Exception as exc:
            result.errors["hibp"] = str(exc)

    # ── Tags ─────────────────────────────────────────────────────────────────

    def _apply_tags(self, result: EnrichmentResult) -> None:
        tags: list[str] = []

        if result.vt_malicious > 5:        tags.append("malware")
        if result.vt_malicious > 0:        tags.append("av-flagged")
        if result.abuse_confidence > 80:   tags.append("abusive-ip")
        if result.is_tor:                  tags.append("tor-exit")
        if result.is_vpn:                  tags.append("vpn")
        if result.is_datacenter:           tags.append("datacenter")
        if result.shodan_vulns:            tags.append("has-cves")
        if 22 in result.shodan_ports:      tags.append("ssh-exposed")
        if 3389 in result.shodan_ports:    tags.append("rdp-exposed")
        if result.breach_count > 0:        tags.append("breached-email")
        if "phishing" in result.vt_categories: tags.append("phishing")
        if result.whois_created:
            import datetime
            try:
                age = (datetime.date.today() - datetime.date.fromisoformat(result.whois_created)).days
                if age < 30: tags.append("newly-registered")
            except Exception:
                pass

        result.tags = tags


# ─── Singleton ───────────────────────────────────────────────────────────────

_engine: Optional[EnrichmentEngine] = None

def get_enrichment_engine() -> EnrichmentEngine:
    global _engine
    if _engine is None:
        _engine = EnrichmentEngine()
    return _engine
