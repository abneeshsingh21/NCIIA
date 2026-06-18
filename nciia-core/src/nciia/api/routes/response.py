
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Any
from pydantic import BaseModel

from nciia.response.engine import get_response_engine, ResponseEngine, ResponseActionType

router = APIRouter(prefix="/response", tags=["response"])

class ActionRequest(BaseModel):
    case_id: str
    action_type: str
    target: str
    details: dict[str, Any] = {}

class ActionResponse(BaseModel):
    id: str
    status: str
    metadata: dict[str, Any]

@router.post("/execute", response_model=ActionResponse)
async def execute_countermeasure(
    request: ActionRequest,
    engine: ResponseEngine = Depends(get_response_engine)
):
    try:
        # Validate action type
        valid_types = [t.value for t in ResponseActionType]
        if request.action_type not in valid_types:
            raise HTTPException(status_code=400, detail=f"Invalid action type. Must be one of {valid_types}")
            
        action = await engine.execute_action(
            request.case_id,
            request.action_type,
            request.target,
            request.details
        )
        
        return ActionResponse(
            id=action.id,
            status=action.status,
            metadata=action.metadata
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{case_id}")
async def get_action_history(
    case_id: str,
    engine: ResponseEngine = Depends(get_response_engine)
):
    actions = await engine.get_actions(case_id)
    return actions
