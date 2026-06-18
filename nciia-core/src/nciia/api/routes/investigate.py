"""
Scammer / Fraud Investigation API Routes
=========================================
POST /api/investigate/scammer
GET  /api/investigate/phone/{number}
GET  /api/investigate/username/{username}
"""
from __future__ import annotations

from typing import Any, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

from nciia.osint.scammer_profiler import investigate_scammer, ScammerProfile, SocialProfile, EmailProfile
from nciia.osint.phone_intel import investigate_phone, PhoneProfile
from nciia.utils import get_settings, get_logger

router = APIRouter(prefix="/api/investigate", tags=["investigate"])
logger = get_logger(__name__)


# ── Request / Response models ─────────────────────────────────────────────────

class InvestigateRequest(BaseModel):
    phone:    Optional[str] = None
    username: Optional[str] = None
    email:    Optional[str] = None
    name:     Optional[str] = None


class PhoneProfileOut(BaseModel):
    raw_input:      str
    normalized:     str
    country_code:   str
    country_name:   str
    carrier:        str
    line_type:      str
    location:       str
    timezone:       str
    is_valid:       bool
    whatsapp_active: bool
    telegram_active: bool
    spam_score:     int
    fraud_reports:  int
    spam_labels:    list[str]
    spam_databases: list[str]
    errors:         dict[str, str]

class EmailProfileOut(BaseModel):
    email:        str
    valid_format: bool
    domain:       str
    disposable:   bool
    breach_count: int
    breach_names: list[str]
    gravatar_url: str

class SocialHitOut(BaseModel):
    platform:  str
    username:  str
    url:       str
    exists:    bool
    bio:       str
    name:      str

class ScammerProfileOut(BaseModel):
    input_phone:      Optional[str]
    input_username:   Optional[str]
    input_email:      Optional[str]
    input_name:       Optional[str]
    phone:            Optional[PhoneProfileOut]
    email_profile:    Optional[EmailProfileOut]
    social_hits:      list[SocialHitOut]
    likely_names:     list[str]
    likely_locations: list[str]
    linked_emails:    list[str]
    fraud_score:      int
    fraud_verdict:    str
    fraud_evidence:   list[str]
    sources_queried:  list[str]
    enriched_at:      float


def _phone_out(p: PhoneProfile) -> PhoneProfileOut:
    return PhoneProfileOut(
        raw_input=p.raw_input, normalized=p.normalized,
        country_code=p.country_code, country_name=p.country_name,
        carrier=p.carrier, line_type=p.line_type,
        location=p.location, timezone=p.timezone,
        is_valid=p.is_valid,
        whatsapp_active=p.whatsapp_active, telegram_active=p.telegram_active,
        spam_score=p.spam_score, fraud_reports=p.fraud_reports,
        spam_labels=p.spam_labels, spam_databases=p.spam_databases,
        errors=p.errors,
    )


def _email_out(e: EmailProfile) -> EmailProfileOut:
    return EmailProfileOut(
        email=e.email, valid_format=e.valid_format, domain=e.domain,
        disposable=e.disposable, breach_count=e.breach_count,
        breach_names=e.breach_names, gravatar_url=e.gravatar_url,
    )


def _social_out(s: SocialProfile) -> SocialHitOut:
    return SocialHitOut(
        platform=s.platform, username=s.username, url=s.url,
        exists=s.exists, bio=s.bio, name=s.name,
    )


def _profile_out(p: ScammerProfile) -> ScammerProfileOut:
    return ScammerProfileOut(
        input_phone=p.input_phone, input_username=p.input_username,
        input_email=p.input_email, input_name=p.input_name,
        phone=_phone_out(p.phone) if p.phone else None,
        email_profile=_email_out(p.email_profile) if p.email_profile else None,
        social_hits=[_social_out(s) for s in p.social_hits],
        likely_names=p.likely_names, likely_locations=p.likely_locations,
        linked_emails=p.linked_emails,
        fraud_score=p.fraud_score, fraud_verdict=p.fraud_verdict,
        fraud_evidence=p.fraud_evidence, sources_queried=p.sources_queried,
        enriched_at=p.enriched_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/scammer", response_model=ScammerProfileOut)
async def investigate_scammer_endpoint(req: InvestigateRequest) -> Any:
    """
    Master scammer investigation endpoint.
    Supply any combination of: phone, username, email, name.
    Returns comprehensive fraud profile with evidence chain.
    """
    settings = get_settings()
    profile = await investigate_scammer(
        phone=req.phone,
        username=req.username,
        email=req.email,
        name=req.name,
        numlookup_key=getattr(settings, "numlookup_api_key", None),
        abstract_key=getattr(settings, "abstract_api_key", None),
        hibp_key=getattr(settings, "hibp_api_key", None),
    )
    return _profile_out(profile)


@router.get("/phone/{number}", response_model=PhoneProfileOut)
async def phone_lookup(number: str) -> Any:
    """Quick phone number intelligence lookup."""
    settings = get_settings()
    result = await investigate_phone(
        raw_number=number,
        api_key_numlookup=getattr(settings, "numlookup_api_key", None),
        api_key_abstract=getattr(settings, "abstract_api_key", None),
    )
    return _phone_out(result)


@router.get("/username/{username}")
async def username_lookup(username: str) -> Any:
    """Cross-platform username presence check (100+ platforms)."""
    from nciia.osint.username_enum import get_enumerator
    report = await get_enumerator().enumerate(username)
    return {
        "username": username,
        "total_platforms_checked": len(report.found_on) + len(report.not_found_on),
        "found_on": len(report.found_on),
        "duration_ms": report.duration_ms,
        "platforms": [
            {"platform": r.platform, "url": r.url, "category": r.category, "response_ms": r.response_time_ms}
            for r in report.found_on
        ],
    }
