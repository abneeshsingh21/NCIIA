"""API routes for IOC enrichment."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from nciia.enrichment.engine import get_enrichment_engine, detect_ioc_type
from nciia.utils import get_logger

router = APIRouter()
logger = get_logger(__name__)

_cache: dict[str, dict] = {}  # Simple in-memory cache


class EnrichRequest(BaseModel):
    ioc: str
    force: bool = False


@router.post("/enrich")
async def enrich_ioc(req: EnrichRequest) -> dict[str, Any]:
    """Enrich a single IOC from all sources."""
    ioc = req.ioc.strip()
    if not ioc:
        raise HTTPException(status_code=400, detail="IOC cannot be empty")

    if not req.force and ioc in _cache:
        cached = _cache[ioc]
        cached["from_cache"] = True
        return cached

    engine = get_enrichment_engine()
    try:
        result = await engine.enrich(ioc)
        data = result.to_dict()
        _cache[ioc] = data
        return data
    except Exception as exc:
        logger.error("enrich_api_error", ioc=ioc, error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/enrich/bulk")
async def enrich_bulk(iocs: list[str]) -> list[dict[str, Any]]:
    """Enrich up to 20 IOCs in parallel."""
    if len(iocs) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 IOCs per bulk request")

    import asyncio
    engine = get_enrichment_engine()

    async def _enrich(ioc: str) -> dict:
        ioc = ioc.strip()
        if ioc in _cache:
            return {**_cache[ioc], "from_cache": True}
        try:
            result = await engine.enrich(ioc)
            data = result.to_dict()
            _cache[ioc] = data
            return data
        except Exception as exc:
            return {"ioc": ioc, "error": str(exc)}

    results = await asyncio.gather(*[_enrich(ioc) for ioc in iocs])
    return list(results)


@router.get("/detect/{ioc}")
async def detect_type(ioc: str) -> dict[str, str]:
    """Detect the type of an IOC."""
    return {"ioc": ioc, "type": detect_ioc_type(ioc)}


@router.get("/cache/stats")
async def cache_stats() -> dict[str, Any]:
    return {
        "cached_iocs": len(_cache),
        "types": {},
    }
