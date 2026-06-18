"""
Evidence API Endpoints
"""

from datetime import datetime
import hashlib
import json
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from nciia.db import get_database
from nciia.models import Evidence, EvidenceItem, Confidence
from nciia.utils import get_logger, get_audit_logger

router = APIRouter()
logger = get_logger(__name__)
audit = get_audit_logger()


class EvidenceCreateRequest(BaseModel):
    case_id: UUID
    persona_id: Optional[UUID] = None


class EvidenceItemAddRequest(BaseModel):
    title: str
    description: str
    content_type: str
    content: str
    source_url: Optional[str] = None
    source_name: str


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_evidence_package(request: EvidenceCreateRequest) -> dict[str, Any]:
    """Create a new evidence package."""
    db = await get_database()
    
    case = await db.get_case(request.case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case not found")
    
    evidence = Evidence(
        case_id=request.case_id,
        persona_id=request.persona_id,
        overall_confidence=Confidence(score=0.5, reasoning=["New package"]),
    )
    
    await db.insert_evidence(evidence.model_dump())
    
    return {"status": "created", "evidence_id": str(evidence.id)}


@router.get("/{evidence_id}")
async def get_evidence(evidence_id: UUID) -> dict[str, Any]:
    """Retrieve evidence by ID."""
    db = await get_database()
    cursor = await db._connection.execute(
        "SELECT * FROM evidence WHERE id = ?", (str(evidence_id),)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return db._row_to_dict(row)


@router.post("/{evidence_id}/items")
async def add_evidence_item(evidence_id: UUID, request: EvidenceItemAddRequest) -> dict[str, Any]:
    """Add item to evidence."""
    db = await get_database()
    
    cursor = await db._connection.execute(
        "SELECT * FROM evidence WHERE id = ?", (str(evidence_id),)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Evidence not found")
    
    evidence = db._row_to_dict(row)
    if evidence.get("is_finalized"):
        raise HTTPException(status_code=400, detail="Evidence is finalized")
    
    content_hash = hashlib.sha256(request.content.encode()).hexdigest()
    item = EvidenceItem(
        title=request.title,
        description=request.description,
        content_type=request.content_type,
        content=request.content,
        content_hash=content_hash,
        source_url=request.source_url,
        source_name=request.source_name,
    )
    
    items = evidence.get("items", [])
    items.append(item.model_dump())
    
    await db._connection.execute(
        "UPDATE evidence SET items = ? WHERE id = ?",
        [json.dumps(items, default=str), str(evidence_id)]
    )
    await db._connection.commit()
    
    return {"status": "added", "item_id": str(item.id)}


@router.post("/{evidence_id}/finalize")
async def finalize_evidence(evidence_id: UUID, analyst_id: str) -> dict[str, Any]:
    """Finalize evidence package."""
    db = await get_database()
    
    await db._connection.execute(
        "UPDATE evidence SET is_finalized=1, finalized_at=?, analyst_id=? WHERE id=?",
        [datetime.utcnow().isoformat(), analyst_id, str(evidence_id)]
    )
    await db._connection.commit()
    
    return {"status": "finalized", "evidence_id": str(evidence_id)}


@router.get("/{evidence_id}/export")
async def export_evidence(evidence_id: UUID, format: str = "json") -> Any:
    """Export evidence."""
    db = await get_database()
    
    cursor = await db._connection.execute(
        "SELECT * FROM evidence WHERE id = ?", (str(evidence_id),)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Evidence not found")
    
    return JSONResponse(content=db._row_to_dict(row))
