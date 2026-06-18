"""API routes for the streaming LLM analyst (ARIA) and hunter agents."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from nciia.intelligence.analyst_llm import (
    stream_analyst_response,
    generate_report,
    new_session,
    get_session,
)
from nciia.hunter.autonomous import get_hunter_manager
from nciia.osint.username_enum import get_enumerator
from nciia.utils import get_logger

router = APIRouter()
logger = get_logger(__name__)


# ─── Analyst (ARIA) ───────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    session_id: str | None = None


class ReportRequest(BaseModel):
    report_type: str       # threat_intel | persona_profile | incident
    target_id: str
    target_type: str       # persona | case | ioc


@router.post("/session/new")
async def create_session() -> dict[str, str]:
    """Create a new analyst session."""
    sid = new_session()
    return {"session_id": sid}


@router.post("/query")
async def query_analyst(req: QueryRequest):
    """
    Stream ARIA's response via SSE.
    Client should consume as text/event-stream.
    """
    session_id = req.session_id or new_session()

    async def event_stream():
        try:
            async for chunk in stream_analyst_response(req.question, session_id):
                yield chunk
        except Exception as exc:
            yield f'data: {{"error": "{str(exc)}"}}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/session/{session_id}/history")
async def get_history(session_id: str) -> dict[str, Any]:
    """Return conversation history for a session."""
    session = get_session(session_id)
    return {
        "session_id": session_id,
        "turns": len(session.history) // 2,
        "history": session.history,
    }


@router.post("/report")
async def generate_intelligence_report(req: ReportRequest) -> dict[str, str]:
    """Generate a complete structured intelligence report (non-streaming)."""
    try:
        report = await generate_report(req.report_type, req.target_id, req.target_type)
        return {"report": report, "format": "markdown"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Hunter Agents ────────────────────────────────────────────────────────────

@router.get("/hunters/stats")
async def hunter_stats() -> list[dict]:
    """Get status and stats for all hunter agents."""
    manager = get_hunter_manager()
    return manager.get_all_stats()


@router.get("/hunters/findings")
async def hunter_findings(limit: int = 50) -> dict[str, Any]:
    """Get recent findings from all hunter agents."""
    manager = get_hunter_manager()
    findings = manager.get_all_findings()
    return {
        "total": len(findings),
        "findings": findings[:limit],
    }


@router.post("/hunters/start")
async def start_hunters() -> dict[str, str]:
    """Start all hunter agents."""
    manager = get_hunter_manager()
    await manager.start_all()
    return {"status": "started"}


@router.post("/hunters/stop")
async def stop_hunters() -> dict[str, str]:
    """Stop all hunter agents."""
    manager = get_hunter_manager()
    await manager.stop_all()
    return {"status": "stopped"}


# ─── Username Enumeration ─────────────────────────────────────────────────────

class EnumRequest(BaseModel):
    query: str    # username or email


@router.post("/enumerate")
async def enumerate_identity(req: EnumRequest) -> dict[str, Any]:
    """
    Enumerate a username or email across 100+ platforms.
    Returns all platforms where the identity was found.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    enumerator = get_enumerator()
    report = await enumerator.enumerate(req.query.strip())
    return report.to_dict()
