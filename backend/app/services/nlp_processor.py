import re
from typing import Dict, Any, List

from app.ml.ontology import expand_skills_semantically, get_skill_category
from app.ml.skill_vocabulary import find_skills_in_text, ALL_CANONICAL_SKILLS
from app.services.resume_parser import ResumeParser


class AdvancedNLPProcessor:
    """
    NLP facade used by the API layer. Resume parsing delegates to the
    deterministic ResumeParser; JD processing extracts canonical skills from
    a curated vocabulary and expands them through the skill ontology.
    """

    def __init__(self):
        self.resume_parser = ResumeParser()

    def process_resume(self, text: str) -> Dict[str, Any]:
        parsed = self.resume_parser.parse(text)
        return {
            "name": parsed["personal_info"]["name"],
            "email": parsed["personal_info"]["email"],
            "phone": parsed["personal_info"]["phone"],
            "skills_detected": parsed["full_extracted_data"]["skills"],
            "education": ", ".join(parsed["education"]) if parsed["education"] else "",
            "raw_text": parsed["raw_text"],
            "expert_data": parsed,
        }

    def process_jd(self, text: str) -> Dict[str, Any]:
        """Extract explicit skills from the JD and expand via ontology."""
        explicit = [h["name"] for h in find_skills_in_text(text)]
        expanded_map = expand_skills_semantically(explicit)

        # Merge explicit skills that the ontology doesn't know about
        for skill in explicit:
            expanded_map.setdefault(skill.lower(), 1.0)

        categorized: Dict[str, List[Dict[str, Any]]] = {
            "domain": [], "tools": [], "soft": []
        }
        for skill, weight in expanded_map.items():
            category = get_skill_category(skill)
            info = {
                "name": skill,
                "is_inferred": weight < 1.0,
                "confidence": "High" if weight >= 0.9 else "Medium" if weight >= 0.6 else "Low",
            }
            if category == "Tool/Technology":
                categorized["tools"].append(info)
            elif category == "Soft Skill":
                categorized["soft"].append(info)
            else:
                categorized["domain"].append(info)

        return {
            "raw_text": text,
            "categorized_skills": categorized,
            "all_skills_flat": list(expanded_map.keys()),
            "explicit_skills": explicit,
            "expanded_map": expanded_map,
        }
