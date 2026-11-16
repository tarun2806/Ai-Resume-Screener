from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.nlp_processor import AdvancedNLPProcessor
from app.utils.parser import extract_text
from app.utils.uploads import read_and_validate, UploadValidationError

router = APIRouter()
processor = AdvancedNLPProcessor()


@router.post("/parse")
async def parse_resume(file: UploadFile = File(...)):
    try:
        content = await read_and_validate(file)
    except UploadValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        text = extract_text(content, file.filename or "")
        if not text or len(text.strip()) < 50:
            raise HTTPException(
                status_code=400,
                detail="Could not extract enough text from the resume file",
            )
        return processor.process_resume(text)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to parse resume file")
