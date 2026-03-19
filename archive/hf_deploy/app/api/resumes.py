from fastapi import APIRouter, UploadFile, File, HTTPException
from app.utils.parser import extract_text
from app.services.nlp_processor import AdvancedNLPProcessor
from typing import Dict, Any

router = APIRouter()
processor = AdvancedNLPProcessor()

@router.post("/parse")
async def parse_resume(file: UploadFile = File(...)):
    try:
        content = await file.read()
        text = extract_text(content, file.filename)
        result = processor.process_resume(text)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
