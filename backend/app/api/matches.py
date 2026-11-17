from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel
from typing import Dict, Any

from app.services.analysis import run_analysis
from app.services.semantic_matcher import SemanticMatcher
from app.services.career_assistant import CareerAssistant
from app.services.nlp_processor import AdvancedNLPProcessor
from app.utils.parser import extract_text
from app.utils.uploads import read_and_validate, UploadValidationError, ensure_uploads_enabled
from app.ratelimit import limiter

router = APIRouter()
matcher = SemanticMatcher()
assistant = CareerAssistant()
processor = AdvancedNLPProcessor()


class MatchRequest(BaseModel):
    resume_data: Dict[str, Any]
    job_data: Dict[str, Any]


@router.post("/")
async def calculate_match(request: MatchRequest):
    """
    Score a match from already-parsed resume/job payloads.
    """
    try:
        resume_info = {
            "name": request.resume_data.get("name", "Candidate"),
            "raw_text": request.resume_data.get("raw_text", ""),
            "skills": request.resume_data.get("skills_detected", []),
            "experience_years": request.resume_data.get("expert_data", {})
            .get("experience", {})
            .get("total_years"),
        }
        jd_info = {
            "raw_text": request.job_data.get("raw_text", ""),
            "required_skills": request.job_data.get("all_skills_flat", []),
            "min_years_experience": request.job_data.get("min_years_experience") or 0,
        }
        match_result = matcher.score_candidate(resume_info, jd_info)

        feedback = assistant.generate_feedback(
            resume_data=request.resume_data,
            jd_data=request.job_data,
            current_score=match_result["final_score"],
        )

        score = match_result["final_score"]
        verdict = (
            "Excellent Match" if score >= 85
            else "Strong Growth Potential" if score >= 70
            else "Good Foundational Match" if score >= 50
            else "Needs Improvement"
        )

        res_canon = {s.lower() for s in resume_info["skills"]}
        matched_explicit = [
            s for s in jd_info["required_skills"] if s.lower() in res_canon
        ]

        return {
            "overall_score": score,
            "breakdown": {
                "skill_match": match_result["breakdown"]["skill_overlap"],
                "experience_relevance": match_result["breakdown"]["experience_fit"],
                "semantic_alignment": match_result["breakdown"]["semantic_similarity"],
                "resume_quality": 100.0,
            },
            "explanation": f"Match computed deterministically. Verdict: {verdict}.",
            "verdict": verdict,
            "suggestions": [
                {"tip": p["suggestion"], "impact": p["estimated_score_increase"]}
                for p in feedback["improvement_plan"][:4]
            ],
            "categorized_skills": request.job_data.get(
                "categorized_skills", {"domain": [], "tools": [], "soft": []}
            ),
            "matched_skills": matched_explicit,
            "partial_matches": [],
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to compute match")


@router.post("/analyze")
@limiter.limit("30/minute")
async def unified_analyze_endpoint(
    request: Request,
    file: UploadFile = File(...),
    job_description: str = Form(...),
):
    """
    Unified pipeline: upload resume + paste JD -> full analysis in one call.
    """
    ensure_uploads_enabled()
    if len(job_description) < 50:
        raise HTTPException(status_code=400, detail="Job description too short (min 50 chars)")

    try:
        content = await read_and_validate(file)
    except UploadValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        resume_text = extract_text(content, file.filename or "")
        if not resume_text or len(resume_text.strip()) < 50:
            raise HTTPException(
                status_code=400,
                detail="Could not extract enough text from the resume file",
            )
        return run_analysis(resume_text, job_description)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to parse resume file")
