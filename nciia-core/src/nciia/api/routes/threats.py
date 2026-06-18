"""
Threat Intelligence API Routes

Endpoints for fetching real-time threat data and controlling threats.
"""

from typing import Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import datetime

from nciia.ingestion.threat_feeds import get_threat_collector, ThreatIndicator, ThreatType, ThreatSeverity
from nciia.utils import get_logger

router = APIRouter()
logger = get_logger(__name__)


class ThreatResponse(BaseModel):
    """Response model for threat indicators."""
    id: str
    type: str
    value: str
    source: str
    severity: str
    description: str
    first_seen: str
    last_seen: str
    tags: List[str]
    is_blocked: bool
    metadata: dict


class BlockIOCRequest(BaseModel):
    """Request to block an IOC."""
    ioc: str = Field(..., min_length=1)
    reason: Optional[str] = None


class SearchIOCRequest(BaseModel):
    """Request to search for an IOC."""
    ioc: str = Field(..., min_length=1)


def threat_to_response(threat: ThreatIndicator) -> ThreatResponse:
    """Convert ThreatIndicator to response model."""
    return ThreatResponse(
        id=threat.id,
        type=threat.type.value,
        value=threat.value,
        source=threat.source,
        severity=threat.severity.value,
        description=threat.description,
        first_seen=threat.first_seen.isoformat(),
        last_seen=threat.last_seen.isoformat(),
        tags=threat.tags,
        is_blocked=threat.is_blocked,
        metadata=threat.metadata
    )


@router.get("/live")
async def get_live_threats(
    limit: int = Query(default=50, ge=1, le=200)
) -> dict[str, Any]:
    """
    Get real-time threat intelligence from external feeds.
    
    Data sources:
    - URLhaus (Abuse.ch) - Malicious URLs
    - ThreatFox (Abuse.ch) - IOCs, C2 servers, malware hashes
    """
    collector = await get_threat_collector()
    threats = await collector.get_recent_threats(limit)
    
    # Aggregate stats
    stats = {
        "total": len(threats),
        "by_severity": {},
        "by_type": {},
        "by_source": {}
    }
    
    for threat in threats:
        sev = threat.severity.value
        stats["by_severity"][sev] = stats["by_severity"].get(sev, 0) + 1
        
        t_type = threat.type.value
        stats["by_type"][t_type] = stats["by_type"].get(t_type, 0) + 1
        
        src = threat.source
        stats["by_source"][src] = stats["by_source"].get(src, 0) + 1
    
    return {
        "status": "success",
        "fetched_at": datetime.now().isoformat(),
        "stats": stats,
        "threats": [threat_to_response(t) for t in threats]
    }


@router.post("/search")
async def search_ioc(request: SearchIOCRequest) -> dict[str, Any]:
    """
    Search for a specific IOC (URL, IP, hash) across threat feeds.
    """
    collector = await get_threat_collector()
    result = await collector.search_ioc(request.ioc)
    
    if result:
        return {
            "status": "found",
            "ioc": request.ioc,
            "threat": threat_to_response(result)
        }
    
    return {
        "status": "not_found",
        "ioc": request.ioc,
        "message": "IOC not found in threat databases"
    }


@router.post("/block")
async def block_ioc(request: BlockIOCRequest) -> dict[str, Any]:
    """
    Block an IOC locally. This adds it to the local blocklist.
    """
    collector = await get_threat_collector()
    success = collector.block_ioc(request.ioc)
    
    logger.info("ioc_block_api", ioc=request.ioc, reason=request.reason)
    
    return {
        "status": "blocked" if success else "failed",
        "ioc": request.ioc,
        "reason": request.reason,
        "blocked_at": datetime.now().isoformat()
    }


@router.post("/unblock")
async def unblock_ioc(request: BlockIOCRequest) -> dict[str, Any]:
    """
    Unblock a previously blocked IOC.
    """
    collector = await get_threat_collector()
    success = collector.unblock_ioc(request.ioc)
    
    logger.info("ioc_unblock_api", ioc=request.ioc)
    
    return {
        "status": "unblocked" if success else "failed",
        "ioc": request.ioc,
        "unblocked_at": datetime.now().isoformat()
    }


@router.get("/blocked")
async def get_blocked_iocs() -> dict[str, Any]:
    """
    Get list of all locally blocked IOCs.
    """
    collector = await get_threat_collector()
    blocked = collector.get_blocked_iocs()
    
    return {
        "status": "success",
        "count": len(blocked),
        "blocked_iocs": blocked
    }


@router.get("/stats")
async def get_threat_stats() -> dict[str, Any]:
    """
    Get aggregated threat statistics.
    """
    collector = await get_threat_collector()
    threats = await collector.get_recent_threats(100)
    blocked = collector.get_blocked_iocs()
    
    # Count by severity
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    type_counts = {}
    source_counts = {}
    
    for threat in threats:
        severity_counts[threat.severity.value] = severity_counts.get(threat.severity.value, 0) + 1
        type_counts[threat.type.value] = type_counts.get(threat.type.value, 0) + 1
        source_counts[threat.source] = source_counts.get(threat.source, 0) + 1
    
    return {
        "status": "success",
        "total_threats": len(threats),
        "blocked_count": len(blocked),
        "severity_breakdown": severity_counts,
        "type_breakdown": type_counts,
        "source_breakdown": source_counts,
        "last_updated": datetime.now().isoformat()
    }
