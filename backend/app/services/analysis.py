import re
from typing import Any, Dict, Optional

from app.services.nlp_processor import AdvancedNLPProcessor
from app.services.semantic_matcher import SemanticMatcher
from app.services.career_assistant import CareerAssistant
from app.ml.skill_vocabulary import canonical_skill

_processor = AdvancedNLPProcessor()
_matcher = SemanticMatcher()
_assistant = CareerAssistant()


def extract_min_years(jd_text: str) -> Optional[float]:
    """Best-effort extraction of required years of experience from JD text."""
    patterns = [
        r"(\d{1,2})\s*\+?\s*(?:or more\s+)?years?\s+(?:of\s+)?(?:relevant\s+)?experience",
        r"(?:minimum|min\.?|at least)\s+(\d{1,2})\s*\+?\s*years?",
        r"(\d{1,2})\s*\+?\s*years?\s+experience",
    ]
    for pat in patterns:
        m = re.search(pat, jd_text, re.I)
        if m:
            return float(m.group(1))
    return None


def run_analysis(resume_text: str, jd_text: str) -> Dict[str, Any]:
    """
    Full pipeline: parse resume -> parse JD -> match -> explain.
    Returns the response shape consumed by the frontend plus internal
    fields (parsed profile, missing skills) for ATS storage.
    """
    resume_data = _processor.process_resume(resume_text)
    job_data = _processor.process_jd(jd_text)

    resume_exp = resume_data.get("expert_data", {}).get("experience", {}).get("total_years")

    match_result = _matcher.score_candidate(
        {
            "name": resume_data.get("name", "Candidate"),
            "raw_text": resume_data.get("raw_text", ""),
            "skills": resume_data.get("skills_detected", []),
            "experience_years": resume_exp,
        },
        {
            "raw_text": job_data.get("raw_text", ""),
            "required_skills": job_data.get("explicit_skills", [])
            or job_data.get("all_skills_flat", []),
            "min_years_experience": extract_min_years(jd_text) or 0,
        },
    )

    feedback = _assistant.generate_feedback(
        resume_data=resume_data,
        jd_data=job_data,
        current_score=match_result["final_score"],
    )

    score = match_result["final_score"]
    if score >= 85:
        verdict = "Excellent Match"
    elif score >= 70:
        verdict = "Strong Growth Potential"
    elif score >= 50:
        verdict = "Good Foundational Match"
    else:
        verdict = "Needs Improvement"

    if score >= 75:
        explanation = (
            "Your skills are well-aligned with the core requirements of this role."
        )
    elif score >= 50:
        explanation = (
            "You have a solid base, but some key technical gaps were identified."
        )
    else:
        explanation = (
            "Major skill gaps detected. Consider following the AI suggestions below."
        )

    fe_suggestions = [
        {"tip": p["suggestion"], "impact": p["estimated_score_increase"]}
        for p in feedback["improvement_plan"][:4]
    ]

    res_canon = {
        (canonical_skill(s) or s).lower() for s in resume_data.get("skills_detected", [])
    }
    jd_skills = job_data.get("explicit_skills") or job_data.get("all_skills_flat", [])
    matched_explicit = [
        s for s in jd_skills if s.lower() in res_canon or (canonical_skill(s) or "").lower() in res_canon
    ]
    missing = [s for s in jd_skills if s not in matched_explicit]

    # Confidence: based on how much signal we actually extracted
    signals = sum([
        bool(resume_data.get("email")),
        bool(resume_data.get("skills_detected")),
        resume_exp is not None,
        len(resume_text.split()) >= 100,
    ])
    confidence = round(signals / 4 * 100, 1)

    return {
        "overall_score": score,
        "breakdown": {
            "skill_match": match_result["breakdown"]["skill_overlap"],
            "experience_relevance": match_result["breakdown"]["experience_fit"],
            "semantic_alignment": match_result["breakdown"]["semantic_similarity"],
            "resume_quality": 100.0,
        },
        "explanation": explanation,
        "verdict": verdict,
        "suggestions": fe_suggestions,
        "categorized_skills": job_data.get("categorized_skills", {"domain": [], "tools": [], "soft": []}),
        "matched_skills": matched_explicit,
        "missing_skills": missing[:20],
        "partial_matches": [],
        "confidence": confidence,
        "candidate": {
            "name": resume_data.get("name"),
            "email": resume_data.get("email"),
            "skills": resume_data.get("skills_detected", []),
            "experience_years": resume_exp,
            "education": resume_data.get("education") or None,
        },
        "required_years": extract_min_years(jd_text),
        "ai_reasoning": [
            "Skill overlap measured on canonical skill names extracted from both documents.",
            "Semantic alignment uses TF-IDF cosine similarity between resume and job description text.",
            "Experience fit compares detected years of experience against the stated requirement.",
        ],
    }
