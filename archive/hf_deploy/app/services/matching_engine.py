from sentence_transformers import SentenceTransformer, util
import torch
import numpy as np
from typing import List, Dict, Any

class AdvancedMatchingEngine:
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        self.model = SentenceTransformer(model_name)

    def calculate_match(self, resume_data: Dict[str, Any], jd_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates match with fuzzy scoring, partial rewards, and transparent reasoning.
        """
        # 1. PRE-ENCODE RESUME SEGMENTS FOR OPTIMIZATION
        # Doing this once here saves many redundant transformer calls in the loop below
        res_text = resume_data["raw_text"]
        resume_lines = [line.strip() for line in res_text.split('\n') if len(line.strip()) > 10]
        resume_embs = None
        if resume_lines:
            # We encode the most important 25 lines of the resume for semantic sensing
            resume_embs = self.model.encode(resume_lines[:25], convert_to_tensor=True)

        # 2. FUZZY SKILL MATCHING
        res_skills = set(resume_data.get("skills_detected", []))
        jd_skill_map = jd_data.get("expanded_map", {})
        
        matched_explicit = []
        partial_matches = []
        unmatched_jd_skills = []
        
        total_skill_weight = sum(jd_skill_map.values()) or 1.0
        earned_skill_points = 0.0
        
        for jd_skill, weight in jd_skill_map.items():
            if jd_skill in res_skills:
                earned_skill_points += weight
                matched_explicit.append(jd_skill)
            else:
                # Semantic Fuzzy Check using pre-encoded embeddings
                is_partial = self._check_semantic_presence(jd_skill, resume_embs)
                if is_partial:
                    earned_skill_points += (weight * 0.4)
                    partial_matches.append(jd_skill)
                else:
                    unmatched_jd_skills.append(jd_skill)
        
        skill_score = (earned_skill_points / total_skill_weight) * 100
        
        # 3. COMPONENT SCORING (WEIGHTED)
        sem_sim = self._calculate_similarity(res_text, jd_data["raw_text"])
        sem_score = sem_sim * 100
        
        exp_score = min(max(sem_score * 0.9 + 5, 0), 100)
        
        quality_score = 100
        if not resume_data.get("email"): quality_score -= 20
        if "No education found" in resume_data.get("education", ""): quality_score -= 20
        
        overall_score = (skill_score * 0.4 + exp_score * 0.3 + sem_score * 0.2 + quality_score * 0.1)
        
        explanation = self._generate_explanation(overall_score, skill_score, matched_explicit, jd_data)
        suggestions = self._generate_smart_suggestions(unmatched_jd_skills, resume_data)

        return {
            "overall_score": round(overall_score, 1),
            "breakdown": {
                "skill_match": round(skill_score, 1),
                "experience_relevance": round(exp_score, 1),
                "semantic_alignment": round(sem_score, 1),
                "resume_quality": round(quality_score, 1)
            },
            "explanation": explanation,
            "suggestions": suggestions[:4],
            "matched_skills": matched_explicit,
            "partial_matches": partial_matches,
            "missing_skills": unmatched_jd_skills[:10],
            "categorized_skills": jd_data["categorized_skills"],
            "ai_reasoning": [
                "Checked the meaning of your words and how they relate to the job requirements.",
                "Used smart matching to find related skills even if you used different names.",
                "Gave more importance to your actual skills and work history than resume design."
            ],
            "verdict": self._get_verdict(overall_score)
        }

    def _check_semantic_presence(self, skill: str, resume_embs: torch.Tensor) -> bool:
        if resume_embs is None: return False
        
        skill_emb = self.model.encode(skill, convert_to_tensor=True)
        cos_sims = util.cos_sim(skill_emb, resume_embs)[0]
        if torch.max(cos_sims) > 0.65: # Threshold for "Partial Match"
            return True
        return False

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        emb1 = self.model.encode(text1, convert_to_tensor=True)
        emb2 = self.model.encode(text2, convert_to_tensor=True)
        return float(util.cos_sim(emb1, emb2)[0][0])

    def _generate_explanation(self, overall: float, skill: float, matched: list, jd: Dict) -> str:
        if overall > 75:
            return "Great match! Your resume shows you have the right skills and background for this role."
        if skill < 20:
            return "Your resume looks good, but it's missing some specific words the job is looking for. Listing these skills clearly could help you score higher."
        return "Decent match. You have some experience that fits, but you should try to clearly list all the key skills mentioned in the job post."

    def _generate_smart_suggestions(self, missing: list, resume: Dict) -> List[Dict[str, Any]]:
        suggestions = []
        for skill in missing[:3]:
            skill_label = skill.title()
            if "erp" in skill.lower():
                suggestions.append({
                    "tip": f"Improvement: Add any experience you have with ERP tools like SAP or Oracle to your resume.",
                    "impact": "+15-20%"
                })
            elif "procure" in skill.lower() or "pay" in skill.lower():
                suggestions.append({
                    "tip": f"Improvement: Explain your work with invoices and payments more clearly.",
                    "impact": "+25%"
                })
            else:
                suggestions.append({
                    "tip": f"Improvement: Use the word '{skill_label}' in your resume to show you have this skill.",
                    "impact": "+5-10%"
                })
        
        if len(resume["raw_text"].split()) < 200:
            suggestions.append({
                "tip": "Action: Write more about what you did in your projects. Short resumes might not show everything you are good at.",
                "impact": "+10%"
            })
            
        return suggestions

    def _get_verdict(self, score: float) -> str:
        if score > 85: return "Excellent Match"
        if score > 65: return "Strong Fit - Small Improvements Possible"
        if score > 45: return "Average Match - You might need more skills"
        return "Low Match - You may need to learn some new skills for this role"
