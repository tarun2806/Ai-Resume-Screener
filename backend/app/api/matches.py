from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from pydantic import BaseModel
from typing import Dict, Any, List
from app.services.semantic_matcher import SemanticMatcher
from app.services.career_assistant import CareerAssistant
from app.services.nlp_processor import AdvancedNLPProcessor
import json

router = APIRouter()
matcher = SemanticMatcher()
assistant = CareerAssistant()

class MatchRequest(BaseModel):
    resume_data: Dict[str, Any]
    job_data: Dict[str, Any]

@router.post("/")
async def calculate_match(request: MatchRequest):
    """
    Main matching endpoint called by the frontend.
    Computes a deep semantic match between parsed resume and job data.
    """
    try:
        # 1. Use SemanticMatcher (already built with expert mocks if env lacked ML)
        # Prepare data for SemanticMatcher
        resume_info = {
            "name": request.resume_data.get("name", "Candidate"),
            "raw_text": request.resume_data.get("raw_text", ""),
            "skills": request.resume_data.get("skills_detected", []),
            "experience_years": request.resume_data.get("expert_data", {}).get("experience", {}).get("total_years", 5)
        }
        
        jd_info = {
            "raw_text": request.job_data.get("raw_text", ""),
            "required_skills": request.job_data.get("all_skills_flat", []),
            "min_years_experience": 0
        }
        
        # 2. Score Match
        match_result = matcher.score_candidate(resume_info, jd_info)
        
        # 3. Generate Feedback/Suggestions
        feedback = assistant.generate_feedback(
            resume_data=request.resume_data,
            jd_data=request.job_data,
            current_score=match_result["final_score"]
        )
        
        # 4. Map to Frontend's expected structure
        # The frontend expects these exact keys:
        # overall_score, breakdown, explanation, verdict, suggestions,
        # categorized_skills, matched_skills, partial_matches
        
        # Heuristic for verdict
        score = match_result["final_score"]
        if score >= 85: verdict = "Excellent Match"
        elif score >= 70: verdict = "Strong Growth Potential"
        elif score >= 50: verdict = "Good Foundational Match"
        else: verdict = "Needs Improvement"
        
        # Heuristic for explanation
        if score >= 75: 
            explanation = "Your skills are well-aligned with the core requirements of this role."
        elif score >= 50:
            explanation = "You have a solid base, but some key technical gaps were identified."
        else:
            explanation = "Major skill gaps detected. Consider following the AI suggestions below."

        # Map suggestions to frontend tip/impact format
        fe_suggestions = []
        for plan_item in feedback["improvement_plan"][:4]:
            fe_suggestions.append({
                "tip": plan_item["suggestion"],
                "impact": plan_item["estimated_score_increase"]
            })
            
        # Ensure categorized_skills is present (already in jd_data)
        cat_skills = request.job_data.get("categorized_skills", {"domain": [], "tools": [], "soft": []})
        
        # Matched/Partial skills (using set logic for quick lookup)
        res_skills_set = set(s.lower() for s in resume_info["skills"])
        # We also need 'partial_matches' for the UI 'Sparkles' icon
        # For demo, let's treat anything that is in both as 'matched' 
        # and anything semantically similar as 'partial'.
        matched = list(res_skills_set.intersection(set(s.lower() for s in jd_info["required_skills"])))
        # Map back to original name for UI
        matched_explicit = [s for s in jd_info["required_skills"] if s.lower() in res_skills_set]
        
        return {
            "overall_score": score,
            "breakdown": {
                "skill_match": match_result["breakdown"]["skill_overlap"],
                "experience_relevance": match_result["breakdown"]["experience_fit"],
                "semantic_alignment": match_result["breakdown"]["semantic_similarity"],
                "resume_quality": 100.0 # Default point for formatting
            },
            "explanation": explanation,
            "verdict": verdict,
            "suggestions": fe_suggestions,
            "categorized_skills": cat_skills,
            "matched_skills": matched_explicit,
            "partial_matches": [] # Can be populated by semantic fuzzy check if needed
        }
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze")
async def unified_analyze_endpoint(
    file: UploadFile = File(...),
    job_description: str = Form(...)
):
    """
    Expert Orchestrator: Combines parsing, JD analysis, and matching in one call.
    Dramatically reduces network overhead and latency.
    """
    try:
        # 1. Initialize Processor
        processor = AdvancedNLPProcessor()
        
        # 2. Extract Text (Corrected: Passing bytes & filename)
        from app.utils.parser import extract_text
        
        file_bytes = await file.read()
        resume_text = extract_text(file_bytes, file.filename)
                
        # 3. Process Concurrently (Logic reuse)
        resume_data = processor.process_resume(resume_text)
        job_data = processor.process_jd(job_description)
        
        # 4. Score & Feedback
        match_result = matcher.score_candidate({
            "name": resume_data.get("name", "Candidate"),
            "raw_text": resume_data.get("raw_text", ""),
            "skills": resume_data.get("skills_detected", []),
            "experience_years": resume_data.get("expert_data", {}).get("experience", {}).get("total_years", 5)
        }, {
            "raw_text": job_data.get("raw_text", ""),
            "required_skills": job_data.get("all_skills_flat", []),
            "min_years_experience": 0
        })
        
        feedback = assistant.generate_feedback(
            resume_data=resume_data,
            jd_data=job_data,
            current_score=match_result["final_score"]
        )
        
        # 5. Map to Response (Same structure as root endpoint)
        fe_suggestions = [{"tip": p["suggestion"], "impact": p["estimated_score_increase"]} for p in feedback["improvement_plan"][:4]]
        
        score = match_result["final_score"]
        verdict = "Excellent Match" if score >= 85 else "Strong Growth Potential" if score >= 70 else "Good Foundational Match" if score >= 50 else "Needs Improvement"
        
        res_skills_set = set(s.lower() for s in resume_data.get("skills_detected", []))
        matched_explicit = [s for s in job_data.get("all_skills_flat", []) if s.lower() in res_skills_set]

        return {
            "overall_score": score,
            "breakdown": {
                "skill_match": match_result["breakdown"]["skill_overlap"],
                "experience_relevance": match_result["breakdown"]["experience_fit"],
                "semantic_alignment": match_result["breakdown"]["semantic_similarity"],
                "resume_quality": 100.0
            },
            "explanation": "High-Speed Analysis completed using AI ScreenX Unified Engine.",
            "verdict": verdict,
            "suggestions": fe_suggestions,
            "categorized_skills": job_data.get("categorized_skills", {}),
            "matched_skills": matched_explicit,
            "partial_matches": []
        }
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
