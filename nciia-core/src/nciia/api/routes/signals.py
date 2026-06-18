"""
Signal API Endpoints

Handles CRUD operations for intelligence signals.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from nciia.db import get_database
from nciia.models import Signal, SignalType
from nciia.utils import get_logger, get_audit_logger

router = APIRouter()
logger = get_logger(__name__)
audit = get_audit_logger()


class SignalCreateRequest(BaseModel):
    """Request body for creating a signal."""
    
    type: SignalType
    source_url: Optional[str] = None
    source_name: str
    raw_content: str = Field(min_length=1)
    extracted_text: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    content_timestamp: Optional[datetime] = None


class SignalResponse(BaseModel):
    """Response model for signal data."""
    
    id: UUID
    type: SignalType
    source_url: Optional[str]
    source_name: str
    raw_content: str
    extracted_text: Optional[str]
    metadata: dict[str, Any]
    discovered_at: datetime
    content_timestamp: Optional[datetime]
    content_hash: str
    is_processed: bool
    age_hours: float
    
    class Config:
        from_attributes = True


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_signal(request: SignalCreateRequest) -> dict[str, Any]:
    """
    Create a new intelligence signal.
    
    This is the primary ingestion endpoint for OSINT data.
    """
    db = await get_database()
    
    # Create signal object
    signal = Signal(
        type=request.type,
        source_url=request.source_url,
        source_name=request.source_name,
        raw_content=request.raw_content,
        extracted_text=request.extracted_text,
        metadata=request.metadata,
        content_timestamp=request.content_timestamp,
    )
    
    # Check for duplicates
    existing = await db.get_signals_by_hash(signal.content_hash)
    if existing:
        logger.info("duplicate_signal_detected", hash=signal.content_hash)
        return {
            "status": "duplicate",
            "message": "Signal with identical content already exists",
            "existing_id": existing[0]["id"],
        }
    
    # Insert signal
    await db.insert_signal(signal.model_dump())
    
    audit.log_action(
        action="create",
        entity_type="signal",
        entity_id=str(signal.id),
        details={"type": signal.type, "source": signal.source_name},
    )
    
    logger.info("signal_created", signal_id=str(signal.id), type=signal.type)
    
    return {
        "status": "created",
        "signal_id": str(signal.id),
        "content_hash": signal.content_hash,
    }


@router.get("/{signal_id}")
async def get_signal(signal_id: UUID) -> dict[str, Any]:
    """Retrieve a signal by ID."""
    db = await get_database()
    signal = await db.get_signal(signal_id)
    
    if not signal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal {signal_id} not found",
        )
    
    return signal


@router.get("/")
async def list_signals(
    type: Optional[SignalType] = None,
    is_processed: Optional[bool] = None,
    since: Optional[datetime] = None,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """List signals with optional filtering."""
    db = await get_database()
    
    # Build query
    query = "SELECT * FROM signals WHERE 1=1"
    params: list[Any] = []
    
    if type:
        query += " AND type = ?"
        params.append(type.value)
    
    if is_processed is not None:
        query += " AND is_processed = ?"
        params.append(is_processed)
    
    if since:
        query += " AND discovered_at >= ?"
        params.append(since.isoformat())
    
    query += " ORDER BY discovered_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor = await db._connection.execute(query, params)
    rows = await cursor.fetchall()
    signals = [db._row_to_dict(row) for row in rows]
    
    # Get total count
    count_query = "SELECT COUNT(*) as count FROM signals WHERE 1=1"
    count_params: list[Any] = []
    
    if type:
        count_query += " AND type = ?"
        count_params.append(type.value)
    
    if is_processed is not None:
        count_query += " AND is_processed = ?"
        count_params.append(is_processed)
    
    cursor = await db._connection.execute(count_query, count_params)
    total = (await cursor.fetchone())["count"]
    
    return {
        "signals": signals,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.patch("/{signal_id}/process")
async def mark_signal_processed(
    signal_id: UUID,
    notes: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Mark a signal as processed."""
    db = await get_database()
    
    # Verify signal exists
    signal = await db.get_signal(signal_id)
    if not signal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Signal {signal_id} not found",
        )
    
    await db.mark_signal_processed(signal_id, notes)
    
    logger.info("signal_processed", signal_id=str(signal_id))
    
    return {"status": "processed", "signal_id": str(signal_id)}
