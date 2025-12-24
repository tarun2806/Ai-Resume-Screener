from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
from app.services.matching_engine import AdvancedMatchingEngine

router = APIRouter()
engine = AdvancedMatchingEngine()

class MatchRequest(BaseModel):
    resume_data: Dict[str, Any]
    job_data: Dict[str, Any]

@router.post("/")
async def match_resume_to_job(request: MatchRequest):
    try:
        results = engine.calculate_match(request.resume_data, request.job_data)
        return results
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
