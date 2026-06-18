"""
Scammer Identity Profiler
=========================
Aggregates all available intelligence on a scammer / fraud actor from:
  - Phone number OSINT
  - Username enumeration (100+ platforms)
  - Email breach lookups
  - Reverse name / alias search
  - Social-media profile harvesting
  - Fraud / scam report databases
  - Paste site appearance checks

Returns a unified ScammerProfile with a confidence-weighted identity assessment.
"""
from __future__ import annotations

import asyncio
import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from nciia.utils import get_logger
from nciia.osint.phone_intel   import investigate_phone, PhoneProfile
from nciia.osint.username_enum import get_enumerator, PlatformResult

logger = get_logger(__name__)


# ─── Supporting data structures ───────────────────────────────────────────────

@dataclass
class SocialProfile:
    platform:  str
    username:  str
    url:       str
    exists:    bool
    bio:       str  = ""
    name:      str  = ""
    followers: int  = 0
    verified:  bool = False
    extra:     dict[str, Any] = field(default_factory=dict)


@dataclass
class EmailProfile:
    email:        str
    valid_format: bool      = False
    domain:       str       = ""
    disposable:   bool      = False
    breach_count: int       = 0
    breach_names: list[str] = field(default_factory=list)
    gravatar_url: str       = ""
    errors:       dict[str, str] = field(default_factory=dict)


@dataclass
class ScammerProfile:
    # Input seeds
    input_phone:    str | None = None
    input_username: str | None = None
    input_email:    str | None = None
    input_name:     str | None = None
    # Enriched data
    phone:          PhoneProfile | None           = None
    social_hits:    list[SocialProfile]           = field(default_factory=list)
    email_profile:  EmailProfile | None           = None
    # Consolidated identity
    likely_names:   list[str]                     = field(default_factory=list)
    likely_locations: list[str]                   = field(default_factory=list)
    linked_emails:  list[str]                     = field(default_factory=list)
    linked_phones:  list[str]                     = field(default_factory=list)
    # Fraud assessment
    fraud_score:    int                           = 0   # 0-100
    fraud_verdict:  str                           = "Unknown"
    fraud_evidence: list[str]                     = field(default_factory=list)
    # Meta
    sources_queried: list[str]                    = field(default_factory=list)
    enriched_at:    float                         = field(default_factory=time.time)
    errors:         dict[str, str]                = field(default_factory=dict)


# ─── Email intelligence ────────────────────────────────────────────────────────

DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "temp-mail.org", "throwam.com",
    "yopmail.com", "dispostable.com", "sharklasers.com", "maildrop.cc",
    "trashmail.com", "getnada.com", "fakeinbox.com",
}


async def _check_email(email: str, hibp_key: str | None) -> EmailProfile:
    ep = EmailProfile(email=email)
    ep.valid_format = bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))
    if not ep.valid_format:
        return ep

    ep.domain = email.split("@", 1)[1].lower()
    ep.disposable = ep.domain in DISPOSABLE_DOMAINS

    # Gravatar
    md5 = hashlib.md5(email.strip().lower().encode()).hexdigest()
    ep.gravatar_url = f"https://www.gravatar.com/avatar/{md5}?d=404"

    async with httpx.AsyncClient(verify=False) as client:
        # HIBP breach check
        if hibp_key:
            try:
                r = await client.get(
                    f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}",
                    headers={"hibp-api-key": hibp_key, "User-Agent": "NCIIA-Investigator"},
                    timeout=10,
                )
                if r.status_code == 200:
                    breaches = r.json()
                    ep.breach_count = len(breaches)
                    ep.breach_names = [b["Name"] for b in breaches[:20]]
            except Exception as exc:
                ep.errors["hibp"] = str(exc)

    return ep


# ─── Social media direct profile scraping ────────────────────────────────────

_SOCIAL_SCRAPE_TARGETS = [
    # platform, url_template, exists_hint, name_pattern, bio_pattern
    ("Instagram",  "https://www.instagram.com/{u}/",        ["og:title"],  None, None),
    ("Twitter/X",  "https://twitter.com/{u}",               ["og:title"],  None, None),
    ("GitHub",     "https://github.com/{u}",                ["vcard-fullname"], None, None),
    ("LinkedIn",   "https://www.linkedin.com/in/{u}/",      ["og:title"],  None, None),
    ("Reddit",     "https://www.reddit.com/user/{u}/",      ["og:title"],  None, None),
    ("TikTok",     "https://www.tiktok.com/@{u}",           ["og:title"],  None, None),
    ("YouTube",    "https://www.youtube.com/@{u}",          ["og:title"],  None, None),
    ("Telegram",   "https://t.me/{u}",                      ["og:title"],  None, None),
    ("Pinterest",  "https://www.pinterest.com/{u}/",        ["og:title"],  None, None),
    ("Snapchat",   "https://www.snapchat.com/add/{u}",      ["og:title"],  None, None),
]


async def _scrape_social(client: httpx.AsyncClient, platform: str, url: str, username: str) -> SocialProfile:
    sp = SocialProfile(platform=platform, username=username, url=url, exists=False)
    try:
        r = await client.get(url, timeout=10, follow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0 (compatible; NCIIAScout/1.0)"})
        if r.status_code == 200 and "not found" not in r.text.lower()[:500]:
            sp.exists = True
            # Extract og:title for name hints
            m = re.search(r'<meta property="og:title" content="([^"]+)"', r.text)
            if m:
                sp.name = m.group(1).split("|")[0].strip()
            # Extract og:description for bio
            m2 = re.search(r'<meta property="og:description" content="([^"]+)"', r.text)
            if m2:
                sp.bio = m2.group(1)[:200]
    except Exception as exc:
        logger.debug("social_scrape_fail", platform=platform, error=str(exc))
    return sp


async def _scrape_all_social(username: str) -> list[SocialProfile]:
    async with httpx.AsyncClient(verify=False, follow_redirects=True) as client:
        tasks = [
            _scrape_social(client, platform, url.replace("{u}", username), username)
            for platform, url, *_ in _SOCIAL_SCRAPE_TARGETS
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, SocialProfile) and r.exists]


# ─── Paste site leak scan ────────────────────────────────────────────────────

async def _check_pastes(query: str) -> list[str]:
    """Check if the query appears on common paste sites."""
    found: list[str] = []
    targets = [
        f"https://pastebin.com/search?q={query}",
        f"https://ghostbin.com/search?q={query}",
    ]
    async with httpx.AsyncClient(verify=False) as client:
        for url in targets:
            try:
                r = await client.get(url, timeout=10,
                                     headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200 and len(r.text) > 1000:
                    found.append(url)
            except Exception:
                pass
    return found


# ─── Fraud score calculator ──────────────────────────────────────────────────

def _calculate_fraud_score(profile: ScammerProfile) -> tuple[int, str, list[str]]:
    score    = 0
    evidence: list[str] = []

    # Phone signals
    if profile.phone:
        ph = profile.phone
        score += ph.spam_score // 2               # up to 50 pts
        if ph.spam_score > 50:
            evidence.append(f"Phone has high spam score ({ph.spam_score}/100)")
        if ph.fraud_reports > 0:
            score += min(20, ph.fraud_reports * 5)
            evidence.append(f"{ph.fraud_reports} community fraud reports")
        if ph.spam_databases:
            evidence.append(f"Appears on spam databases: {', '.join(ph.spam_databases)}")
        if ph.line_type == "voip":
            score += 10
            evidence.append("Phone is a VoIP number (common with scammers)")
        if "Scam" in ph.spam_labels or "fraud" in ph.spam_labels:
            score += 20
            evidence.append("Explicitly labelled as scam/fraud")

    # Email signals
    if profile.email_profile:
        em = profile.email_profile
        if em.disposable:
            score += 25
            evidence.append(f"Uses disposable/throwaway email domain ({em.domain})")
        if em.breach_count > 0:
            score += min(15, em.breach_count * 3)
            evidence.append(f"Email found in {em.breach_count} data breach(es): {', '.join(em.breach_names[:3])}")

    # Social signals: few profiles = evasion
    if len(profile.social_hits) == 0 and profile.input_username:
        score += 10
        evidence.append("No social presence found — possible burner identity")
    elif len(profile.social_hits) > 5:
        evidence.append(f"Active across {len(profile.social_hits)} platforms")

    score = min(100, score)
    if score >= 75:
        verdict = "🔴 High Fraud Risk"
    elif score >= 50:
        verdict = "🟠 Medium Fraud Risk"
    elif score >= 25:
        verdict = "🟡 Suspicious"
    else:
        verdict = "🟢 Low / No Risk Detected"

    return score, verdict, evidence


# ─── Master investigation function ───────────────────────────────────────────

async def investigate_scammer(
    phone:    str | None = None,
    username: str | None = None,
    email:    str | None = None,
    name:     str | None = None,
    # Optional API keys
    numlookup_key: str | None = None,
    abstract_key:  str | None = None,
    hibp_key:      str | None = None,
) -> ScammerProfile:
    """
    Comprehensive scammer/fraud actor investigation.
    Accepts any combination of phone, username, email, and name.
    Returns a unified ScammerProfile with fraud scoring.
    """
    profile = ScammerProfile(
        input_phone=phone,
        input_username=username,
        input_email=email,
        input_name=name,
    )

    tasks: list[Any] = []

    # ── Phase 1: parallel investigation across all input seeds ────────────────
    phone_coro    = investigate_phone(phone, numlookup_key, abstract_key) if phone else None
    email_coro    = _check_email(email, hibp_key) if email else None
    social_coro   = _scrape_all_social(username) if username else None
    enum_coro     = get_enumerator().enumerate(username) if username else None
    paste_coro    = _check_pastes(phone or username or email or name or "") if any([phone, username, email, name]) else None

    results = await asyncio.gather(
        phone_coro  or asyncio.sleep(0),
        email_coro  or asyncio.sleep(0),
        social_coro or asyncio.sleep(0),
        enum_coro   or asyncio.sleep(0),
        paste_coro  or asyncio.sleep(0),
        return_exceptions=True,
    )

    # ── Phase 2: extract results ───────────────────────────────────────────────
    phone_result, email_result, social_result, enum_result, paste_result = results

    # Unwrap EnumerationReport into a flat list of PlatformResult
    from nciia.osint.username_enum import EnumerationReport
    if isinstance(enum_result, EnumerationReport):
        enum_result = enum_result.found_on

    if isinstance(phone_result, PhoneProfile):
        profile.phone = phone_result
        profile.sources_queried.append("phone_intel")
        if phone_result.location:
            profile.likely_locations.append(phone_result.location)
        if phone_result.country_name:
            profile.likely_locations.append(phone_result.country_name)

    if isinstance(email_result, EmailProfile):
        profile.email_profile = email_result
        profile.sources_queried.append("email_intel")
        if email_result.gravatar_url:
            profile.linked_emails.append(email)

    if isinstance(social_result, list):
        profile.social_hits = social_result
        profile.sources_queried.append("social_scrape")
        for sp in social_result:
            if sp.name and sp.name not in profile.likely_names:
                profile.likely_names.append(sp.name)

    if isinstance(enum_result, list):
        # Merge enum results into social_hits (avoids duplicates)
        existing_platforms = {s.platform.lower() for s in profile.social_hits}
        for r in enum_result:
            if isinstance(r, PlatformResult) and r.found and r.platform.lower() not in existing_platforms:
                profile.social_hits.append(SocialProfile(
                    platform=r.platform, username=r.username if hasattr(r, 'username') else username or '',
                    url=r.url, exists=True, bio=r.bio if hasattr(r, 'bio') else "",
                    name=r.display_name if hasattr(r, 'display_name') else "",
                ))
                existing_platforms.add(r.platform.lower())
        profile.sources_queried.append("username_enum")

    # ── Phase 3: fraud scoring ─────────────────────────────────────────────────
    profile.fraud_score, profile.fraud_verdict, profile.fraud_evidence = _calculate_fraud_score(profile)

    profile.enriched_at = time.time()
    logger.info(
        "scammer_investigated",
        phone=phone, username=username, email=email,
        fraud_score=profile.fraud_score,
        verdict=profile.fraud_verdict,
        social_hits=len(profile.social_hits),
    )
    return profile
