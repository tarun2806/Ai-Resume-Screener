import math
import re
from typing import Dict, Any, List, Optional

from app.ml.skill_vocabulary import canonical_skill
from app.ml.ontology import SKILL_ONTOLOGY


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

    Score components (weights sum to 1.0):
      - skill_overlap      0.45  canonical skill coverage of JD requirements
      - semantic_similarity 0.35 TF-IDF cosine between resume and JD text
      - experience_fit     0.20  years-of-experience vs requirement

    No randomness, no fabricated values: unknown experience yields a
    neutral 0.5 component rather than an invented number.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.weights = {
            "semantic_similarity": 0.35,
            "skill_overlap": 0.45,
            "experience_fit": 0.20,
        }

    @staticmethod
    def _canon_set(skills: List[str]) -> set:
        out = set()
        for s in skills:
            c = canonical_skill(s) or s.lower().strip()
            out.add(c.lower())
        return out

    @staticmethod
    def _has_related_skill(jd_skill: str, res_skills: set) -> bool:
        """True if the resume contains a skill ontology-related to the JD skill."""
        entry = SKILL_ONTOLOGY.get(jd_skill.lower()) or SKILL_ONTOLOGY.get(jd_skill)
        if entry:
            related = {r.lower() for r in entry.get("related", {})}
            if related & res_skills:
                return True
        # reverse direction: resume skill declares the JD skill as related
        for rs in res_skills:
            re_entry = SKILL_ONTOLOGY.get(rs)
            if re_entry and jd_skill.lower() in {r.lower() for r in re_entry.get("related", {})}:
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

        # 3. Experience fit
        actual_exp = resume_data.get("experience_years")
        required_exp = jd_data.get("min_years_experience") or 0
        if actual_exp is None:
            exp_fit = 0.5  # unknown -> neutral, disclosed in breakdown
        elif required_exp and required_exp > 0:
            exp_fit = 1.0 if actual_exp >= required_exp else max(0.0, actual_exp / required_exp)
        else:
            exp_fit = 1.0

        final_score = (
            semantic_sim * self.weights["semantic_similarity"]
            + skill_overlap * self.weights["skill_overlap"]
            + exp_fit * self.weights["experience_fit"]
        ) * 100

        return {
            "candidate_name": resume_data.get("name", "Unknown"),
            "final_score": round(final_score, 2),
            "breakdown": {
                "semantic_similarity": round(semantic_sim * 100, 2),
                "skill_overlap": round(skill_overlap * 100, 2),
                "experience_fit": round(exp_fit * 100, 2),
            },
        }

    def rank_candidates(
        self, candidates: List[Dict[str, Any]], jd_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        results = [self.score_candidate(c, jd_data) for c in candidates]
        return sorted(results, key=lambda x: x["final_score"], reverse=True)
