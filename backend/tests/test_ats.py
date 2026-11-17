import os
import sys
import tempfile

# Isolate DB before importing the app
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["JWT_SECRET"] = "test-secret"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

SAMPLE_RESUME_TEXT = """Jane Smith
jane@email.com

Experience
Software Engineer at TechCo, 2020 - Present
- Built APIs with Python and Django
- Worked with PostgreSQL and Docker on AWS

Education
B.Tech Computer Science, 2020

Skills
Python, Django, PostgreSQL, Docker, AWS, SQL
"""

SAMPLE_JD = """We need a Software Engineer with 3+ years of experience.
Requirements: Python, Django, PostgreSQL, Docker, AWS, SQL, REST API.
Nice to have: Kubernetes, Machine Learning.
"""


def _register(email, role="candidate", password="password123"):
    r = client.post("/api/v1/auth/register", json={
        "email": email, "password": password, "name": email.split("@")[0], "role": role,
    })
    assert r.status_code == 200, r.text
    return r.json()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make_docx_bytes(text: str) -> bytes:
    import docx, io
    d = docx.Document()
    for line in text.split("\n"):
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


@pytest.fixture(scope="module")
def recruiter():
    return _register("rec@t.com", "recruiter")


@pytest.fixture(scope="module")
def candidate():
    return _register("cand@t.com", "candidate")


def test_register_duplicate_409():
    _register("dup@t.com", "candidate")
    r = client.post("/api/v1/auth/register", json={
        "email": "dup@t.com", "password": "password123", "name": "x", "role": "candidate",
    })
    assert r.status_code == 409


def test_login_bad_password_401():
    r = client.post("/api/v1/auth/login", json={"email": "rec@t.com", "password": "wrongpass"})
    assert r.status_code == 401


def test_unauthenticated_401():
    assert client.get("/api/v1/ats/jobs").status_code == 401
    assert client.post("/api/v1/ats/jobs", json={"title": "x" * 5, "description": SAMPLE_JD}).status_code == 401


def test_candidate_cannot_create_job(recruiter, candidate):
    r = client.post("/api/v1/ats/jobs", json={"title": "Dev", "description": SAMPLE_JD}, headers=_auth(candidate["token"]))
    assert r.status_code == 403


def test_job_crud_and_screening(recruiter):
    tok = _auth(recruiter["token"])
    r = client.post("/api/v1/ats/jobs", json={
        "title": "Backend Engineer", "description": SAMPLE_JD, "location": "Remote",
    }, headers=tok)
    assert r.status_code == 200
    job = r.json()
    assert job["required_skills"]
    assert job["min_years"] == 3.0

    docx_bytes = _make_docx_bytes(SAMPLE_RESUME_TEXT)
    files = [("files", ("jane.docx", docx_bytes, "application/octet-stream"))]
    r = client.post(f"/api/v1/ats/jobs/{job['id']}/screen", files=files, headers=tok)
    assert r.status_code == 200
    data = r.json()
    assert data["screened"] == 1
    assert data["ranked"][0]["score"] > 0
    assert "Python" in data["ranked"][0]["matched_skills"]

    # applications list
    r = client.get(f"/api/v1/ats/jobs/{job['id']}/applications", headers=tok)
    assert r.status_code == 200
    apps = r.json()["applications"]
    assert len(apps) == 1
    app_id = apps[0]["id"]

    # detail + update
    r = client.get(f"/api/v1/ats/applications/{app_id}", headers=tok)
    assert r.status_code == 200
    assert "match_result" in r.json()

    r = client.patch(f"/api/v1/ats/applications/{app_id}", json={"status": "shortlisted", "notes": "good"}, headers=tok)
    assert r.status_code == 200
    assert r.json()["status"] == "shortlisted"

    # other recruiter (different org) cannot see it — 404, no existence leak
    other = _register("other@t.com", "recruiter")
    r = client.get(f"/api/v1/ats/jobs/{job['id']}/applications", headers=_auth(other["token"]))
    assert r.status_code == 404

    # export csv
    r = client.get(f"/api/v1/ats/jobs/{job['id']}/export.csv", headers=tok)
    assert r.status_code == 200
    assert "candidate_name" in r.text


def test_candidate_apply_flow(recruiter, candidate):
    tok_r = _auth(recruiter["token"])
    r = client.post("/api/v1/ats/jobs", json={"title": "ML Engineer", "description": SAMPLE_JD}, headers=tok_r)
    job_id = r.json()["id"]

    docx_bytes = _make_docx_bytes(SAMPLE_RESUME_TEXT)
    r = client.post(
        f"/api/v1/ats/jobs/{job_id}/apply",
        files=[("file", ("jane.docx", docx_bytes, "application/octet-stream"))],
        headers=_auth(candidate["token"]),
    )
    assert r.status_code == 200
    assert r.json()["candidate_email"] == "cand@t.com"

    # duplicate apply -> 409
    r = client.post(
        f"/api/v1/ats/jobs/{job_id}/apply",
        files=[("file", ("jane.docx", docx_bytes, "application/octet-stream"))],
        headers=_auth(candidate["token"]),
    )
    assert r.status_code == 409

    # candidate sees own application
    r = client.get("/api/v1/ats/me/applications", headers=_auth(candidate["token"]))
    assert r.status_code == 200
    assert len(r.json()["applications"]) >= 1

    # candidate cannot patch application status
    app_id = r.json()["applications"][0]["id"]
    r = client.patch(f"/api/v1/ats/applications/{app_id}", json={"status": "rejected"}, headers=_auth(candidate["token"]))
    assert r.status_code == 403


def test_screen_rejects_bad_file(recruiter):
    tok = _auth(recruiter["token"])
    r = client.post("/api/v1/ats/jobs", json={"title": "Dev2", "description": SAMPLE_JD}, headers=tok)
    job_id = r.json()["id"]
    r = client.post(
        f"/api/v1/ats/jobs/{job_id}/screen",
        files=[("files", ("evil.exe", b"MZ\x90\x00", "application/octet-stream"))],
        headers=tok,
    )
    assert r.status_code == 200
    assert r.json()["screened"] == 0
    assert len(r.json()["errors"]) == 1


def test_analytics(recruiter):
    r = client.get("/api/v1/ats/analytics", headers=_auth(recruiter["token"]))
    assert r.status_code == 200
    assert r.json()["total_jobs"] >= 2
