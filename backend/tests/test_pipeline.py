from app.services.resume_parser import ResumeParser
from app.ml.skill_vocabulary import find_skills_in_text, canonical_skill
from app.services.semantic_matcher import SemanticMatcher, _text_cosine
from app.services.analysis import run_analysis, extract_min_years
from app.utils.uploads import validate_upload, UploadValidationError

SAMPLE_RESUME = """John Doe
john.doe@email.com
+1-555-123-4567

Professional Summary
Senior Software Engineer with 8 years of experience.

Experience
Senior Software Engineer at Acme Corp, 2019-2025 (6 years)
- Built REST APIs with Python, FastAPI, and PostgreSQL
Software Engineer at Beta Inc, 2016-2019 (3 years)
- Developed React and JavaScript frontends

Education
Bachelor of Technology in Computer Science, State University, 2016

Skills
Python, JavaScript, React, Node.js, FastAPI, PostgreSQL, Docker, AWS, SQL
"""

SAMPLE_JD = """We are looking for a Senior Software Engineer with 5+ years of experience.

Requirements:
- Strong Python and FastAPI experience
- PostgreSQL and SQL databases
- Docker and AWS cloud experience
- React and JavaScript frontend skills
- Experience with REST API design

Nice to have:
- Kubernetes
- Machine Learning
"""


# ---------- skill vocabulary ----------

def test_find_skills_basic():
    hits = find_skills_in_text("Experienced with Python, React and AWS")
    names = {h["name"] for h in hits}
    assert {"Python", "React", "AWS"} <= names


def test_canonical_alias():
    assert canonical_skill("js") == "JavaScript"
    assert canonical_skill("k8s") == "Kubernetes"
    assert canonical_skill("not-a-skill") is None


# ---------- resume parser ----------

def test_parse_resume_extracts_key_fields():
    p = ResumeParser().parse(SAMPLE_RESUME)
    assert p["personal_info"]["email"] == "john.doe@email.com"
    assert "Python" in p["full_extracted_data"]["skills"]
    assert "FastAPI" in p["full_extracted_data"]["skills"]
    assert p["experience"]["total_years"] == 9.0
    assert any("Bachelor" in e for e in p["education"])


def test_parse_no_fabricated_contact_or_experience():
    p = ResumeParser().parse("Some random text without contact info or dates")
    assert p["personal_info"]["email"] is None
    assert p["personal_info"]["phone"] is None
    assert p["experience"]["total_years"] is None


def test_experience_single_range_present():
    p = ResumeParser().parse("Experience\nEngineer at X, Jan 2020 - Present\nSkills\nPython")
    assert p["experience"]["total_years"] is not None
    assert p["experience"]["total_years"] >= 1


# ---------- matcher ----------

def test_matcher_deterministic():
    m = SemanticMatcher()
    resume = {"raw_text": SAMPLE_RESUME, "skills": ["Python", "React"], "experience_years": 6, "name": "A"}
    jd = {"raw_text": SAMPLE_JD, "required_skills": ["Python", "FastAPI", "Docker"], "min_years_experience": 5}
    r1 = m.score_candidate(resume, jd)
    r2 = m.score_candidate(resume, jd)
    assert r1 == r2  # no randomness
    assert 0 <= r1["final_score"] <= 100


def test_matcher_skill_overlap_partial():
    m = SemanticMatcher()
    resume = {"raw_text": "x", "skills": ["Python", "FastAPI"], "experience_years": None, "name": "A"}
    jd = {"raw_text": "x", "required_skills": ["Python", "Kubernetes"], "min_years_experience": 0}
    r = m.score_candidate(resume, jd)
    assert r["breakdown"]["skill_overlap"] == 50.0
    assert r["breakdown"]["experience_fit"] == 50.0  # unknown -> neutral


def test_text_cosine_bounds():
    assert 0.0 <= _text_cosine("hello world", "hello world") <= 1.0
    assert _text_cosine("hello world", "hello world") > 0.5


# ---------- analysis pipeline ----------

def test_run_analysis_shape():
    out = run_analysis(SAMPLE_RESUME, SAMPLE_JD)
    for key in ["overall_score", "breakdown", "verdict", "suggestions",
                "matched_skills", "missing_skills", "confidence", "candidate"]:
        assert key in out
    assert out["required_years"] == 5.0
    assert "Python" in out["matched_skills"]
    assert "Kubernetes" in out["missing_skills"] or "Machine Learning" in out["missing_skills"]


def test_extract_min_years():
    assert extract_min_years(SAMPLE_JD) == 5.0
    assert extract_min_years("no requirement here") is None


# ---------- upload validation ----------

def test_validate_pdf_magic():
    assert validate_upload("cv.pdf", b"%PDF-1.4 fake content") == ".pdf"


def test_validate_docx_magic():
    assert validate_upload("cv.docx", b"PK\x03\x04rest") == ".docx"


def test_validate_rejects_bad_ext():
    try:
        validate_upload("evil.exe", b"MZ")
        assert False, "should have raised"
    except UploadValidationError:
        pass


def test_validate_rejects_spoofed_content():
    try:
        validate_upload("fake.pdf", b"not a pdf at all")
        assert False, "should have raised"
    except UploadValidationError:
        pass


def test_validate_rejects_oversize():
    try:
        validate_upload("big.pdf", b"%PDF" + b"0" * (5 * 1024 * 1024 + 1))
        assert False, "should have raised"
    except UploadValidationError:
        pass
