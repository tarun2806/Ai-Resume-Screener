import re
from typing import Any, Dict, List, Optional

from app.services.nlp_processor import AdvancedNLPProcessor
from app.services.semantic_matcher import SemanticMatcher
from app.services.career_assistant import CareerAssistant
from app.ml.skill_vocabulary import canonical_skill, find_skills_in_text, CANONICAL_TO_ALIASES
from app.config import get_scoring_weights

_processor = AdvancedNLPProcessor()
_matcher = SemanticMatcher()
_assistant = CareerAssistant()

_PREFERRED_MARKER = re.compile(
    r"(preferred qualifications?|nice[- ]to[- ]have|bonus(?: points?)?|plus:|"
    r"desired qualifications?|would be a plus|additional (?:skills|qualifications))",
    re.I,
)
_DEGREE_REQ = re.compile(
    r"(ph\.?d\.?|doctorate|master'?s?|mba|bachelor'?s?|b\.?s\.?|b\.?a\.?|"
    r"bachelor of|master of|degree in|degree required)",
    re.I,
)


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


def extract_preferred_skills(jd_text: str) -> List[str]:
    """
    Extract canonical skills mentioned in the JD's preferred/nice-to-have
    section. Returns [] when no preferred section exists.
    """
    m = _PREFERRED_MARKER.search(jd_text)
    if not m:
        return []
    section = jd_text[m.end(): m.end() + 1200]
    # Stop at the next major heading so we don't bleed into other sections
    next_head = re.search(r"\n\s*(?:requirements|responsibilities|qualifications|about|who we are|what you.ll do)", section, re.I)
    if next_head:
        section = section[: next_head.start()]
    skills = find_skills_in_text(section)
    return [s["name"] for s in skills][:15]


def extract_required_degree(jd_text: str) -> Optional[str]:
    """
    Best-effort detection of a degree requirement in the JD.
    Returns 'phd' | 'master' | 'bachelor' | None.
    """
    m = _DEGREE_REQ.search(jd_text)
    if not m:
        return None
    token = m.group(1).lower().replace(".", "")
    if "phd" in token or "doctorate" in token:
        return "phd"
    if "master" in token or "mba" in token:
        return "master"
    return "bachelor"


def _evidence_for_skill(skill: str, raw_text: str) -> Optional[str]:
    """Return the first resume line/snippet evidencing a canonical skill."""
    aliases = CANONICAL_TO_ALIASES.get(skill) or [skill]
    lowered_lines = raw_text.splitlines()
    for alias in aliases:
        pattern = r"(?<![\w+#.-])" + re.escape(alias.lower()) + r"(?![\w+#.-])"
        for line in lowered_lines:
            if re.search(pattern, line.lower()):
                snippet = line.strip()
                if len(snippet) > 160:
                    snippet = snippet[:157] + "..."
                return snippet
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

    preferred_skills = extract_preferred_skills(jd_text)
    required_degree = extract_required_degree(jd_text)
    resume_edu_text = " ".join(
        str(e) for e in (resume_data.get("education") or [])
    ) or ""

    match_result = _matcher.score_candidate(
        {
            "name": resume_data.get("name", "Candidate"),
            "raw_text": resume_data.get("raw_text", ""),
            "skills": resume_data.get("skills_detected", []),
            "experience_years": resume_exp,
            "education_text": resume_edu_text,
        },
        {
            "raw_text": job_data.get("raw_text", ""),
            "required_skills": job_data.get("explicit_skills", [])
            or job_data.get("all_skills_flat", []),
            "preferred_skills": preferred_skills,
            "required_degree": required_degree,
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

    # Preferred-skill coverage (informational; also feeds score component)
    pref_matched = [s for s in preferred_skills
                    if s.lower() in res_canon or (canonical_skill(s) or "").lower() in res_canon]

    # Evidence snippets for matched required skills (no fabrication: only
    # lines actually present in the resume text)
    raw_resume = resume_data.get("raw_text", "")
    evidence = [
        {"skill": s, "snippet": _evidence_for_skill(s, raw_resume)}
        for s in matched_explicit[:12]
    ]

    # Extraction limitations — disclosed to recruiters, never hidden
    limitations = []
    if len(raw_resume.split()) < 100:
        limitations.append("Very short resume text — extraction confidence is limited.")
    if resume_exp is None:
        limitations.append("No date ranges detected; experience could not be estimated.")
    if not resume_data.get("skills_detected"):
        limitations.append("No skills detected in resume text.")
    limitations.append("Skills are matched by canonical name/alias; equivalent-but-differently-named skills may be undercounted.")
    limitations.append("Score is a screening aid only — it does not reject candidates automatically.")

    # Confidence: based on how much signal we actually extracted
    signals = sum([
        bool(resume_data.get("email")),
        bool(resume_data.get("skills_detected")),
        resume_exp is not None,
        len(resume_text.split()) >= 100,
    ])
    confidence = round(signals / 4 * 100, 1)

    weights = get_scoring_weights()
    comp = match_result["breakdown"]
    score_breakdown = [
        {"component": "Required skills", "key": "skill_overlap",
         "score": comp["skill_overlap"], "weight": weights["skill_overlap"]},
        {"component": "Preferred skills", "key": "preferred_match",
         "score": comp["preferred_match"], "weight": weights["preferred_match"]},
        {"component": "Semantic relevance", "key": "semantic_similarity",
         "score": comp["semantic_similarity"], "weight": weights["semantic_similarity"]},
        {"component": "Experience fit", "key": "experience_fit",
         "score": comp["experience_fit"], "weight": weights["experience_fit"]},
        {"component": "Education / qualifications", "key": "education_fit",
         "score": comp["education_fit"], "weight": weights["education_fit"]},
    ]

    return {
        "overall_score": score,
        "overall_match": score,
        "breakdown": {
            "skill_match": comp["skill_overlap"],
            "preferred_match": comp["preferred_match"],
            "experience_relevance": comp["experience_fit"],
            "semantic_alignment": comp["semantic_similarity"],
            "education_fit": comp["education_fit"],
            "resume_quality": 100.0,
        },
        "score_breakdown": score_breakdown,
        "scoring_weights": weights,
        "preferred_skills": preferred_skills,
        "preferred_skills_matched": pref_matched,
        "explanation": explanation,
        "verdict": verdict,
        "suggestions": fe_suggestions,
        "categorized_skills": job_data.get("categorized_skills", {"domain": [], "tools": [], "soft": []}),
        "matched_skills": matched_explicit,
        "missing_skills": missing[:20],
        "partial_matches": [],
        "confidence": confidence,
        "evidence": evidence,
        "extraction_limitations": limitations,
        "required_degree": required_degree,
        "candidate": {
            "name": resume_data.get("name"),
            "email": resume_data.get("email"),
            "skills": resume_data.get("skills_detected", []),
            "experience_years": resume_exp,
            "education": resume_data.get("education") or None,
        },
        "required_years": extract_min_years(jd_text),
        "ai_reasoning": [
            "Score = 100 * sum(component_score * weight) over: required skills, preferred skills, semantic relevance, experience fit, education fit.",
            "Skill overlap measured on canonical skill names; ontology-related skills earn 0.4 partial credit (never full equivalence).",
            "Semantic relevance uses TF-IDF cosine similarity between resume and job description text.",
            "Experience fit compares detected years of experience against the stated requirement.",
            "Scores are screening aids for recruiter review — no candidate is auto-rejected.",
        ],
    }
