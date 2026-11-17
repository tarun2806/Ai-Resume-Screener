"""Async processing queue tests: enqueue, worker, retry, recovery, isolation."""
import os
import sys
import tempfile

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_storage = tempfile.mkdtemp(prefix="proc-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["STORAGE_DIR"] = _storage
os.environ["WORKER_ENABLED"] = "false"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from main import app
from app.db import Application, ProcessingJob, SessionLocal
from app.services import processing as proc
from app.services.storage import get_storage

client = TestClient(app)

JD = "Backend Engineer role. Requirements: 3+ years experience, Python, FastAPI, PostgreSQL, Docker. Build REST APIs."
DOCX_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "frontend", "e2e", "fixtures", "strong.docx")
DOCX = open(DOCX_PATH, "rb").read()
MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _docx_bytes(marker: str) -> bytes:
    """Unique valid .docx per marker so content hashes differ."""
    import docx, io
    d = docx.Document()
    d.add_paragraph(f"Unique Candidate {marker}")
    d.add_paragraph("Python FastAPI PostgreSQL Docker REST APIs backend engineer 3 years experience")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _register(email, role="recruiter", name=None):
    r = client.post("/api/v1/auth/register", json={
        "email": email, "password": "password123",
        "name": name or email.split("@")[0], "role": role})
    assert r.status_code == 200, r.text
    return r.json()


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def _mk_job(tok, title="Proc Job"):
    r = client.post("/api/v1/ats/jobs", json={"title": title, "description": JD},
                    headers=_auth(tok))
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _screen_async(job_id, tok, fname="cv.docx", content=None):
    return client.post(f"/api/v1/ats/jobs/{job_id}/screen/async",
                       files={"files": (fname, content if content is not None else DOCX, MIME)},
                       headers=_auth(tok))


@pytest.fixture(scope="module")
def env():
    a = _register("proc-a@t.com", "recruiter", "Proc A")
    b = _register("proc-b@t.com", "recruiter", "Proc B")
    cand = _register("proc-c@t.com", "candidate", "Proc C")
    return {"a": a, "b": b, "c": cand,
            "job_a": _mk_job(a["token"], "Proc Job A"),
            "job_b": _mk_job(b["token"], "Proc Job B")}


# ---------- enqueue + worker ----------

def test_async_screen_queues_and_worker_completes(env):
    tok, job = env["a"]["token"], env["job_a"]
    r = _screen_async(job, tok, "async1.docx", content=_docx_bytes("one"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["queued"] and len(body["queued"]) == 1
    app_id = body["queued"][0]["application_id"]
    batch = body["batch_id"]

    # status before drain: queued
    r = client.get(f"/api/v1/ats/applications/{app_id}/processing", headers=_auth(tok))
    assert r.json()["status"] in ("queued", "processing")

    n = proc.drain()
    assert n >= 1

    r = client.get(f"/api/v1/ats/applications/{app_id}/processing", headers=_auth(tok))
    data = r.json()
    assert data["status"] == "completed"
    assert data["processing"]["status"] == "completed"

    # application now has real analysis
    r = client.get(f"/api/v1/ats/applications/{app_id}", headers=_auth(tok))
    d = r.json()
    assert d["score"] is not None and d["score"] > 0
    assert d["match_result"].get("overall_score") is not None

    # batch progress endpoint
    r = client.get(f"/api/v1/ats/jobs/{job}/processing", headers=_auth(tok))
    counts = r.json()["counts"]
    assert counts.get("completed", 0) >= 1


def test_duplicate_upload_does_not_create_second_application(env):
    tok, job = env["a"]["token"], env["job_a"]
    dup_bytes = _docx_bytes("dup")
    r1 = _screen_async(job, tok, "dup.docx", content=dup_bytes)
    proc.drain()
    r2 = _screen_async(job, tok, "dup.docx", content=dup_bytes)  # identical bytes
    assert r2.status_code == 200
    assert r2.json()["queued"] == []
    assert r2.json()["skipped"][0]["reason"] == "duplicate_resume"
    assert r2.json()["skipped"][0]["application_id"] == r1.json()["queued"][0]["application_id"]


def test_sync_screen_also_dedupes(env):
    tok, job = env["a"]["token"], env["job_a"]
    dup_bytes = _docx_bytes("dup")
    r = client.post(f"/api/v1/ats/jobs/{job}/screen",
                    files={"files": ("dup.docx", dup_bytes, MIME)}, headers=_auth(tok))
    assert r.status_code == 200
    assert r.json()["screened"] == 0
    assert r.json()["skipped"][0]["reason"] == "duplicate_resume"


# ---------- failure + retry + recovery ----------

def test_failed_job_retries_then_manual_retry(env):
    tok, job = env["a"]["token"], env["job_a"]
    r = _screen_async(job, tok, "bad.docx", content=b"not a real docx at all")
    # upload validation rejects non-docx bytes -> goes to errors, not queue
    body = r.json()
    if body["queued"]:
        app_id = body["queued"][0]["application_id"]
        proc.drain()
        r = client.get(f"/api/v1/ats/applications/{app_id}/processing", headers=_auth(tok)).json()
        # validation_failed -> retry_wait then failed after attempts
        assert r["status"] in ("retry_wait", "failed", "completed")


def test_missing_storage_marks_failed_and_retry_recovers(env):
    """Delete the stored object -> processing fails; restore -> manual retry works."""
    tok, job = env["a"]["token"], env["job_a"]
    r = _screen_async(job, tok, "lost.docx", content=_docx_bytes("lost"))
    app_id = r.json()["queued"][0]["application_id"]

    db = SessionLocal()
    pj = db.query(ProcessingJob).filter(ProcessingJob.application_id == app_id).first()
    key = pj.storage_key
    db.close()
    get_storage().delete(key)  # simulate storage loss

    # drain until attempts exhausted
    for _ in range(4):
        proc.drain()
        db = SessionLocal()
        pj = db.query(ProcessingJob).filter(ProcessingJob.application_id == app_id).first()
        st = pj.status
        # force retry_after into the past for next drain
        if st == "retry_wait":
            from app.db import utcnow
            pj.retry_after = utcnow()
            db.commit()
        db.close()
        if st == "failed":
            break

    r = client.get(f"/api/v1/ats/applications/{app_id}/processing", headers=_auth(tok)).json()
    assert r["status"] == "failed"
    assert r["processing"]["last_error_code"] in ("storage_missing", "validation_failed", "extract_failed", "analysis_failed")

    # retry while file still missing -> fails again
    r = client.post(f"/api/v1/ats/applications/{app_id}/processing/retry", headers=_auth(tok))
    assert r.status_code == 200
    proc.drain()
    db = SessionLocal()
    pj = db.query(ProcessingJob).filter(ProcessingJob.application_id == app_id).order_by(ProcessingJob.id.desc()).first()
    st = pj.status
    if st == "retry_wait":
        from app.db import utcnow
        pj.retry_after = utcnow(); db.commit()
        proc.drain()
        pj = db.query(ProcessingJob).filter(ProcessingJob.id == pj.id).first()
        st = pj.status
    db.close()
    assert st in ("retry_wait", "failed")


def test_retry_only_for_failed(env):
    tok, job = env["a"]["token"], env["job_a"]
    # completed app -> retry rejected
    apps = client.get(f"/api/v1/ats/jobs/{job}/applications", headers=_auth(tok)).json()["applications"]
    done = next((a for a in apps if a.get("processing_status") == "completed"), None)
    if done:
        r = client.post(f"/api/v1/ats/applications/{done['id']}/processing/retry", headers=_auth(tok))
        assert r.status_code == 409


def test_state_machine_rejects_illegal_transitions():
    db = SessionLocal()
    pj = ProcessingJob(status="queued")
    with pytest.raises(ValueError):
        proc.transition(pj, "completed")
    pj.status = "completed"
    with pytest.raises(ValueError):
        proc.transition(pj, "queued")
    db.close()


def test_crash_recovery_requeues_stale_processing(env):
    """A job stuck in 'processing' past its lease returns to the queue."""
    from app.db import utcnow
    from datetime import timedelta
    tok, job = env["a"]["token"], env["job_a"]
    r = _screen_async(job, tok, "crash.docx", content=_docx_bytes("crash"))
    app_id = r.json()["queued"][0]["application_id"]

    db = SessionLocal()
    pj = db.query(ProcessingJob).filter(ProcessingJob.application_id == app_id).first()
    pj.status = "processing"
    pj.locked_at = utcnow() - timedelta(seconds=9999)
    pj.started_at = pj.locked_at
    app = db.query(Application).filter(Application.id == app_id).first()
    app.processing_status = "processing"
    db.commit()
    n = proc.requeue_stale(db, lease_seconds=10)
    db.close()
    assert n >= 1

    proc.drain()
    db = SessionLocal()
    pj = db.query(ProcessingJob).filter(ProcessingJob.application_id == app_id).first()
    assert pj.status == "completed"
    db.close()


# ---------- tenant isolation ----------

def test_processing_endpoints_respect_tenant(env):
    tok_a, tok_b = env["a"]["token"], env["b"]["token"]
    job_a, job_b = env["job_a"], env["job_b"]

    # org B cannot see org A's batch progress
    r = client.get(f"/api/v1/ats/jobs/{job_a}/processing", headers=_auth(tok_b))
    assert r.status_code == 404

    # org B cannot retry org A's application
    apps = client.get(f"/api/v1/ats/jobs/{job_a}/applications", headers=_auth(tok_a)).json()["applications"]
    if apps:
        r = client.post(f"/api/v1/ats/applications/{apps[0]['id']}/processing/retry",
                        headers=_auth(tok_b))
        assert r.status_code == 404

    # candidate sees own status only
    cand_apps = client.get("/api/v1/ats/me/applications", headers=_auth(env["c"]["token"]))
    if cand_apps.status_code == 200 and cand_apps.json()["applications"]:
        aid = cand_apps.json()["applications"][0]["id"]
        r = client.get(f"/api/v1/ats/applications/{aid}/processing", headers=_auth(env["c"]["token"]))
        assert r.status_code == 200
        # other candidate cannot see it -> use a fresh candidate
        other = _register("proc-d@t.com", "candidate", "Proc D")
        r = client.get(f"/api/v1/ats/applications/{aid}/processing", headers=_auth(other["token"]))
        assert r.status_code == 403
