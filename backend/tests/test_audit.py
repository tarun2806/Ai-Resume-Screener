"""Audit logging, application history, metrics, and malware-scanning tests."""
import os
import socket
import sys
import tempfile
import threading

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_storage = tempfile.mkdtemp(prefix="audit-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["STORAGE_DIR"] = _storage
os.environ["WORKER_ENABLED"] = "false"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from main import app
from app.db import Application, AuditEvent, SessionLocal, User

client = TestClient(app)

JD = "Backend Engineer role. Requirements: 3+ years experience, Python, FastAPI, PostgreSQL, Docker. Build REST APIs."
DOCX_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "frontend", "e2e", "fixtures", "strong.docx")
DOCX = open(DOCX_PATH, "rb").read()
MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _register(email, role="recruiter", name=None):
    r = client.post("/api/v1/auth/register", json={
        "email": email, "password": "password123",
        "name": name or email.split("@")[0], "role": role})
    assert r.status_code == 200, r.text
    return r.json()


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def _mk_job(tok, title="Audit Job"):
    r = client.post("/api/v1/ats/jobs", json={"title": title, "description": JD},
                    headers=_auth(tok))
    assert r.status_code == 200, r.text
    return r.json()["id"]


@pytest.fixture(scope="module")
def env():
    a = _register("aud-a@t.com", "recruiter", "Aud A")
    b = _register("aud-b@t.com", "recruiter", "Aud B")
    return {"a": a, "b": b, "job_a": _mk_job(a["token"], "Audit Job A")}


def _events(action=None, resource_type=None):
    db = SessionLocal()
    q = db.query(AuditEvent)
    if action:
        q = q.filter(AuditEvent.action == action)
    if resource_type:
        q = q.filter(AuditEvent.resource_type == resource_type)
    out = [(e.action, e.resource_type, e.resource_id, e.outcome, e.organization_id)
           for e in q.all()]
    db.close()
    return out


# ---------- audit recording ----------

def test_register_login_and_job_events_recorded(env):
    acts = [a for a, *_ in _events()]
    assert "user_registered" in acts
    assert "login_success" in acts or "user_registered" in acts
    assert "job_created" in acts
    # org auto-provisioning audited
    assert "org_created" in acts


def test_login_failure_audited_as_denied():
    r = client.post("/api/v1/auth/login",
                    json={"email": "nobody@t.com", "password": "wrongpass1"})
    assert r.status_code == 401
    evs = _events(action="login_failed")
    assert evs and evs[-1][3] == "denied"


def test_org_workflow_events_recorded(env):
    tok = env["a"]["token"]
    orgs = client.get("/api/v1/orgs", headers=_auth(tok)).json()["organizations"]
    oid = orgs[0]["id"]
    inv = client.post(f"/api/v1/orgs/{oid}/invites",
                      json={"email": "newmember@t.com", "role": "viewer"},
                      headers=_auth(tok))
    assert inv.status_code == 200
    acts = [a for a, *_ in _events()]
    assert "invite_created" in acts


def test_screen_and_status_change_events(env):
    tok, job = env["a"]["token"], env["job_a"]
    r = client.post(f"/api/v1/ats/jobs/{job}/screen",
                    files={"files": ("aud.docx", DOCX, MIME)}, headers=_auth(tok))
    assert r.status_code == 200 and r.json()["screened"] == 1
    apps = client.get(f"/api/v1/ats/jobs/{job}/applications", headers=_auth(tok)).json()["applications"]
    aid = apps[0]["id"]
    r = client.patch(f"/api/v1/ats/applications/{aid}",
                     json={"status": "shortlisted", "notes": "good"}, headers=_auth(tok))
    assert r.status_code == 200
    acts = [a for a, *_ in _events()]
    assert "screening_submitted" in acts
    app_acts = [a for a, rt, *_ in _events(resource_type="application")]
    assert "application_status_changed" in app_acts
    assert "application_notes_updated" in app_acts


def test_resume_download_audited(env):
    tok, job = env["a"]["token"], env["job_a"]
    apps = client.get(f"/api/v1/ats/jobs/{job}/applications", headers=_auth(tok)).json()["applications"]
    aid = apps[0]["id"]
    client.get(f"/api/v1/ats/applications/{aid}/resume", headers=_auth(tok))
    assert "resume_downloaded" in [a for a, *_ in _events(resource_type="application")]


def test_audit_metadata_has_no_secrets():
    db = SessionLocal()
    for e in db.query(AuditEvent).all():
        meta = e.metadata_json or ""
        for bad in ("password", "token", "Bearer", "pbkdf2"):
            assert bad not in meta.lower(), f"secret-like data in audit metadata: {meta[:200]}"
    db.close()


# ---------- org audit isolation ----------

def test_org_audit_isolation(env):
    tok_a, tok_b = env["a"]["token"], env["b"]["token"]
    orgs_a = client.get("/api/v1/orgs", headers=_auth(tok_a)).json()["organizations"]
    oid_a = orgs_a[0]["id"]

    # org A admin can read own audit
    r = client.get(f"/api/v1/orgs/{oid_a}/audit", headers=_auth(tok_a))
    assert r.status_code == 200
    assert r.json()["events"]

    # org B owner is not admin of org A -> 403
    r = client.get(f"/api/v1/orgs/{oid_a}/audit", headers=_auth(tok_b))
    assert r.status_code == 403

    # non-member recruiter also denied
    r = client.get(f"/api/v1/orgs/{oid_a}/audit", headers=_auth(_register("aud-c@t.com", "recruiter")["token"]))
    assert r.status_code == 403


# ---------- application history ----------

def test_application_history_timeline(env):
    tok, job = env["a"]["token"], env["job_a"]
    apps = client.get(f"/api/v1/ats/jobs/{job}/applications", headers=_auth(tok)).json()["applications"]
    aid = apps[0]["id"]
    r = client.get(f"/api/v1/ats/applications/{aid}/history", headers=_auth(tok))
    assert r.status_code == 200
    actions = [e["action"] for e in r.json()["events"]]
    assert "application_status_changed" in actions
    assert "application_notes_updated" in actions

    # cross-tenant recruiter cannot read history
    r = client.get(f"/api/v1/ats/applications/{aid}/history", headers=_auth(env["b"]["token"]))
    assert r.status_code == 404


def test_candidate_sees_own_history_only(env):
    cand = _register("aud-cand@t.com", "candidate", "Aud Cand")
    job = _mk_job(env["a"]["token"], "Cand Apply Job")
    r = client.post(f"/api/v1/ats/jobs/{job}/apply",
                    files={"file": ("cand.docx", DOCX, MIME)},
                    headers=_auth(cand["token"]))
    assert r.status_code == 200, r.text
    aid = r.json()["id"]
    r = client.get(f"/api/v1/ats/applications/{aid}/history", headers=_auth(cand["token"]))
    assert r.status_code == 200
    other = _register("aud-cand2@t.com", "candidate", "Aud Cand2")
    r = client.get(f"/api/v1/ats/applications/{aid}/history", headers=_auth(other["token"]))
    assert r.status_code == 403


# ---------- metrics & health ----------

def _promote_admin(email):
    db = SessionLocal()
    u = db.query(User).filter(User.email == email).first()
    u.role = "admin"
    db.commit(); db.close()


def test_metrics_endpoint_admin_only_and_contents(env):
    # non-admin forbidden
    r = client.get("/api/v1/ats/admin/metrics", headers=_auth(env["a"]["token"]))
    assert r.status_code == 403

    adm = _register("aud-admin@t.com", "recruiter", "Aud Admin")
    _promote_admin("aud-admin@t.com")
    r = client.get("/api/v1/ats/admin/metrics", headers=_auth(adm["token"]))
    assert r.status_code == 200, r.text
    d = r.json()
    assert "api" in d and "requests_total" in d["api"]
    assert "database" in d and "pool" in d["database"]
    assert "worker" in d and "queue_depth" in d["worker"]
    assert "storage" in d and d["storage"]["status"] == "ok"
    assert "scanner" in d


def test_health_endpoints_stay_sanitized():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "checks" in body
    # no internal detail leaked
    assert "pool" not in str(body) and "worker" not in str(body)


def test_request_id_returned():
    r = client.get("/health")
    assert "x-request-id" in {k.lower() for k in r.headers.keys()}


# ---------- audit retention ----------

def test_audit_purge_retention(env):
    from app.db import utcnow
    from datetime import timedelta
    # age one event beyond retention (730d default)
    db = SessionLocal()
    e = db.query(AuditEvent).first()
    assert e
    e.created_at = utcnow() - timedelta(days=800)
    db.commit(); db.close()

    adm = _register("aud-admin2@t.com", "recruiter", "Aud Admin2")
    _promote_admin("aud-admin2@t.com")
    r = client.post("/api/v1/ats/admin/maintenance/purge-audit", headers=_auth(adm["token"]))
    assert r.status_code == 200, r.text
    assert r.json()["purged"] >= 1
