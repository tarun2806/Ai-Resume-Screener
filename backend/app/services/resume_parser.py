import re
from datetime import datetime
from typing import Dict, List, Any, Optional

from app.ml.skill_vocabulary import find_skills_in_text, ALL_CANONICAL_SKILLS


class ResumeParser:
    """
    Rule-based resume parser. Deterministic, dependency-free extraction of
    contact info, sections, skills, education and experience.
    """

    SECTION_HEADERS = {
        "experience": ["experience", "work experience", "employment history", "work history", "professional experience"],
        "education": ["education", "academic background", "academics", "educational qualification"],
        "skills": ["skills", "technical skills", "core competencies", "technologies", "expertise", "tech stack"],
        "projects": ["projects", "academic projects", "personal projects", "key projects"],
    }

    def parse(self, text: str) -> Dict[str, Any]:
        sections = self._extract_sections(text)
        skills = self._extract_skills(sections, text)
        education = self._extract_education(sections.get("education", text))
        experience_summary = self._analyze_experience(sections.get("experience", ""))
        projects = self._extract_projects(sections.get("projects", ""))

        personal_info = {
            "name": self._extract_name(text),
            "email": self._extract_email(text),
            "phone": self._extract_phone(text),
        }

        return {
            "personal_info": personal_info,
            "sections_found": list(sections.keys()),
            "skills": skills,
            "education": education,
            "experience": {
                "total_years": experience_summary["total_years"],
                "date_ranges": experience_summary.get("date_ranges", []),
                "raw_experience_text": sections.get("experience", "")[:500],
            },
            "projects": projects,
            "full_extracted_data": {
                "skills": [s["normalized"] for s in skills],
                "experience_years": experience_summary["total_years"],
            },
            "raw_text": text,
        }

    # ---------- sections ----------

    def _extract_sections(self, text: str) -> Dict[str, str]:
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        sections: Dict[str, List[str]] = {}
        current_section = "summary"
        section_content: List[str] = []

        header_patterns = []
        for key, aliases in self.SECTION_HEADERS.items():
            pattern = re.compile(
                r"^\s*(" + "|".join(re.escape(a) for a in aliases) + r")\s*[:\-–—]?\s*$",
                re.I,
            )
            header_patterns.append((key, pattern))

        for line in lines:
            header_found = False
            for sec_key, pattern in header_patterns:
                if pattern.match(line):
                    if section_content:
                        sections[current_section] = "\n".join(section_content)
                    current_section = sec_key
                    section_content = []
                    header_found = True
                    break
            if not header_found:
                section_content.append(line)

        if section_content:
            sections[current_section] = "\n".join(section_content)
        return sections

    # ---------- skills ----------

    def _extract_skills(self, sections: Dict[str, str], full_text: str) -> List[Dict[str, str]]:
        """
        Extract canonical skills. The dedicated skills section is scanned
        first; the remainder of the document is scanned afterwards so skills
        mentioned in experience descriptions are still captured.
        """
        found: Dict[str, Dict[str, str]] = {}

        def _scan(text: str):
            for hit in find_skills_in_text(text):
                name = hit["name"]
                if name not in found:
                    found[name] = {"raw": hit["matched_alias"], "normalized": name}

        _scan(sections.get("skills", ""))
        _scan(full_text)

        # Stable order: order of first appearance in the document
        order = {h["name"]: i for i, h in enumerate(find_skills_in_text(full_text))}
        return sorted(found.values(), key=lambda s: order.get(s["normalized"], 9999))

    # ---------- personal info ----------

    def _extract_name(self, text: str) -> str:
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Skip obvious non-name lines (emails, phones, URLs, headers)
            if "@" in line or re.search(r"\d{3}", line) or line.lower() in {
                "resume", "curriculum vitae", "cv", "professional summary"
            }:
                continue
            if 2 <= len(line.split()) <= 5 and not line.endswith(":"):
                return line
        return "Candidate"

    def _extract_email(self, text: str) -> Optional[str]:
        match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
        return match.group(0) if match else None

    def _extract_phone(self, text: str) -> Optional[str]:
        match = re.search(
            r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", text
        )
        return match.group(0) if match else None

    # ---------- education ----------

    def _extract_education(self, text: str) -> List[str]:
        edu_keywords = [
            "bachelor", "master", "phd", "ph.d", "b.tech", "m.tech", "b.e", "m.e",
            "b.sc", "m.sc", "mba", "bca", "mca", "degree", "university", "college",
            "diploma", "associate",
        ]
        lines = text.split("\n")
        education = [
            line.strip()
            for line in lines
            if any(k in line.lower() for k in edu_keywords)
        ]
        # de-duplicate preserving order
        seen = set()
        out = []
        for e in education:
            if e.lower() not in seen:
                seen.add(e.lower())
                out.append(e)
        return out[:4]

    # ---------- projects ----------

    def _extract_projects(self, text: str) -> List[str]:
        if not text:
            return []
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        projects = [l for l in lines if re.match(r"^[\s·\-•*]", l)]
        seen = set()
        out = []
        for p in projects:
            if p.lower() not in seen:
                seen.add(p.lower())
                out.append(p)
        return out[:3]

    # ---------- experience ----------

    _YEAR = r"(?:19|20)\d{2}"
    _MONTH = (
        r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
        r"[a-z]*\.?"
    )
    _DATE = rf"(?:{_MONTH}\s+)?{_YEAR}"

    def _analyze_experience(self, text: str) -> Dict[str, Any]:
        """
        Estimate total years of experience.

        Strategy (deterministic, best-effort):
        1. Parse explicit date ranges like 'Jan 2019 - Present' or '2016-2019'.
        2. Fall back to explicit 'N years' mentions.
        3. Otherwise return None (unknown) — never fabricate a value.
        """
        if not text:
            return {"total_years": None, "date_ranges": []}

        ranges = []
        seen_ranges = set()
        # Patterns: "2019 - 2025", "2019-2025", "Jan 2019 – Present", "2019 to Present"
        range_patterns = [
            rf"{self._DATE}\s*(?:-|–|—|to)\s*(?:{self._DATE}|present|current|now)",
            rf"{self._DATE}\s*-\s*{self._DATE}",
        ]
        for pat in range_patterns:
            for m in re.finditer(pat, text, re.I):
                key = re.sub(r"\s+", "", m.group(0).lower())
                if key not in seen_ranges:
                    seen_ranges.add(key)
                    ranges.append(m.group(0))

        total = 0.0
        parsed_any = False
        current_year = datetime.now().year

        for r in ranges:
            years = [int(y) for y in re.findall(self._YEAR, r)]
            if not years:
                continue
            start = min(years)
            end = max(years) if len(years) > 1 else current_year
            if "present" in r.lower() or "current" in r.lower() or "now" in r.lower():
                end = current_year
            span = end - start
            if 0 <= span <= 60:
                total += span
                parsed_any = True

        if parsed_any:
            # Avoid double counting nested/overlapping ranges: cap at a sane max
            return {
                "total_years": round(min(total, 45.0), 1),
                "date_ranges": ranges[:10],
            }

        years_match = re.findall(r"(\d{1,2})\s*\+?\s*years?", text, re.I)
        if years_match:
            return {
                "total_years": float(max(int(y) for y in years_match)),
                "date_ranges": [],
            }

        return {"total_years": None, "date_ranges": []}
