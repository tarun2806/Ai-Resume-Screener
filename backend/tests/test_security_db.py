import os
import sys
import tempfile

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["JWT_SECRET"] = "test-secret-key-that-is-long-enough-32chars"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from main import app
from app.db import SessionLocal, Application, User

client = TestClient(app)


def _register(email, role="candidate", password="password123"):
    r = client.post("/api/v1/auth/register", json={
        "email": email, "password": password, "name": email.split("@")[0], "role": role,
    })
    assert r.status_code == 200, r.text
    return r.json()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _docx(text: str) -> bytes:
    import docx, io
    d = docx.Document()
    for line in text.split("\n"):
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


RESUME = """Test User
t@e.com
Experience
Engineer at X, 2020 - Present
Skills
Python, SQL
"""
JD = "We need an engineer. Requirements: Python, SQL, 2+ years experience. Nice: Docker."


@pytest.fixture(scope="module")
def env():
    rec = _register("sec-rec@t.com", "recruiter")
    cand = _register("sec-cand@t.com", "candidate")
    admin = _register("sec-admin@t.com", "recruiter")
    # promote to admin via direct DB (no admin exists yet to use API)
    db = SessionLocal()
    u = db.query(User).filter(User.email == "sec-admin@t.com").first()
    u.role = "admin"
    db.commit()
    db.close()
    return {"rec": rec, "cand": cand, "admin": admin}


def test_fk_enforcement_blocks_orphan_application(env):
    """SQLite foreign_keys pragma must reject applications with bad job_id."""
    db = SessionLocal()
    try:
        db.add(Application(job_id=999999, candidate_name="ghost"))
        db.commit()
        pytest.fail("orphan application was committed — FK enforcement broken")
    except IntegrityError:
        db.rollback()
    finally:
        db.close()


def test_health_endpoint():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["checks"]["database"] == "ok"


def test_candidate_data_export_and_delete(env):
    cand_tok = _auth(env["cand"]["token"])
    rec_tok = _auth(env["rec"]["token"])

    # recruiter creates job, candidate applies
    r = client.post("/api/v1/ats/jobs", json={"title": "Sec Job", "description": JD}, headers=rec_tok)
    job_id = r.json()["id"]
    r = client.post(
        f"/api/v1/ats/jobs/{job_id}/apply",
        files=[("file", ("c.docx", _docx(RESUME), "application/octet-stream"))],
        headers=cand_tok,
    )
    assert r.status_code == 200

    # export contains user + application
    r = client.get("/api/v1/ats/me/export", headers=cand_tok)
    assert r.status_code == 200
    data = r.json()
    assert data["user"]["email"] == "sec-cand@t.com"
    assert len(data["applications"]) >= 1
    assert "resume_text" in data["applications"][0]

    # recruiter cannot use candidate export (still works but returns their own empty data)
    r = client.get("/api/v1/ats/me/export", headers=rec_tok)
    assert r.status_code == 200

    # delete account
    r = client.delete("/api/v1/ats/me", headers=cand_tok)
    assert r.status_code == 200
    assert r.json()["deleted"] is True

    # token now invalid (user gone)
    r = client.get("/api/v1/ats/me/applications", headers=cand_tok)
    assert r.status_code == 401

    # applications deleted too
    db = SessionLocal()
    remaining = db.query(Application).filter(Application.candidate_email == "sec-cand@t.com").count()
    db.close()
    assert remaining == 0


def test_delete_account_recruiter_forbidden(env):
    r = client.delete("/api/v1/ats/me", headers=_auth(env["rec"]["token"]))
    assert r.status_code == 403


def test_csv_formula_injection_escaped(env):
    rec_tok = _auth(env["rec"]["token"])
    r = client.post("/api/v1/ats/jobs", json={"title": "CSV Job", "description": JD}, headers=rec_tok)
    job_id = r.json()["id"]

    # resume whose "name" line is a formula payload
    evil_resume = "=HYPERLINK(\"http://evil\")\nt@e.com\nSkills\nPython"
    r = client.post(
        f"/api/v1/ats/jobs/{job_id}/screen",
        files=[("files", ("evil.docx", _docx(evil_resume), "application/octet-stream"))],
        headers=rec_tok,
    )
    assert r.status_code == 200

    r = client.get(f"/api/v1/ats/jobs/{job_id}/export.csv", headers=rec_tok)
    assert r.status_code == 200
    for line in r.text.splitlines():
        for cell in line.split(","):
            assert not cell.startswith("="), f"formula injection in CSV: {cell}"


def test_purge_endpoint_admin_only_and_works(env):
    # non-admin forbidden
    r = client.post("/api/v1/ats/admin/maintenance/purge-resume-text",
                    headers=_auth(env["rec"]["token"]))
    assert r.status_code == 403

    # admin allowed
    r = client.post("/api/v1/ats/admin/maintenance/purge-resume-text",
                    headers=_auth(env["admin"]["token"]))
    assert r.status_code == 200
    assert "purged" in r.json()


def test_production_config_validation():
    from app.config import Settings

    prod_bad = Settings(environment="production", jwt_secret="", allowed_origins="", database_url="sqlite:///./x.db")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        prod_bad.validate_production()

    prod_bad2 = Settings(environment="production", jwt_secret="x" * 40,
                         allowed_origins="https://app.example.com",
                         database_url="sqlite:///./x.db")
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        prod_bad2.validate_production()

    prod_good = Settings(environment="production", jwt_secret="x" * 40,
                         allowed_origins="https://app.example.com",
                         database_url="postgresql+psycopg://u:p@h/db")
    prod_good.validate_production()  # must not raise

    dev = Settings(environment="development")
    dev.validate_production()  # must not raise


def test_production_settings_flags():
    from app.config import Settings

    prod = Settings(environment="production", jwt_secret="x" * 40,
                    allowed_origins="https://a.com, https://b.com/",
                    database_url="postgresql+psycopg://u:p@h/db")
    assert prod.is_production
    assert prod.origins_list == ["https://a.com", "https://b.com"]

    dev = Settings(environment="development")
    assert not dev.is_production
    assert "http://localhost:5173" in dev.origins_list
