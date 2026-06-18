"""
Case API Endpoints

Handles investigation case management.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from nciia.db import get_database
from nciia.models import Case
from nciia.utils import get_logger, get_audit_logger

router = APIRouter()
logger = get_logger(__name__)
audit = get_audit_logger()


class CaseCreateRequest(BaseModel):
    """Request body for creating a case."""
    
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="")
    priority: str = Field(default="medium")
    analyst_id: Optional[str] = None


class CaseUpdateRequest(BaseModel):
    """Request body for updating a case."""
    
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    analyst_id: Optional[str] = None


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_case(request: CaseCreateRequest) -> dict[str, Any]:
    """Create a new investigation case."""
    db = await get_database()
    
    case = Case(
        name=request.name,
        description=request.description,
        priority=request.priority,
        analyst_id=request.analyst_id,
    )
    
    await db.insert_case(case.model_dump())
    
    audit.log_action(
        action="create",
        entity_type="case",
        entity_id=str(case.id),
        analyst_id=request.analyst_id,
        details={"name": case.name},
    )
    
    logger.info("case_created", case_id=str(case.id), name=case.name)
    
    return {
        "status": "created",
        "case_id": str(case.id),
        "name": case.name,
    }


@router.get("/{case_id}")
async def get_case(case_id: UUID) -> dict[str, Any]:
    """Retrieve a case by ID."""
    db = await get_database()
    case = await db.get_case(case_id)
    
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )
    
    return case


@router.get("/")
async def list_cases(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    analyst_id: Optional[str] = None,
    limit: int = Query(default=50, le=200),
) -> dict[str, Any]:
    """List cases with optional filtering."""
    db = await get_database()
    
    query = "SELECT * FROM cases WHERE 1=1"
    params: list[Any] = []
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    
    if analyst_id:
        query += " AND analyst_id = ?"
        params.append(analyst_id)
    
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    
    cursor = await db._connection.execute(query, params)
    rows = await cursor.fetchall()
    cases = [db._row_to_dict(row) for row in rows]
    
    return {"cases": cases, "total": len(cases)}


@router.patch("/{case_id}")
async def update_case(case_id: UUID, request: CaseUpdateRequest) -> dict[str, Any]:
    """Update a case."""
    db = await get_database()
    
    case = await db.get_case(case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )
    
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    
    if updates:
        # Add to action log
        action_log = case.get("action_log", [])
        action_log.append({
            "action": "update",
            "timestamp": datetime.utcnow().isoformat(),
            "fields": list(updates.keys()),
        })
        updates["action_log"] = action_log
        
        # Update in database
        await db._connection.execute(
            f"""
            UPDATE cases SET 
                {', '.join(f'{k} = ?' for k in updates.keys())},
                updated_at = ?
            WHERE id = ?
            """,
            [*updates.values(), datetime.utcnow().isoformat(), str(case_id)]
        )
        await db._connection.commit()
    
    logger.info("case_updated", case_id=str(case_id), fields=list(updates.keys()))
    
    return {"status": "updated", "case_id": str(case_id)}


@router.post("/{case_id}/close")
async def close_case(case_id: UUID, analyst_id: Optional[str] = None) -> dict[str, Any]:
    """Close an investigation case."""
    db = await get_database()
    
    case = await db.get_case(case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )
    
    if case.get("status") == "closed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Case is already closed",
        )
    
    await db._connection.execute(
        """
        UPDATE cases SET 
            status = 'closed',
            closed_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        [datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), str(case_id)]
    )
    await db._connection.commit()
    
    audit.log_action(
        action="close",
        entity_type="case",
        entity_id=str(case_id),
        analyst_id=analyst_id,
    )
    
    logger.info("case_closed", case_id=str(case_id))
    
    return {"status": "closed", "case_id": str(case_id)}


@router.post("/{case_id}/personas/{persona_id}")
async def link_persona_to_case(case_id: UUID, persona_id: UUID) -> dict[str, Any]:
    """Link a persona to a case."""
    db = await get_database()
    
    case = await db.get_case(case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case {case_id} not found",
        )
    
    persona = await db.get_persona(persona_id)
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found",
        )
    
    persona_ids = case.get("persona_ids", [])
    if str(persona_id) not in persona_ids:
        persona_ids.append(str(persona_id))
        await db._connection.execute(
            "UPDATE cases SET persona_ids = ?, updated_at = ? WHERE id = ?",
            [str(persona_ids), datetime.utcnow().isoformat(), str(case_id)]
        )
        await db._connection.commit()
    
    # Update persona's case_id
    await db.update_persona(persona_id, {"case_id": str(case_id)})
    
    logger.info("persona_linked", case_id=str(case_id), persona_id=str(persona_id))
    
    return {
        "status": "linked",
        "case_id": str(case_id),
        "persona_id": str(persona_id),
    }
