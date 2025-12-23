from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.services.nlp_processor import AdvancedNLPProcessor

router = APIRouter()
processor = AdvancedNLPProcessor()

class JobRequest(BaseModel):
    description: str

@router.post("/analyze")
async def analyze_job(job: JobRequest):
    if len(job.description) < 50:
        raise HTTPException(status_code=400, detail="Job description too short (min 50 chars)")
    
    try:
        result = processor.process_jd(job.description)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
