from typing import List, Dict, Any
from app.ml.ontology import expand_skills_semantically, get_skill_category

class CareerAssistant:
    """
    Expert AI Career Assistant providing actionable resume improvements.
    """
    
    def generate_feedback(self, resume_data: Dict[str, Any], jd_data: Dict[str, Any], current_score: float) -> Dict[str, Any]:
        """
        Analyzes the match and provides a structured improvement plan.
        """
        # 1. Identify Missing Skills (Compare JD Expanded vs Resume Detected)
        res_skills = set(s.lower() for s in resume_data.get("skills_detected", []))
        jd_skill_map = jd_data.get("expanded_map", {}) # Map of {skill: weight}
        
        missing_skills = []
        for skill, weight in jd_skill_map.items():
            if skill not in res_skills:
                missing_skills.append({"name": skill, "weight": weight})
        
        # Sort missing skills by importance (weight)
        missing_skills = sorted(missing_skills, key=lambda x: x["weight"], reverse=True)
        
        # 2. Generate Actionable Suggestions
        improvement_plan = []
        
        # Tip 1: Top Missing Hard Skills
        top_missing = missing_skills[:3]
        for skill_info in top_missing:
            skill_name = skill_info["name"].title()
            category = get_skill_category(skill_info["name"])
            
            # Estimate Impact: Skill match is 40% of total score. 
            # If a skill has 1.0 weight and we have 10 skills, one skill is ~4% of total.
            impact = round(skill_info["weight"] * 8.5, 1) # Estimated score jump
            
            improvement_plan.append({
                "type": "Skill Addition",
                "skill": skill_name,
                "suggestion": f"Explicitly mention your experience with '{skill_name}' in your 'Professional Experience' or 'Skills' section. The job specifically requires this {category}.",
                "estimated_score_increase": f"+{impact}%"
            })
            
        # Tip 2: Content Depth (Heuristic)
        word_count = len(resume_data.get("raw_text", "").split())
        if word_count < 250:
             improvement_plan.append({
                "type": "Content Expansion",
                "suggestion": "Your resume is currently quite brief. Expanding on the specific impact of your projects (e.g., using the STAR method: Situation, Task, Action, Result) will improve your Semantic Alignment score.",
                "estimated_score_increase": "+10-15%"
            })
            
        # Tip 3: Formatting & Education
        if "No education found" in resume_data.get("education", ""):
            improvement_plan.append({
                "type": "Structure Improvement",
                "suggestion": "Add a clear 'Education' section. Recruiters and AI systems look for your academic background as part of the total candidate evaluation.",
                "estimated_score_increase": "+5%"
            })

        return {
            "current_score": round(current_score, 1),
            "missing_key_skills": [s["name"].title() for s in top_missing],
            "improvement_plan": improvement_plan,
            "next_steps": [
                "1. Update your resume with the suggested keywords above.",
                "2. Focus on quantifiable achievements in your work history.",
                "3. Re-upload your resume to AI ScreenX to see your new improved score!"
            ]
        }

if __name__ == "__main__":
    # Test Data
    res = {"skills_detected": ["python", "sql"], "raw_text": "...", "education": "B.Tech"}
    jd = {
        "expanded_map": {"python": 1.0, "fastapi": 0.9, "docker": 0.8, "aws": 0.7, "sql": 1.0},
        "categorized_skills": {"tools": ["fastapi", "docker"]}
    }
    
    assistant = CareerAssistant()
    feedback = assistant.generate_feedback(res, jd, 65.4)
    
    import json
    print(json.dumps(feedback, indent=2))
