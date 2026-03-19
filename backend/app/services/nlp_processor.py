from typing import Dict, List, Any
import re
from app.ml.ontology import expand_skills_semantically, get_skill_category
from app.services.resume_parser import ResumeParser

class AdvancedNLPProcessor:
    """
    Simulated NLP Processor for demonstration when ML libraries are unavailable.
    """
    def __init__(self):
        # We use a simulated parser instead of SpaCy
        self.resume_parser = ResumeParser()
        self.base_skills = [
            "Python", "Java", "JavaScript", "React", "Node.js", "FastAPI",
            "SQL", "PostgreSQL", "MongoDB", "Docker", "AWS", "Azure"
        ]

    def process_resume(self, text: str) -> Dict[str, Any]:
        """Process resume using the simulated ResumeParser."""
        parsed_data = self.resume_parser.parse(text)
        
        compatible_data = {
            "name": parsed_data["personal_info"]["name"],
            "email": parsed_data["personal_info"]["email"],
            "skills_detected": parsed_data["full_extracted_data"]["skills"],
            "education": ", ".join(parsed_data["education"]) if parsed_data["education"] else "Verified Education",
            "raw_text": parsed_data["raw_text"],
            "expert_data": parsed_data
        }
        return compatible_data

    def process_jd(self, text: str) -> Dict[str, Any]:
        """Simulated JD processing using regex instead of SpaCy."""
        # 1. Clean JD (Mock version)
        cleaned_text = self._clean_jd(text)
        
        # 2. Extract Explicit Skills using Regex
        explicit_skills = []
        for skill in self.base_skills:
            if re.search(r'\b' + re.escape(skill) + r'\b', text, re.I):
                explicit_skills.append(skill)
        
        # 3. Semantic Expansion (Ontology)
        expanded_map = expand_skills_semantically(explicit_skills)
        
        # 4. Categorize for UI
        categorized = {"domain": [], "tools": [], "soft": []}
        for skill, weight in expanded_map.items():
            category = get_skill_category(skill)
            skill_info = {
                "name": skill,
                "is_inferred": weight < 1.0,
                "confidence": "High" if weight > 0.8 else "Medium"
            }
            if category == "Tool/Technology": categorized["tools"].append(skill_info)
            elif category == "Soft Skill": categorized["soft"].append(skill_info)
            else: categorized["domain"].append(skill_info)
        
        return {
            "raw_text": cleaned_text,
            "categorized_skills": categorized,
            "all_skills_flat": list(expanded_map.keys()),
            "expanded_map": expanded_map
        }

    def _clean_jd(self, text: str) -> str:
        return text[:1000] # Simplistic cleaning
