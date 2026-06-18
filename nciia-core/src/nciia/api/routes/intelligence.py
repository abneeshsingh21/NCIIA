
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Any
from datetime import datetime

from nciia.intelligence.analyst import get_analyst, IntelligenceAnalyst
# Mock Signal for demo - in real app would import from models
class MockSignal(BaseModel):
    id: str
    source_type: str
    content: str
    metadata: dict

class AnalysisRequest(BaseModel):
    case_name: str
    signals: List[dict] # Simplified for flexibility

class AnalysisResponse(BaseModel):
    report: dict[str, Any]

router = APIRouter(prefix="/intelligence", tags=["intelligence"])

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_case(
    request: AnalysisRequest,
    analyst: IntelligenceAnalyst = Depends(get_analyst)
):
    # Convert dicts to pseudo-objects for the engine
    from nciia.models import Signal
    import uuid
    
    signals = []
    for s in request.signals:
        signals.append(Signal(
            id=uuid.uuid4(),
            content=s.get("content", ""),
            source_type=s.get("source", "unknown"),
            discovered_at=datetime.now(),
            metadata=s.get("metadata", {})
        ))
        
    report = await analyst.generate_briefing(request.case_name, signals)
    return AnalysisResponse(report=report)
