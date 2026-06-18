"""
AI Assistant API Endpoints
Restricted LLM integration for reasoning and explanation.
"""

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from nciia.utils import get_logger, get_audit_logger

router = APIRouter()
logger = get_logger(__name__)
audit = get_audit_logger()


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    context_persona_id: Optional[UUID] = None
    context_case_id: Optional[UUID] = None


class ExplainRequest(BaseModel):
    finding_type: str  # threat_score, persona, signal, etc.
    finding_id: UUID
    detail_level: str = "standard"  # brief, standard, detailed


@router.post("/query")
async def query_assistant(request: QueryRequest) -> dict[str, Any]:
    """
    Query the AI assistant about investigation findings.
    LLM only reasons over verified outputs - never invents data.
    """
    # NOTE: This is a placeholder. Full LLM integration in Phase 6.
    return {
        "status": "pending",
        "message": "LLM integration not yet implemented. Coming in Phase 6.",
        "question": request.question,
    }


@router.post("/explain")
async def explain_finding(request: ExplainRequest) -> dict[str, Any]:
    """
    Get AI explanation of a specific finding.
    """
    return {
        "status": "pending",
        "message": "Explain functionality coming in Phase 6.",
        "finding_type": request.finding_type,
        "finding_id": str(request.finding_id),
    }


@router.post("/summarize/{case_id}")
async def summarize_case(case_id: UUID) -> dict[str, Any]:
    """
    Generate AI summary of a case investigation.
    """
    return {
        "status": "pending",
        "message": "Case summarization coming in Phase 6.",
        "case_id": str(case_id),
    }
