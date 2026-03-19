from typing import List, Dict, Any
import re
import random

class SemanticMatcher:
    """
    Expert Semantic Job Matching Engine (Mocked version using text-overlap for SpaCy/Torch-incompatible systems).
    """
    def __init__(self, model_name: str = None):
        # We ignore nlp_model here as we're using mock similarity
        pass
        self.weights = {
            "semantic_similarity": 0.4,
            "skill_overlap": 0.4,
            "experience_fit": 0.2
        }

    def score_candidate(self, resume_data: Dict[str, Any], jd_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates match using weighted Jaccard similarity and randomization for demo.
        """
        # 1. Mock Semantic Similarity (based on term overlap + jitter)
        res_text = resume_data.get("raw_text", "").lower()
        jd_text = jd_data.get("raw_text", "").lower()
        
        # Word set overlap (Jaccard-ish)
        res_words = set(re.findall(r'\w+', res_text))
        jd_words = set(re.findall(r'\w+', jd_text))
        intersection = res_words.intersection(jd_words)
        union = res_words.union(jd_words)
        
        base_sim = len(intersection) / len(union) if union else 0.5
        semantic_sim = min(base_sim * 2.5 + random.uniform(0.1, 0.3), 1.0) # Boost and add jitter
        
        # 2. Skill Overlap Score (Based on parsed skills)
        res_skills = set(s.lower() for s in resume_data.get("skills", []))
        jd_skills = set(s.lower() for s in jd_data.get("required_skills", []))
        
        if jd_skills:
            overlap = jd_skills.intersection(res_skills)
            skill_overlap = len(overlap) / len(jd_skills)
        else:
            skill_overlap = 0.8 # Default match
            
        # 3. Experience Fit (Years check)
        # Mock logic: assume good fit for demo
        actual_exp = float(resume_data.get("experience_years", 5))
        required_exp = float(jd_data.get("min_years_experience", 0))
        exp_fit = 1.0 if actual_exp >= required_exp else (actual_exp / required_exp if required_exp > 0 else 1.0)
        
        # Weighted Overall Score
        final_score = (
            (semantic_sim * self.weights["semantic_similarity"]) +
            (skill_overlap * self.weights["skill_overlap"]) +
            (exp_fit * self.weights["experience_fit"])
        ) * 100
        
        return {
            "candidate_name": resume_data.get("name", "Unknown"),
            "final_score": round(final_score, 2),
            "breakdown": {
                "semantic_similarity": round(semantic_sim * 100, 2),
                "skill_overlap": round(skill_overlap * 100, 2),
                "experience_fit": round(exp_fit * 100, 2)
            }
        }

    def rank_candidates(self, candidates: List[Dict[str, Any]], jd_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = [self.score_candidate(c, jd_data) for c in candidates]
        return sorted(results, key=lambda x: x["final_score"], reverse=True)
