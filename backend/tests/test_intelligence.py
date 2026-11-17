"""Milestone 2 tests: taxonomy, explainable scoring, recruiter intelligence."""
import os
import sys
import tempfile

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["JWT_SECRET"] = "test-secret"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json

import pytest
from fastapi.testclient import TestClient

from main import app
from app.ml.skill_vocabulary import (
    canonical_skill, find_skills_in_text, SKILL_VOCABULARY, ALL_CANONICAL_SKILLS,
)
from app.ml.ontology import related_skills_for, get_skill_category, expand_skills_semantically
from app.ml.skill_taxonomy import SKILL_CATEGORIES, SKILL_RELATIONS
from app.services.analysis import (
    run_analysis, extract_preferred_skills, extract_required_degree, _evidence_for_skill,
)
from app.services.semantic_matcher import SemanticMatcher

client = TestClient(app)


# ---------- taxonomy / ontology ----------

def test_taxonomy_covers_vocabulary():
    """Every canonical skill must have a category."""
    missing = [s for s in ALL_CANONICAL_SKILLS if s not in SKILL_CATEGORIES]
    assert not missing, f"Skills missing categories: {missing}"


def test_relation_targets_resolvable():
    """Relation targets should be canonical skills or resolvable aliases."""
    unresolved = set()
    for src, rels in SKILL_RELATIONS.items():
        for tgt in rels:
            if tgt not in SKILL_VOCABULARY and canonical_skill(tgt) is None:
                unresolved.add((src, tgt))
    assert not unresolved, f"Unresolved relation targets: {unresolved}"


def test_alias_normalization():
    assert canonical_skill("k8s") == "Kubernetes"
    assert canonical_skill("JS") == "JavaScript"
    assert canonical_skill("postgres") == "PostgreSQL"
    assert canonical_skill("reactjs") == "React"


def test_no_false_positive_skills():
    """Common English words must not extract as skills."""
    text = "I enjoy cooking, reading books, and playing chess on weekends."
    found = {s["name"] for s in find_skills_in_text(text)}
    assert found == set()


def test_related_is_partial_not_equivalent():
    """Ontology-related skills must not count as full matches."""
    m = SemanticMatcher()
    resume = {"skills": ["Vue.js"], "raw_text": "", "experience_years": None}
    jd = {"required_skills": ["React"], "raw_text": "", "min_years_experience": 0,
          "preferred_skills": [], "required_degree": None}
    r = m.score_candidate(resume, jd)
    # Vue is related to React but should earn only partial credit -> <100
    assert r["breakdown"]["skill_overlap"] < 100.0
    assert r["breakdown"]["skill_overlap"] > 0.0


def test_different_terms_same_skill():
    """'k8s' and 'Kubernetes' are the same canonical skill."""
    m = SemanticMatcher()
    resume = {"skills": ["k8s"], "raw_text": "", "experience_years": None}
    jd = {"required_skills": ["Kubernetes"], "raw_text": "", "min_years_experience": 0,
          "preferred_skills": [], "required_degree": None}
    r = m.score_candidate(resume, jd)
    assert r["breakdown"]["skill_overlap"] == 100.0


# ---------- explainable scoring ----------

SAMPLE_JD = """
Senior Backend Engineer
We are looking for a backend engineer with 5+ years of experience.

Requirements:
- Python and FastAPI
- PostgreSQL
- AWS or GCP
- Docker and Kubernetes

Preferred qualifications:
- Redis
- GraphQL
- Terraform

Bachelor's degree in Computer Science or equivalent required.
"""

SAMPLE_RESUME = """
Jane Doe
jane@example.com

Experience:
Senior Engineer, Acme Corp (2019 - Present)
- Built REST APIs with Python and FastAPI
- PostgreSQL database design and optimization
- Deployed services on AWS with Docker and Kubernetes

Education:
B.S. Computer Science, State University, 2018

Skills: Python, FastAPI, PostgreSQL, AWS, Docker, Kubernetes, Redis
"""


def test_preferred_skill_extraction():
    prefs = extract_preferred_skills(SAMPLE_JD)
    assert "Redis" in prefs
    assert "Terraform" in prefs
    # Required skills must NOT leak into preferred list
    assert "Python" not in prefs


def test_required_degree_extraction():
    assert extract_required_degree(SAMPLE_JD) == "bachelor"
    assert extract_required_degree("No degree requirements listed here.") is None


def test_score_breakdown_components():
    out = run_analysis(SAMPLE_RESUME, SAMPLE_JD)
    keys = {c["key"] for c in out["score_breakdown"]}
    assert keys == {"skill_overlap", "preferred_match", "semantic_similarity",
                    "experience_fit", "education_fit"}
    assert out["scoring_weights"]["skill_overlap"] == pytest.approx(0.35)
    # Deterministic
    out2 = run_analysis(SAMPLE_RESUME, SAMPLE_JD)
    assert out["overall_score"] == out2["overall_score"]


def test_evidence_snippets_real():
    out = run_analysis(SAMPLE_RESUME, SAMPLE_JD)
    evidence = {e["skill"]: e["snippet"] for e in out["evidence"]}
    assert "Python" in evidence
    assert evidence["Python"] is not None
    assert "python" in evidence["Python"].lower()


def test_missing_mandatory_shown():
    weak_resume = "John Smith\njohn@test.com\n\nExperience: Sales manager 2015-Present\n\nEducation: B.A. English\n\nSkills: Excel, communication"
    out = run_analysis(weak_resume, SAMPLE_JD)
    assert "Python" in out["missing_skills"]
    assert out["overall_score"] < 60


def test_no_auto_reject_fields():
    """Output must not contain rejection/auto-decision fields."""
    out = run_analysis(SAMPLE_RESUME, SAMPLE_JD)
    assert "rejected" not in out
    assert "auto_reject" not in out


def test_extraction_limitations_disclosed():
    out = run_analysis(SAMPLE_RESUME, SAMPLE_JD)
    assert isinstance(out["extraction_limitations"], list)
    assert len(out["extraction_limitations"]) >= 2


# ---------- recruiter intelligence endpoints ----------

def _register(email, role="recruiter"):
    client.post("/api/v1/auth/register", json={
        "email": email, "password": "password123", "name": "T User", "role": role})
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def recruiter_headers():
    return _register("rec-intel@test.com")


def _docx(text: str) -> bytes:
    import docx, io
    d = docx.Document()
    for line in text.split("\n"):
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


@pytest.fixture(scope="module")
def job_and_apps(recruiter_headers):
    h = recruiter_headers
    job = client.post("/api/v1/ats/jobs", json={
        "title": "Backend Engineer", "description": SAMPLE_JD, "location": "Remote",
    }, headers=h).json()
    # Screen two resumes: one strong, one weak
    strong = _docx(SAMPLE_RESUME)
    weak = _docx("Bob Jones\nbob@x.com\nSales associate 2018-Present\nB.A. History\nSkills: Excel")
    r = client.post(f"/api/v1/ats/jobs/{job['id']}/screen",
                    files=[("files", ("strong.docx", strong, "application/octet-stream")),
                           ("files", ("weak.docx", weak, "application/octet-stream"))],
                    headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["screened"] == 2, r.json()
    apps = r.json()["ranked"]
    return job, apps, h


def test_compare_endpoint(job_and_apps):
    job, apps, h = job_and_apps
    ids = ",".join(str(a["id"]) for a in apps[:2])
    r = client.get(f"/api/v1/ats/jobs/{job['id']}/compare?ids={ids}", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert len(data["candidates"]) == 2
    assert "skill_matrix" in data
    # Strong candidate should rank first
    assert data["candidates"][0]["score"] >= data["candidates"][1]["score"]


def test_compare_requires_auth(job_and_apps):
    job, apps, _ = job_and_apps
    r = client.get(f"/api/v1/ats/jobs/{job['id']}/compare?ids={apps[0]['id']}")
    assert r.status_code in (401, 403)


def test_compare_wrong_job_rejected(job_and_apps):
    job, apps, h = job_and_apps
    other = client.post("/api/v1/ats/jobs", json={
        "title": "Other Role", "description": SAMPLE_JD * 2,
    }, headers=h).json()
    r = client.get(f"/api/v1/ats/jobs/{other['id']}/compare?ids={apps[0]['id']}", headers=h)
    # app belongs to different job -> no matching applications
    assert r.status_code == 404


def test_insights_endpoint(job_and_apps):
    job, apps, h = job_and_apps
    r = client.get(f"/api/v1/ats/jobs/{job['id']}/insights", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert data["total_applications"] >= 2
    assert "by_status" in data
    assert "top_missing_skills" in data
    assert data["score"]["avg"] is not None


def test_insights_forbidden_for_candidate(job_and_apps):
    job, _, _ = job_and_apps
    ch = _register("cand-insight@test.com", role="candidate")
    r = client.get(f"/api/v1/ats/jobs/{job['id']}/insights", headers=ch)
    assert r.status_code == 403


def test_deterministic_scoring_regression():
    """Same inputs must always produce the same score."""
    scores = {run_analysis(SAMPLE_RESUME, SAMPLE_JD)["overall_score"] for _ in range(3)}
    assert len(scores) == 1
