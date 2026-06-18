"""
Persona API Endpoints

Handles digital persona operations including reconstruction,
monitoring, and correlation.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from nciia.db import get_database
from nciia.models import Persona, Entity, EntityType, Confidence
from nciia.utils import get_logger, get_audit_logger

router = APIRouter()
logger = get_logger(__name__)
audit = get_audit_logger()


class PersonaSeedRequest(BaseModel):
    """Request to create a persona from a seed identifier."""
    
    seed_type: EntityType
    seed_value: str = Field(min_length=1)
    case_id: Optional[UUID] = None
    start_investigation: bool = False


class PersonaResponse(BaseModel):
    """Response model for persona data."""
    
    id: UUID
    primary_identifier: str
    identifier_type: EntityType
    entity_count: int
    alias_count: int
    platforms_detected: list[str]
    activity_count: int
    first_activity: Optional[datetime]
    last_activity: Optional[datetime]
    is_active_watch: bool
    overall_confidence: float
    
    class Config:
        from_attributes = True


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_persona(request: PersonaSeedRequest) -> dict[str, Any]:
    """
    Create a new persona from a seed identifier.
    
    This initiates the persona reconstruction process.
    """
    db = await get_database()
    
    # Create initial entity from seed
    entity = Entity(
        type=request.seed_type,
        value=request.seed_value.lower().strip(),
        original_value=request.seed_value,
        confidence=Confidence(score=1.0, reasoning=["User-provided seed"]),
    )
    
    # Create persona
    persona = Persona(
        case_id=request.case_id,
        primary_identifier=entity.value,
        identifier_type=request.seed_type,
        entities=[entity],
        first_activity=datetime.utcnow(),
        last_activity=datetime.utcnow(),
        overall_confidence=Confidence(
            score=0.5,
            reasoning=["Initial persona creation from seed"],
        ),
    )
    
    # Store persona
    await db.insert_persona(persona.model_dump())
    
    audit.log_action(
        action="create",
        entity_type="persona",
        entity_id=str(persona.id),
        details={
            "seed_type": request.seed_type,
            "seed_value": entity.value,
        },
    )
    
    logger.info(
        "persona_created",
        persona_id=str(persona.id),
        seed_type=request.seed_type,
        seed_value=entity.value,
    )
    
    return {
        "status": "created",
        "persona_id": str(persona.id),
        "message": "Persona created. Use /reconstruct to start OSINT collection.",
    }


@router.get("/{persona_id}")
async def get_persona(persona_id: UUID) -> dict[str, Any]:
    """Retrieve a persona by ID."""
    db = await get_database()
    persona = await db.get_persona(persona_id)
    
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found",
        )
    
    return persona


@router.get("/")
async def list_personas(
    identifier: Optional[str] = None,
    case_id: Optional[UUID] = None,
    is_active_watch: Optional[bool] = None,
    limit: int = Query(default=50, le=200),
) -> dict[str, Any]:
    """List personas with optional filtering."""
    db = await get_database()
    
    personas = await db.search_personas(
        identifier=identifier,
        case_id=case_id,
        is_active_watch=is_active_watch,
        limit=limit,
    )
    
    return {
        "personas": personas,
        "total": len(personas),
    }


@router.post("/{persona_id}/watch")
async def start_watch(persona_id: UUID) -> dict[str, Any]:
    """Enable real-time monitoring for a persona."""
    db = await get_database()
    
    persona = await db.get_persona(persona_id)
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found",
        )
    
    await db.update_persona(persona_id, {"is_active_watch": True})
    
    audit.log_watcher_action("start", str(persona_id))
    logger.info("watch_started", persona_id=str(persona_id))
    
    return {
        "status": "watching",
        "persona_id": str(persona_id),
        "message": "Real-time monitoring enabled",
    }


@router.delete("/{persona_id}/watch")
async def stop_watch(persona_id: UUID) -> dict[str, Any]:
    """Disable real-time monitoring for a persona."""
    db = await get_database()
    
    persona = await db.get_persona(persona_id)
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found",
        )
    
    await db.update_persona(persona_id, {"is_active_watch": False})
    
    audit.log_watcher_action("stop", str(persona_id))
    logger.info("watch_stopped", persona_id=str(persona_id))
    
    return {
        "status": "stopped",
        "persona_id": str(persona_id),
        "message": "Real-time monitoring disabled",
    }


@router.post("/{persona_id}/entities")
async def add_entity(
    persona_id: UUID,
    entity_type: EntityType,
    value: str,
    is_alias: bool = False,
) -> dict[str, Any]:
    """Add an entity to a persona."""
    db = await get_database()
    
    persona = await db.get_persona(persona_id)
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found",
        )
    
    # Create entity
    entity = Entity(
        type=entity_type,
        value=value.lower().strip(),
        original_value=value,
        confidence=Confidence(score=0.8, reasoning=["Analyst-provided"]),
    )
    
    # Update persona
    entities = persona.get("entities", [])
    entities.append(entity.model_dump())
    
    await db.update_persona(persona_id, {"entities": entities})
    
    logger.info(
        "entity_added",
        persona_id=str(persona_id),
        entity_type=entity_type,
        value=entity.value,
    )
    
    return {
        "status": "added",
        "entity_id": str(entity.id),
        "persona_id": str(persona_id),
    }


@router.get("/{persona_id}/timeline")
async def get_persona_timeline(
    persona_id: UUID,
    limit: int = Query(default=100, le=500),
) -> dict[str, Any]:
    """Get activity timeline for a persona."""
    db = await get_database()
    
    persona = await db.get_persona(persona_id)
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found",
        )
    
    # Get signals associated with this persona
    signal_ids = persona.get("signal_ids", [])
    
    timeline_events = []
    for signal_id in signal_ids[:limit]:
        signal = await db.get_signal(UUID(signal_id) if isinstance(signal_id, str) else signal_id)
        if signal:
            timeline_events.append({
                "timestamp": signal.get("discovered_at"),
                "type": signal.get("type"),
                "source": signal.get("source_name"),
                "signal_id": signal_id,
            })
    
    # Sort by timestamp
    timeline_events.sort(key=lambda x: x["timestamp"] or "", reverse=True)
    
    return {
        "persona_id": str(persona_id),
        "events": timeline_events,
        "total_activity": persona.get("activity_count", 0),
    }
