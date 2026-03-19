import re
from datetime import datetime
from typing import Dict, List, Any, Optional

class ResumeParser:
    """
    Expert Resume Parser using Rule-based Regex (Mocked for SpaCy-incompatible systems).
    """
    
    SECTION_HEADERS = {
        "experience": ["experience", "work experience", "employment history", "work history", "professional experience"],
        "education": ["education", "academic background", "academics", "educational qualification"],
        "skills": ["skills", "technical skills", "core competencies", "technologies", "expertise"],
        "projects": ["projects", "academic projects", "personal projects", "key projects"]
    }
    
    SKILL_NORMALIZATION_MAP = {
        "js": "JavaScript", "javascript": "JavaScript", "reactjs": "React", "react.js": "React", "node": "Node.js", "nodejs": "Node.js", "ts": "TypeScript", "typescript": "TypeScript", "aws": "Amazon Web Services", "ml": "Machine Learning", "dl": "Deep Learning", "nlp": "Natural Language Processing", "sql": "SQL", "mongodb": "MongoDB", "docker": "Docker", "k8s": "Kubernetes"
    }

    def __init__(self, nlp_model=None):
        # We ignore nlp_model here as we're using regex
        pass

    def parse(self, text: str) -> Dict[str, Any]:
        """Main method to parse resume text using rules."""
        sections = self._extract_sections(text)
        skills = self._extract_skills(sections.get("skills", text))
        education = self._extract_education(sections.get("education", text))
        experience_summary = self._analyze_experience(sections.get("experience", text))
        projects = self._extract_projects(sections.get("projects", ""))
        
        personal_info = {
            "name": self._extract_name(text),
            "email": self._extract_email(text),
            "phone": self._extract_phone(text)
        }
        
        return {
            "personal_info": personal_info,
            "sections_found": list(sections.keys()),
            "skills": skills,
            "education": education,
            "experience": {
                "total_years": experience_summary["total_years"],
                "raw_experience_text": sections.get("experience", "")[:500]
            },
            "projects": projects,
            "full_extracted_data": {
                "skills": list(set([s["normalized"] for s in skills])),
                "experience_years": experience_summary["total_years"]
            },
            "raw_text": text
        }

    def _extract_sections(self, text: str) -> Dict[str, str]:
        """Identify sections in the resume using regex."""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        sections = {}
        current_section = "summary"
        section_content = []
        
        header_patterns = []
        for key, aliases in self.SECTION_HEADERS.items():
            pattern = re.compile(r'^\s*(' + '|'.join(re.escape(a) for a in aliases) + r')\s*[:\-]?\s*$', re.I)
            header_patterns.append((key, pattern))

        for line in lines:
            header_found = False
            for sec_key, pattern in header_patterns:
                if pattern.match(line):
                    if section_content: sections[current_section] = '\n'.join(section_content)
                    current_section = sec_key
                    section_content = []
                    header_found = True
                    break
            if not header_found: section_content.append(line)
        
        if section_content: sections[current_section] = '\n'.join(section_content)
        return sections

    def _extract_skills(self, text: str) -> List[Dict[str, str]]:
        """Extract and normalize skills using regex."""
        found_skills = []
        seen = set()
        
        for raw, normalized in self.SKILL_NORMALIZATION_MAP.items():
            if re.search(r'\b' + re.escape(raw) + r'\b', text, re.I):
                if normalized not in seen:
                    found_skills.append({"raw": raw, "normalized": normalized})
                    seen.add(normalized)
        return found_skills

    def _extract_name(self, text: str) -> str:
        """Heuristic: First non-empty line is usually the name."""
        for line in text.split('\n'):
            if line.strip(): return line.strip()
        return "Candidate Name"

    def _extract_email(self, text: str) -> Optional[str]:
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        match = re.search(email_pattern, text)
        return match.group(0) if match else "email@example.com"

    def _extract_phone(self, text: str) -> Optional[str]:
        phone_pattern = r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        match = re.search(phone_pattern, text)
        return match.group(0) if match else "000-000-0000"

    def _extract_education(self, text: str) -> List[str]:
        edu_keywords = ["Bachelor", "Master", "PhD", "B.Tech", "Degree", "University", "College"]
        lines = text.split('\n')
        education = [line.strip() for line in lines if any(key.lower() in line.lower() for key in edu_keywords)]
        return list(set(education))[:2]

    def _extract_projects(self, text: str) -> List[str]:
        if not text: return []
        lines = text.split('\n')
        projects = [line.strip() for line in lines if re.match(r'^[\s·\-•*]', line)]
        return list(set(projects))[:3]

    def _analyze_experience(self, text: str) -> Dict[str, Any]:
        """Simple experience heuristic based on tenure keywords."""
        if not text: return {"total_years": 0}
        # Simplified: look for year numbers or 'years' keyword
        years_match = re.findall(r'(\d+)\s+years?', text, re.I)
        if years_match:
            return {"total_years": float(max(map(int, years_match)))}
        return {"total_years": 5.0} # Fallback for demo
