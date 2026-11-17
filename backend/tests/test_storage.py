"""Private resume storage tests: keys, traversal, download auth, retention."""
import io
import os
import sys
import tempfile

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_storage = tempfile.mkdtemp(prefix="resumes-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["STORAGE_DIR"] = _storage
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from main import app
from app.services.storage import (
    LocalStorage, StorageError, generate_key, get_storage, validate_key,
)

client = TestClient(app)

JD = "Backend Engineer role. Requirements: 3+ years experience, Python, FastAPI, PostgreSQL, Docker. Build REST APIs."
RESUME_TEXT = "Test Person\nt@t.com\n\nExperience\nEngineer 2019-Present\n- Python FastAPI PostgreSQL Docker REST APIs\n\nSkills\nPython, FastAPI, PostgreSQL, Docker"


def _register(email, role="recruiter", name=None):
    r = client.post("/api/v1/auth/register", json={
        "email": email, "password": "password123",
        "name": name or email.split("@")[0], "role": role})
    assert r.status_code == 200, r.text
    return r.json()


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


DOCX_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "frontend", "e2e", "fixtures", "strong.docx")
DOCX_BYTES = open(DOCX_PATH, "rb").read() if os.path.exists(DOCX_PATH) else None


def _upload_resume(job_id, token, filename="cv.docx"):
    assert DOCX_BYTES, "missing strong.docx fixture"
    return client.post(f"/api/v1/ats/jobs/{job_id}/screen",
                       files={"files": (filename, DOCX_BYTES,
                                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                       headers=_auth(token))


@pytest.fixture(scope="module")
def env():
    rec_a = _register("stor-a@t.com", "recruiter", "Stor A")
    rec_b = _register("stor-b@t.com", "recruiter", "Stor B")
    cand = _register("stor-c@t.com", "candidate", "Stor C")

    def mk_job(tok, title):
        r = client.post("/api/v1/ats/jobs", json={"title": title, "description": JD},
                        headers=_auth(tok))
        assert r.status_code == 200, r.text
        return r.json()["id"]

    job_a = mk_job(rec_a["token"], "Storage Job A")
    job_b = mk_job(rec_b["token"], "Storage Job B")
    return {"a": rec_a, "b": rec_b, "c": cand, "job_a": job_a, "job_b": job_b}


# ---------- unit: keys & traversal ----------

def test_key_generation_is_opaque_and_tenant_namespaced():
    k1 = generate_key(7, ".pdf")
    k2 = generate_key(7, ".pdf")
    assert k1 != k2
    assert k1.startswith("7/")
    assert "@" not in k1 and " " not in k1
    # PII-looking input is irrelevant - keys never contain names/emails
    assert "stor" not in k1.lower()


def test_validate_key_rejects_traversal():
    for bad in ["../etc/passwd", "a/../../b.pdf", "/abs/path.pdf", "x.exe",
                "noext", "", "a b.pdf", "..%2f.pdf"]:
        with pytest.raises(StorageError):
            validate_key(bad)
    assert validate_key("3/abc123.pdf") == "3/abc123.pdf"


def test_local_storage_roundtrip_and_delete():
    st = LocalStorage(tempfile.mkdtemp())
    key = generate_key(1, ".docx")
    payload = b"PK\x03\x04fake"
    st.put(key, payload)
    assert st.get(key) == payload
    assert st.exists(key)
    st.delete(key)
    assert not st.exists(key)
    st.delete(key)  # idempotent


# ---------- API: storage on screen + download auth ----------

def test_screen_stores_original_and_download_authorized(env):
    tok_a, job_a = env["a"]["token"], env["job_a"]
    r = _upload_resume(job_a, tok_a, "alice-cv.docx")
    assert r.status_code == 200, r.text
    assert r.json()["screened"] == 1

    apps = client.get(f"/api/v1/ats/jobs/{job_a}/applications", headers=_auth(tok_a)).json()["applications"]
    assert apps, "expected an application"
    app_id = apps[0]["id"]

    # owner-org recruiter can download
    r = client.get(f"/api/v1/ats/applications/{app_id}/resume", headers=_auth(tok_a))
    assert r.status_code == 200
    assert r.content[:2] == b"PK"
    assert "alice-cv.docx" in r.headers.get("content-disposition", "")

    # cross-tenant recruiter cannot even see the application (404 on job)
    r = client.get(f"/api/v1/ats/applications/{app_id}/resume", headers=_auth(env["b"]["token"]))
    assert r.status_code == 404

    # unrelated candidate cannot download
    r = client.get(f"/api/v1/ats/applications/{app_id}/resume", headers=_auth(env["c"]["token"]))
    assert r.status_code == 403


def test_candidate_apply_stores_and_self_download(env):
    cand, job_a = env["c"], env["job_a"]
    assert DOCX_BYTES, "missing strong.docx fixture"
    r = client.post(f"/api/v1/ats/jobs/{job_a}/apply",
                    files={"file": ("cand.docx", DOCX_BYTES,
                                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                    headers=_auth(cand["token"]))
    assert r.status_code == 200, r.text
    app_id = r.json()["id"]

    r = client.get(f"/api/v1/ats/applications/{app_id}/resume", headers=_auth(cand["token"]))
    assert r.status_code == 200
    assert r.content[:2] == b"PK"

    # storage key is opaque (uuid), not filename-derived
    from app.db import Application, SessionLocal
    db = SessionLocal()
    app_row = db.query(Application).filter(Application.id == app_id).first()
    assert app_row.resume_storage_key
    assert app_row.resume_filename == "cand.docx"
    assert app_row.resume_storage_key.split("/")[-1] != "cand.docx"
    key = app_row.resume_storage_key
    db.close()
    assert get_storage().exists(key)


def test_retention_purge_deletes_stored_files(env):
    """Purge removes the object from private storage, not just DB text."""
    from app.db import Application, SessionLocal, utcnow
    from datetime import timedelta

    # age an application beyond retention
    db = SessionLocal()
    app_row = db.query(Application).filter(Application.resume_filename == "cand.docx").first()
    assert app_row and app_row.resume_storage_key
    key = app_row.resume_storage_key
    app_row.created_at = utcnow() - timedelta(days=400)
    db.commit()
    db.close()

    from app.db import User
    adm = _register("stor-admin@t.com", "recruiter", "Stor Admin")
    db2 = SessionLocal()
    u = db2.query(User).filter(User.email == "stor-admin@t.com").first()
    u.role = "admin"
    db2.commit(); db2.close()
    r = client.post("/api/v1/ats/admin/maintenance/purge-resume-text",
                    headers=_auth(adm["token"]))
    assert r.status_code == 200, r.text
    assert r.json()["purged"] >= 1
    assert not get_storage().exists(key)
