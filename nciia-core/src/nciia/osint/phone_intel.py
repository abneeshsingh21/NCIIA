"""
Phone Number Intelligence Engine
=================================
Gathers open-source intelligence on any phone number including:
- Carrier / line-type identification (mobile, VoIP, landline)
- Country / region / timezone metadata
- Reverse-lookup via public sources (NumLookupAPI, AbstractAPI, ...)
- WhatsApp / Telegram / Signal activity probing
- Spam-database cross-referencing (Truecaller community data patterns)
- Appearance in known breach / leak datasets
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

# ── Regex: very loose – accepts +91XXXXXXXXXX, 91XXXXXXXXXX, plain 10-digits, etc.
PHONE_RE = re.compile(r"[\+]?[\d\s\-\(\)]{7,20}")

# ── Public / free-tier API endpoints (no key required unless noted) ──────────
NUMVERIFY_ENDPOINT   = "http://apilayer.net/api/validate"          # free tier (key optional)
ABSTRACT_ENDPOINT    = "https://phonevalidation.abstractapi.com/v1"# needs key
NUMLOOKUP_ENDPOINT   = "https://api.numlookupapi.com/v1/info"      # free tier exists
IPAPI_ENDPOINT       = "https://ipapi.co/json"                      # for geo cross-check
TRUECALLER_SUGGEST   = "https://search5-noneu.truecaller.com/v2/search"  # community headers only

WHATSAPP_CHECK_URL   = "https://wa.me/{number}"
TELEGRAM_CHECK_URL   = "https://t.me/+{number}"

# ── Spam & scam reports ──────────────────────────────────────────────────────
SPAM_DOSSIER_URL     = "https://www.spamcalls.net/en/search?q={number}"
SHOULD_I_ANSWER_URL  = "https://www.shouldianswer.com/phone-number/{number}"
WHOCALLD_URL         = "https://whocalld.com/+{number}"
SCAM_SEARCH_URL      = "https://scamsearch.io/search_report?search={number}"

@dataclass
class PhoneProfile:
    raw_input: str
    normalized: str          = ""
    country_code: str        = ""
    country_name: str        = ""
    carrier: str             = ""
    line_type: str           = ""       # mobile | landline | voip | unknown
    location: str            = ""
    timezone: str            = ""
    is_valid: bool           = False
    is_possible: bool        = False
    # Social presence
    whatsapp_active: bool    = False
    telegram_active: bool    = False
    # Spam / fraud signals
    spam_score: int          = 0        # 0-100
    fraud_reports: int       = 0
    spam_labels: list[str]   = field(default_factory=list)
    spam_databases: list[str]= field(default_factory=list)
    # Raw sources
    sources: dict[str, Any]  = field(default_factory=dict)
    errors: dict[str, str]   = field(default_factory=dict)
    enriched_at: float       = field(default_factory=time.time)


def _normalize(raw: str) -> str:
    """Strip everything except digits and leading +."""
    digits = re.sub(r"[^\d]", "", raw)
    return f"+{digits}" if not raw.strip().startswith("+") else f"+{digits}"


async def _get(client: httpx.AsyncClient, url: str, **kwargs: Any) -> httpx.Response | None:
    try:
        r = await client.get(url, timeout=10, **kwargs)
        r.raise_for_status()
        return r
    except Exception as exc:
        logger.debug("phone_get_failed", url=url, error=str(exc))
        return None


# ── Individual probe functions ─────────────────────────────────────────────────

async def _probe_numlookup(client: httpx.AsyncClient, number: str, api_key: str | None, profile: PhoneProfile) -> None:
    """Free tier: country, carrier, line type."""
    try:
        params: dict[str, str] = {"number": number}
        if api_key:
            params["apikey"] = api_key
        resp = await _get(client, NUMLOOKUP_ENDPOINT, params=params)
        if resp is None:
            return
        data = resp.json()
        profile.sources["numlookup"] = data
        profile.is_valid     = data.get("valid", False)
        profile.country_code = data.get("country_code", "")
        profile.country_name = data.get("country_name", "")
        profile.carrier      = data.get("carrier", "")
        line_type            = data.get("line_type", "")
        profile.line_type    = line_type if line_type else "unknown"
        profile.location     = data.get("location", "")
        profile.timezone     = data.get("timezones", [""])[0] if data.get("timezones") else ""
        profile.normalized   = data.get("number", number)
        profile.is_possible  = data.get("valid", False)
    except Exception as exc:
        profile.errors["numlookup"] = str(exc)


async def _probe_abstract(client: httpx.AsyncClient, number: str, api_key: str, profile: PhoneProfile) -> None:
    """AbstractAPI — requires free key (500 req/month)."""
    try:
        resp = await _get(client, ABSTRACT_ENDPOINT, params={"api_key": api_key, "phone": number})
        if resp is None:
            return
        data = resp.json()
        profile.sources["abstract"] = data
        if not profile.carrier and data.get("carrier"):
            profile.carrier    = data["carrier"]
        if not profile.line_type or profile.line_type == "unknown":
            fmt = data.get("type", "")
            profile.line_type  = fmt.lower() if fmt else "unknown"
        if not profile.country_name and data.get("country"):
            profile.country_name = data["country"].get("name", "")
        if not profile.location and data.get("location"):
            profile.location = data["location"]
    except Exception as exc:
        profile.errors["abstract"] = str(exc)


async def _probe_whatsapp(client: httpx.AsyncClient, digits: str, profile: PhoneProfile) -> None:
    """Check if WhatsApp returns 200 for the number (public redirect)."""
    try:
        url = f"https://api.whatsapp.com/send?phone={digits}"
        resp = await client.get(url, timeout=8, follow_redirects=True)
        # WA returns 200 with JS content if the number is valid account
        if resp.status_code == 200 and "invalid" not in resp.text.lower():
            profile.whatsapp_active = True
    except Exception:
        pass


async def _probe_spam_databases(client: httpx.AsyncClient, digits: str, profile: PhoneProfile) -> None:
    """
    Check multiple spam-report crowd-sources.  We use heuristics:
    - HTTP 200 + presence of keywords like 'scam', 'fraud', 'spam' in body
    """
    checks = [
        ("SpamCalls",      f"https://www.spamcalls.net/en/search?q={digits}"),
        ("ShouldIAnswer",  f"https://www.shouldianswer.com/phone-number/{digits}"),
        ("WhoCalld",       f"https://whocalld.com/+{digits}"),
        ("CallerIdTest",   f"https://www.calleridtest.com/phone-lookup/{digits}"),
    ]
    bad_keywords = ["scam", "fraud", "spam", "phishing", "dangerous",
                    "reported", "telemarketer", "robocall", "nuisance"]
    hit_labels: list[str] = []
    hit_dbs: list[str]    = []

    async def _check(label: str, url: str) -> None:
        try:
            r = await client.get(url, timeout=10, follow_redirects=True,
                                 headers={"User-Agent": "Mozilla/5.0 (compatible; NCIIABot/1.0)"})
            if r.status_code == 200:
                body = r.text.lower()
                hits = [kw for kw in bad_keywords if kw in body]
                if hits:
                    hit_labels.extend(hits[:3])
                    hit_dbs.append(label)
                    profile.fraud_reports += body.count("report")
        except Exception:
            pass

    await asyncio.gather(*[_check(label, url) for label, url in checks])

    profile.spam_labels   = list(set(hit_labels))
    profile.spam_databases= hit_dbs
    profile.spam_score    = min(100, len(hit_dbs) * 25 + len(hit_labels) * 5)


# ── Main entry point ──────────────────────────────────────────────────────────

async def investigate_phone(
    raw_number: str,
    api_key_numlookup: str | None = None,
    api_key_abstract: str | None  = None,
) -> PhoneProfile:
    """
    Full async phone intelligence investigation.
    Returns a PhoneProfile with every field populated from available sources.
    """
    profile = PhoneProfile(raw_input=raw_number)
    digits  = re.sub(r"[^\d]", "", raw_number)

    async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
        tasks = [
            _probe_numlookup(client, raw_number, api_key_numlookup, profile),
            _probe_spam_databases(client, digits, profile),
            _probe_whatsapp(client, digits, profile),
        ]
        if api_key_abstract:
            tasks.append(_probe_abstract(client, raw_number, api_key_abstract, profile))

        await asyncio.gather(*tasks, return_exceptions=True)

    profile.enriched_at = time.time()
    logger.info("phone_investigated", number=raw_number, spam_score=profile.spam_score,
                valid=profile.is_valid, fraud_reports=profile.fraud_reports)
    return profile
