"""
Ingestion API Endpoints

REST endpoints for controlling OSINT collection.
"""

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from nciia.ingestion import get_collector
from nciia.utils import get_logger

router = APIRouter()
logger = get_logger(__name__)


class SearchRequest(BaseModel):
    """Request for OSINT search."""
    query: str = Field(min_length=1)
    sources: Optional[list[str]] = None


class AddQueryRequest(BaseModel):
    """Request to add a monitoring query."""
    query: str
    source: str = "WebSearch"


@router.post("/search")
async def search_osint(request: SearchRequest) -> dict[str, Any]:
    """
    Perform an OSINT search across configured sources.
    """
    collector = await get_collector()
    
    signals = await collector.search(request.query, request.sources)
    
    return {
        "status": "complete",
        "query": request.query,
        "signals_found": len(signals),
        "signals": [
            {
                "id": str(s.id),
                "type": s.type.value,
                "source": s.source_name,
                "content_preview": s.raw_content[:200] + "..." if len(s.raw_content) > 200 else s.raw_content,
            }
            for s in signals
        ],
    }


@router.post("/monitor/add")
async def add_monitor_query(request: AddQueryRequest) -> dict[str, Any]:
    """Add a query to continuous monitoring."""
    collector = await get_collector()
    
    if request.source not in collector.sources:
        raise HTTPException(status_code=404, detail=f"Source {request.source} not found")
    
    source = collector.sources[request.source]
    
    if hasattr(source, "add_query"):
        source.add_query(request.query)
    elif hasattr(source, "add_keyword"):
        source.add_keyword(request.query)
    else:
        raise HTTPException(status_code=400, detail="Source doesn't support monitoring")
    
    return {"status": "added", "query": request.query, "source": request.source}


@router.get("/news")
async def get_cyber_news():
    """Get latest cyber news headlines from external RSS feeds."""
    from nciia.ingestion.rss import get_rss_collector
    collector = get_rss_collector()
    news = await collector.fetch_headlines()
    return {"data": news}


@router.get("/stats")
async def get_collection_stats():
    """Get collection statistics."""
    collector = await get_collector()
    return collector.get_stats()


@router.get("/sources")
async def list_sources() -> dict[str, Any]:
    """List available OSINT sources."""
    collector = await get_collector()
    
    return {
        "sources": [
            {
                "name": source.name,
                "type": source.config.source_type,
                "enabled": source.is_enabled,
                "status": source.status.value,
                "last_check": source.last_check.isoformat() if source.last_check else None,
            }
            for source in collector.sources.values()
        ]
    }


@router.post("/start")
async def start_collection() -> dict[str, Any]:
    """Start continuous OSINT collection."""
    collector = await get_collector()
    await collector.start()
    return {"status": "started"}


@router.post("/stop")
async def stop_collection() -> dict[str, Any]:
    """Stop continuous OSINT collection."""
    collector = await get_collector()
    await collector.stop()
    return {"status": "stopped"}
