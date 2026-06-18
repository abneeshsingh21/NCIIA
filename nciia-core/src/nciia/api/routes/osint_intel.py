"""
OSINT Intelligence API Routes
================================
Routes for: EXIF forensics, dark web scanning, crypto tracing, UPI identity
"""
from __future__ import annotations
import asyncio
from typing import Any
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from nciia.utils import get_logger

router = APIRouter(prefix="/api/osint", tags=["OSINT Intelligence"])
logger = get_logger(__name__)


# ── EXIF Forensics ────────────────────────────────────────────────────────────

@router.post("/exif")
async def analyze_exif(file: UploadFile = File(...)) -> dict[str, Any]:
    """Upload a photo and extract all hidden EXIF metadata."""
    from nciia.osint.exif_forensics import analyze_image_async
    data = await file.read()
    if len(data) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(413, "File too large (max 50MB)")
    report = await analyze_image_async(data, file.filename or "image")
    return {
        "filename":          report.filename,
        "file_size_kb":      report.file_size_kb,
        "image_width":       report.image_width,
        "image_height":      report.image_height,
        "gps_lat":           report.gps_lat,
        "gps_lon":           report.gps_lon,
        "gps_altitude":      report.gps_altitude,
        "gps_maps_url":      report.gps_maps_url,
        "camera_make":       report.camera_make,
        "camera_model":      report.camera_model,
        "camera_serial":     report.camera_serial,
        "lens_model":        report.lens_model,
        "date_taken":        report.date_taken,
        "date_modified":     report.date_modified,
        "software":          report.software,
        "photoshop_detected":report.photoshop_detected,
        "edited":            report.edited,
        "original_format":   report.original_format,
        "whatsapp_compressed": report.whatsapp_compressed,
        "raw_exif":          report.raw_exif,
        "errors":            report.errors,
    }


# ── Dark Web Scanner ──────────────────────────────────────────────────────────

class DarkWebRequest(BaseModel):
    query: str

@router.post("/darkweb")
async def scan_darkweb(req: DarkWebRequest) -> dict[str, Any]:
    """Search dark web indexes for mentions of phone/email/username/name."""
    from nciia.osint.darkweb_scanner import scan_darkweb as _scan
    report = await _scan(req.query)
    return {
        "query":       report.query,
        "total_found": report.total_found,
        "risk_level":  report.risk_level,
        "sources_hit": report.sources_hit,
        "hits": [
            {"source": h.source, "title": h.title, "url": h.url,
             "snippet": h.snippet, "onion": h.onion}
            for h in report.hits
        ],
        "errors": report.errors,
    }


# ── Crypto Wallet Tracer ──────────────────────────────────────────────────────

class CryptoRequest(BaseModel):
    address: str

@router.post("/crypto")
async def trace_crypto(req: CryptoRequest) -> dict[str, Any]:
    """Trace a cryptocurrency wallet across BTC/ETH/BNB/TRON chains."""
    from nciia.osint.crypto_tracer import trace_wallet
    report = await trace_wallet(req.address)
    return {
        "address":           report.address,
        "chain":             report.chain,
        "balance_usd":       report.balance_usd,
        "balance_crypto":    report.balance_crypto,
        "total_received":    report.total_received,
        "total_sent":        report.total_sent,
        "tx_count":          report.tx_count,
        "first_seen":        report.first_seen,
        "last_seen":         report.last_seen,
        "label":             report.label,
        "is_exchange":       report.is_exchange,
        "mixer_detected":    report.mixer_detected,
        "risk_score":        report.risk_score,
        "risk_flags":        report.risk_flags,
        "transactions": [
            {"hash": t.hash, "from": t.from_addr, "to": t.to_addr,
             "value_usd": t.value_usd, "value_crypto": t.value_crypto,
             "timestamp": t.timestamp, "chain": t.chain, "label": t.label}
            for t in report.transactions
        ],
        "connected_wallets": report.connected_wallets,
        "errors":            report.errors,
    }


# ── UPI Identity Resolver ─────────────────────────────────────────────────────

class UPIRequest(BaseModel):
    phone: str

@router.post("/upi-identity")
async def upi_identity(req: UPIRequest) -> dict[str, Any]:
    """Resolve the real bank-verified name behind an Indian mobile number."""
    from nciia.osint.upi_resolver import resolve_identity
    result = await resolve_identity(req.phone)
    return {
        "phone":           result.phone,
        "verified_name":   result.verified_name,
        "verified_vpa":    result.verified_vpa,
        "source":          result.source,
        "confidence":      result.confidence,
        "all_names_found": result.all_names_found,
        "all_vpas_found":  result.all_vpas_found,
        "errors":          result.errors,
    }
