import spacy
from spacy.matcher import PhraseMatcher
import re
from typing import Dict, List, Any
from app.ml.ontology import expand_skills_semantically, get_skill_category

try:
    nlp = spacy.load("en_core_web_md")
except:
    nlp = spacy.blank("en")

class AdvancedNLPProcessor:
    def __init__(self):
        self.nlp = nlp
        # Expanded base skills for matching - this triggers the ontology
        self.base_skills = [
            "Python", "Java", "JavaScript", "React", "Node.js", "FastAPI",
            "SQL", "PostgreSQL", "MongoDB", "Docker", "AWS", "Azure",
            "Machine Learning", "Deep Learning", "NLP", "Transformers",
            "Procure to Pay", "P2P", "Order to Cash", "O2C", "ERP", "SAP", "Oracle",
            "Leadership", "Communication", "Excel", "Accounts Payable", "Invoicing",
            "Vendor Management", "Audit", "Compliance"
        ]
        self.matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
        patterns = [self.nlp.make_doc(text) for text in self.base_skills]
        self.matcher.add("SKILLS", patterns)

    def process_resume(self, text: str) -> Dict[str, Any]:
        doc = self.nlp(text)
        raw_skills = self._extract_skills(doc)
        
        return {
            "name": self._extract_name(doc),
            "email": self._extract_email(text),
            "skills_detected": raw_skills,
            "education": self._extract_education(text),
            "raw_text": text
        }

    def process_jd(self, text: str) -> Dict[str, Any]:
        # 1. Clean JD (Remove fluff)
        cleaned_text = self._clean_jd(text)
        doc = self.nlp(cleaned_text)
        
        # 2. Extract Explicit Skills
        explicit_skills = self._extract_skills(doc)
        
        # 3. Semantic Expansion (Inference)
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
            
            if category == "Tool/Technology":
                categorized["tools"].append(skill_info)
            elif category == "Soft Skill":
                categorized["soft"].append(skill_info)
            else:
                categorized["domain"].append(skill_info)
        
        # Ensure sections aren't empty (fill with defaults if nothing detected)
        self._ensure_minimum_content(categorized)

        return {
            "raw_text": cleaned_text,
            "categorized_skills": categorized,
            "all_skills_flat": list(expanded_map.keys()),
            "expanded_map": expanded_map
        }

    def _ensure_minimum_content(self, categorized: Dict):
        if not categorized["soft"]:
            categorized["soft"].append({"name": "Communication", "is_inferred": True, "confidence": "Low"})
            categorized["soft"].append({"name": "Problem Solving", "is_inferred": True, "confidence": "Low"})
        if not categorized["domain"]:
             categorized["domain"].append({"name": "Professional Experience", "is_inferred": True, "confidence": "Low"})

    def _clean_jd(self, text: str) -> str:
        # Improved cleaning: focus on sections that describe the role
        content_patterns = [
            r"(?i)(Responsibilities|Requirements|Role|Qualifications).*?(?=(About us|Equal Opportunity|Benefit|$))",
            r"(?i)(What you will do|The role|Skills needed).*?(?=(About us|Employer|$))"
        ]
        
        for pattern in content_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(0).strip()
        return text

    def _extract_skills(self, doc) -> List[str]:
        matches = self.matcher(doc)
        return list(set([doc[start:end].text.lower() for _, start, end in matches]))

    def _extract_name(self, doc) -> str:
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                return ent.text
        return "Unknown"

    def _extract_email(self, text: str) -> str:
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        match = re.search(email_pattern, text)
        return match.group(0) if match else ""

    def _extract_education(self, text: str) -> str:
        edu_keywords = ["Bachelor", "Master", "PhD", "B.Tech", "Degree"]
        for line in text.split('\n'):
            if any(key in line for key in edu_keywords):
                return line.strip()
        return "No education found"
