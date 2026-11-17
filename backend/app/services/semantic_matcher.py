import math
import re
from typing import Dict, Any, List, Optional

from app.ml.skill_vocabulary import canonical_skill
from app.ml.ontology import related_skills_for


def _text_cosine(text1: str, text2: str) -> float:
    """
    Deterministic semantic similarity via TF-IDF cosine.
    Falls back to normalized token Jaccard if sklearn is unavailable.
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        vectorizer = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            stop_words="english",
            max_features=5000,
        )
        matrix = vectorizer.fit_transform([text1, text2])
        sim = cosine_similarity(matrix[0], matrix[1])[0][0]
        return float(max(0.0, min(1.0, sim)))
    except Exception:
        words1 = set(re.findall(r"\w+", text1.lower()))
        words2 = set(re.findall(r"\w+", text2.lower()))
        if not words1 or not words2:
            return 0.0
        return len(words1 & words2) / len(words1 | words2)


class SemanticMatcher:
    """
    Deterministic, explainable matcher.

    Score components (weights configurable, default sum to 1.0):
      - skill_overlap        0.35  canonical skill coverage of JD requirements
      - preferred_match      0.05  coverage of JD "preferred/nice-to-have" skills
      - semantic_similarity  0.30  TF-IDF cosine between resume and JD text
      - experience_fit       0.15  years-of-experience vs requirement
      - education_fit        0.15  degree/qualification requirement vs resume

    No randomness, no fabricated values: unknown experience yields a
    neutral 0.5 component rather than an invented number.
    """

    def __init__(self, model_name: Optional[str] = None, weights: Optional[Dict[str, float]] = None):
        from app.config import get_scoring_weights

        self.weights = weights or get_scoring_weights()

    @staticmethod
    def _canon_set(skills: List[str]) -> set:
        out = set()
        for s in skills:
            c = canonical_skill(s) or s.lower().strip()
            out.add(c.lower())
        return out

    @staticmethod
    def _has_related_skill(jd_skill: str, res_skills: set) -> bool:
        """True if the resume contains a skill related to the JD skill.

        Uses the merged ontology + taxonomy relation graph. Related skills
        earn only partial credit (0.4) — they are NOT treated as equivalent
        qualifications.
        """
        related = related_skills_for(jd_skill)
        if {r.lower() for r in related} & res_skills:
            return True
        # reverse direction: resume skill declares the JD skill as related
        for rs in res_skills:
            if jd_skill.lower() in related_skills_for(rs):
                return True
        return False

    def score_candidate(
        self,
        resume_data: Dict[str, Any],
        jd_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        res_text = resume_data.get("raw_text", "") or ""
        jd_text = jd_data.get("raw_text", "") or ""

        # 1. Semantic similarity (deterministic TF-IDF cosine)
        semantic_sim = _text_cosine(res_text, jd_text)

        # 2. Skill overlap on canonical skill names.
        # Only EXPLICIT JD requirements count toward the denominator;
        # inferred/related JD skills are not treated as hard requirements.
        res_skills = self._canon_set(resume_data.get("skills", []))
        jd_skills_raw = jd_data.get("required_skills", []) or []
        jd_skills = self._canon_set(jd_skills_raw)

        if jd_skills:
            earned = 0.0
            for s in jd_skills:
                if s in res_skills:
                    earned += 1.0
                elif self._has_related_skill(s, res_skills):
                    earned += 0.4  # partial credit for ontology-related skill
            skill_overlap = earned / len(jd_skills)
        else:
            skill_overlap = 0.5  # neutral when JD yields no extractable skills

        # 2b. Preferred-skill coverage ("nice to have" / "preferred" section).
        # Neutral rule: when the JD lists no preferred skills, this component
        # mirrors required-skill coverage so it neither rewards nor penalizes.
        pref_raw = jd_data.get("preferred_skills") or []
        pref_skills = self._canon_set(pref_raw)
        if pref_skills:
            earned = 0.0
            for s in pref_skills:
                if s in res_skills:
                    earned += 1.0
                elif self._has_related_skill(s, res_skills):
                    earned += 0.4
            preferred_match = earned / len(pref_skills)
        else:
            preferred_match = skill_overlap

        # 3. Experience fit
        actual_exp = resume_data.get("experience_years")
        required_exp = jd_data.get("min_years_experience") or 0
        if actual_exp is None:
            exp_fit = 0.5  # unknown -> neutral, disclosed in breakdown
        elif required_exp and required_exp > 0:
            exp_fit = 1.0 if actual_exp >= required_exp else max(0.0, actual_exp / required_exp)
        else:
            exp_fit = 1.0

        # 4. Education / qualification fit.
        # required_degree comes from JD parsing ("bachelor"/"master"/"phd"/None).
        # Neutral rule: no degree requirement in JD -> 1.0 (no penalty).
        required_degree = (jd_data.get("required_degree") or "").lower().strip()
        edu_text = (resume_data.get("education_text") or "").lower()
        if not required_degree:
            education_fit = 1.0
        elif not edu_text:
            education_fit = 0.0  # required but nothing found in resume
        elif required_degree in edu_text or "phd" in edu_text or "doctorate" in edu_text:
            education_fit = 1.0
        elif required_degree == "master" and "bachelor" in edu_text:
            education_fit = 0.5  # bachelor's does not satisfy a master's req
        else:
            education_fit = 0.7

        w = self.weights
        final_score = (
            skill_overlap * w.get("skill_overlap", 0.35)
            + preferred_match * w.get("preferred_match", 0.05)
            + semantic_sim * w.get("semantic_similarity", 0.30)
            + exp_fit * w.get("experience_fit", 0.15)
            + education_fit * w.get("education_fit", 0.15)
        ) * 100

        return {
            "candidate_name": resume_data.get("name", "Unknown"),
            "final_score": round(final_score, 2),
            "breakdown": {
                "skill_overlap": round(skill_overlap * 100, 2),
                "preferred_match": round(preferred_match * 100, 2),
                "semantic_similarity": round(semantic_sim * 100, 2),
                "experience_fit": round(exp_fit * 100, 2),
                "education_fit": round(education_fit * 100, 2),
            },
        }

    def rank_candidates(
        self, candidates: List[Dict[str, Any]], jd_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        results = [self.score_candidate(c, jd_data) for c in candidates]
        return sorted(results, key=lambda x: x["final_score"], reverse=True)
