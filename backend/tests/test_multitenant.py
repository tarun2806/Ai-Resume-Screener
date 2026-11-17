"""Multi-tenant isolation tests: organizations, memberships, invitations."""
import os
import sys
import tempfile

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["JWT_SECRET"] = "test-secret"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

JD = "Backend Engineer role. Requirements: 3+ years experience, Python, FastAPI, PostgreSQL, Docker. Build REST APIs."
RESUME = "Test Person\nt@t.com\n\nExperience\nEngineer 2019-Present\n- Python FastAPI PostgreSQL Docker REST APIs\n\nSkills\nPython, FastAPI, PostgreSQL, Docker"


def _register(email, role="recruiter", name=None):
    r = client.post("/api/v1/auth/register", json={
        "email": email, "password": "password123",
        "name": name or email.split("@")[0], "role": role})
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


@pytest.fixture(scope="module")
def orgs():
    """Two independent organizations with jobs + screened applicants."""
    a = _register("owner-a@t.com", "recruiter", "Owner A")
    b = _register("owner-b@t.com", "recruiter", "Owner B")

    def make_job(tok, title):
        r = client.post("/api/v1/ats/jobs", json={
            "title": title, "description": JD, "location": "Remote"}, headers=_auth(tok))
        assert r.status_code == 200, r.text
        return r.json()

    job_a = make_job(a["token"], "Org A Backend Role")
    job_b = make_job(b["token"], "Org B Backend Role")

    docx_bytes = _docx(RESUME)
    for tok, job in ((a["token"], job_a), (b["token"], job_b)):
        r = client.post(f"/api/v1/ats/jobs/{job['id']}/screen",
                        files=[("files", ("r.docx", docx_bytes, "application/octet-stream"))],
                        headers=_auth(tok))
        assert r.status_code == 200, r.text
        assert r.json()["screened"] == 1

    apps_a = client.get(f"/api/v1/ats/jobs/{job_a['id']}/applications", headers=_auth(a["token"])).json()["applications"]
    apps_b = client.get(f"/api/v1/ats/jobs/{job_b['id']}/applications", headers=_auth(b["token"])).json()["applications"]

    return {
        "a": a, "b": b, "job_a": job_a, "job_b": job_b,
        "app_a": apps_a[0], "app_b": apps_b[0],
    }


# ---------- cross-tenant isolation ----------

def test_cross_org_job_list_isolated(orgs):
    r = client.get("/api/v1/ats/jobs", headers=_auth(orgs["a"]["token"]))
    titles = [j["title"] for j in r.json()["jobs"]]
    assert "Org A Backend Role" in titles
    assert "Org B Backend Role" not in titles


def test_cross_org_job_detail_404(orgs):
    r = client.get(f"/api/v1/ats/jobs/{orgs['job_b']['id']}", headers=_auth(orgs["a"]["token"]))
    assert r.status_code == 404


def test_cross_org_applications_404(orgs):
    r = client.get(f"/api/v1/ats/jobs/{orgs['job_b']['id']}/applications", headers=_auth(orgs["a"]["token"]))
    assert r.status_code == 404


def test_cross_org_application_detail_404(orgs):
    r = client.get(f"/api/v1/ats/applications/{orgs['app_b']['id']}", headers=_auth(orgs["a"]["token"]))
    assert r.status_code == 404


def test_cross_org_status_update_404(orgs):
    r = client.patch(f"/api/v1/ats/applications/{orgs['app_b']['id']}",
                     json={"status": "rejected"}, headers=_auth(orgs["a"]["token"]))
    assert r.status_code == 404


def test_cross_org_export_404(orgs):
    r = client.get(f"/api/v1/ats/jobs/{orgs['job_b']['id']}/export.csv", headers=_auth(orgs["a"]["token"]))
    assert r.status_code == 404


def test_cross_org_insights_404(orgs):
    r = client.get(f"/api/v1/ats/jobs/{orgs['job_b']['id']}/insights", headers=_auth(orgs["a"]["token"]))
    assert r.status_code == 404


def test_cross_org_compare_404(orgs):
    r = client.get(f"/api/v1/ats/jobs/{orgs['job_b']['id']}/compare?ids={orgs['app_b']['id']}",
                   headers=_auth(orgs["a"]["token"]))
    assert r.status_code == 404


def test_cross_org_analytics_isolated(orgs):
    r = client.get("/api/v1/ats/analytics", headers=_auth(orgs["a"]["token"]))
    titles = [j["title"] for j in r.json()["per_job"]]
    assert "Org A Backend Role" in titles
    assert "Org B Backend Role" not in titles


def test_cross_org_job_update_404(orgs):
    r = client.patch(f"/api/v1/ats/jobs/{orgs['job_b']['id']}",
                     json={"title": "Hijacked", "description": JD}, headers=_auth(orgs["a"]["token"]))
    assert r.status_code == 404
    # verify unchanged
    r2 = client.get(f"/api/v1/ats/jobs/{orgs['job_b']['id']}", headers=_auth(orgs["b"]["token"]))
    assert r2.json()["title"] == "Org B Backend Role"


def test_cross_org_screen_404(orgs):
    docx_bytes = _docx(RESUME)
    r = client.post(f"/api/v1/ats/jobs/{orgs['job_b']['id']}/screen",
                    files=[("files", ("x.docx", docx_bytes, "application/octet-stream"))],
                    headers=_auth(orgs["a"]["token"]))
    assert r.status_code == 404


# ---------- org workflows ----------

def test_create_second_org_and_job_scoping(orgs):
    tok = orgs["a"]["token"]
    r = client.post("/api/v1/orgs", json={"name": "Org A Second"}, headers=_auth(tok))
    assert r.status_code == 200
    org2 = r.json()
    assert org2["my_role"] == "owner"

    # user now belongs to 2 orgs; job created goes to FIRST org by default
    r = client.post("/api/v1/ats/jobs", json={"title": "Second Org Job", "description": JD},
                    headers=_auth(tok))
    assert r.status_code == 200

    # X-Org-Id selects the second org for listing
    h = {**_auth(tok), "X-Org-Id": str(org2["id"])}
    r = client.get("/api/v1/ats/jobs", headers=h)
    titles = [j["title"] for j in r.json()["jobs"]]
    assert "Second Org Job" not in titles  # created under org 1 (default)
    assert "Org A Backend Role" not in titles  # org 2 has no jobs yet

    # invalid org id rejected
    h_bad = {**_auth(tok), "X-Org-Id": "99999"}
    r = client.post("/api/v1/ats/jobs", json={"title": "Bad Org Job", "description": JD}, headers=h_bad)
    assert r.status_code == 403


def test_invite_accept_flow_and_single_use(orgs):
    tok_a = orgs["a"]["token"]
    org_a_id = orgs["job_a"]["id"]  # placeholder; fetch real org id below

    orgs_list = client.get("/api/v1/orgs", headers=_auth(tok_a)).json()["organizations"]
    org_id = orgs_list[0]["id"]

    # invite a new recruiter
    inv = client.post(f"/api/v1/orgs/{org_id}/invites",
                      json={"email": "newrecruit@t.com", "role": "recruiter"},
                      headers=_auth(tok_a))
    assert inv.status_code == 200
    token = inv.json()["token"]

    # new user registers and accepts
    new = _register("newrecruit@t.com", "recruiter", "New Recruit")
    r = client.post("/api/v1/orgs/invites/accept", json={"token": token}, headers=_auth(new["token"]))
    assert r.status_code == 200
    assert r.json()["role"] == "recruiter"

    # token cannot be reused
    r = client.post("/api/v1/orgs/invites/accept", json={"token": token}, headers=_auth(new["token"]))
    assert r.status_code in (404, 409)

    # new member can now see org A's job
    r = client.get(f"/api/v1/ats/jobs/{orgs['job_a']['id']}", headers=_auth(new["token"]))
    assert r.status_code == 200
    # but still cannot see org B's job
    r = client.get(f"/api/v1/ats/jobs/{orgs['job_b']['id']}", headers=_auth(new["token"]))
    assert r.status_code == 404


def test_invite_wrong_email_rejected(orgs):
    tok_a = orgs["a"]["token"]
    orgs_list = client.get("/api/v1/orgs", headers=_auth(tok_a)).json()["organizations"]
    org_id = orgs_list[0]["id"]
    inv = client.post(f"/api/v1/orgs/{org_id}/invites",
                      json={"email": "someone-else@t.com", "role": "viewer"},
                      headers=_auth(tok_a)).json()
    other = _register("wrong-person@t.com", "recruiter", "Wrong")
    r = client.post("/api/v1/orgs/invites/accept", json={"token": inv["token"]},
                    headers=_auth(other["token"]))
    assert r.status_code == 403


def test_member_removal_loses_access(orgs):
    tok_a = orgs["a"]["token"]
    orgs_list = client.get("/api/v1/orgs", headers=_auth(tok_a)).json()["organizations"]
    org_id = orgs_list[0]["id"]

    # invite + accept a viewer
    inv = client.post(f"/api/v1/orgs/{org_id}/invites",
                      json={"email": "viewer@t.com", "role": "viewer"},
                      headers=_auth(tok_a)).json()
    viewer = _register("viewer@t.com", "recruiter", "Viewer")
    client.post("/api/v1/orgs/invites/accept", json={"token": inv["token"]},
                headers=_auth(viewer["token"]))

    # viewer can READ job detail
    r = client.get(f"/api/v1/ats/jobs/{orgs['job_a']['id']}", headers=_auth(viewer["token"]))
    assert r.status_code == 200

    # viewer CANNOT write (screen is a write op)
    docx_bytes = _docx(RESUME)
    r = client.post(f"/api/v1/ats/jobs/{orgs['job_a']['id']}/screen",
                    files=[("files", ("v.docx", docx_bytes, "application/octet-stream"))],
                    headers=_auth(viewer["token"]))
    assert r.status_code == 403

    # owner removes viewer -> access gone entirely
    detail = client.get(f"/api/v1/orgs/{org_id}", headers=_auth(tok_a)).json()
    viewer_uid = next(m["user_id"] for m in detail["members"] if m["email"] == "viewer@t.com")
    r = client.delete(f"/api/v1/orgs/{org_id}/members/{viewer_uid}", headers=_auth(tok_a))
    assert r.status_code == 200

    r = client.get(f"/api/v1/ats/jobs/{orgs['job_a']['id']}", headers=_auth(viewer["token"]))
    assert r.status_code == 404


def test_candidate_applies_across_orgs(orgs):
    cand = _register("global-cand@t.com", "candidate", "Global Cand")
    # apply to org B's job (candidate is global, not an org member)
    docx_bytes = _docx(RESUME)
    r = client.post(f"/api/v1/ats/jobs/{orgs['job_b']['id']}/apply",
                    files=[("file", ("c.docx", docx_bytes, "application/octet-stream"))],
                    headers=_auth(cand["token"]))
    assert r.status_code == 200
    # candidate sees it in my applications
    r = client.get("/api/v1/ats/me/applications", headers=_auth(cand["token"]))
    assert any(a["job_id"] == orgs["job_b"]["id"] for a in r.json()["applications"])
    # candidate cannot see org analytics
    r = client.get(f"/api/v1/orgs/{orgs['job_b']['id']}/analytics", headers=_auth(cand["token"]))
    # job_b id is not org id — use real org id
    orgs_b = client.get("/api/v1/orgs", headers=_auth(orgs["b"]["token"])).json()["organizations"]
    r = client.get(f"/api/v1/orgs/{orgs_b[0]['id']}/analytics", headers=_auth(cand["token"]))
    assert r.status_code in (403, 404)


def test_org_analytics_scoped(orgs):
    orgs_a = client.get("/api/v1/orgs", headers=_auth(orgs["a"]["token"])).json()["organizations"]
    org_id_a = orgs_a[0]["id"]
    r = client.get(f"/api/v1/orgs/{org_id_a}/analytics", headers=_auth(orgs["a"]["token"]))
    assert r.status_code == 200
    assert r.json()["total_jobs"] >= 1
    # org B member cannot read org A analytics
    r = client.get(f"/api/v1/orgs/{org_id_a}/analytics", headers=_auth(orgs["b"]["token"]))
    assert r.status_code in (403, 404)


def test_non_member_cannot_manage_org(orgs):
    # recruiter B tries to invite into org A
    orgs_a = client.get("/api/v1/orgs", headers=_auth(orgs["a"]["token"])).json()["organizations"]
    r = client.post(f"/api/v1/orgs/{orgs_a[0]['id']}/invites",
                    json={"email": "x@t.com", "role": "recruiter"},
                    headers=_auth(orgs["b"]["token"]))
    assert r.status_code == 403


def test_last_owner_cannot_be_removed(orgs):
    orgs_a = client.get("/api/v1/orgs", headers=_auth(orgs["a"]["token"])).json()["organizations"]
    org_id = orgs_a[0]["id"]
    detail = client.get(f"/api/v1/orgs/{org_id}", headers=_auth(orgs["a"]["token"])).json()
    owner_uid = next(m["user_id"] for m in detail["members"] if m["role"] == "owner")
    r = client.delete(f"/api/v1/orgs/{org_id}/members/{owner_uid}", headers=_auth(orgs["a"]["token"]))
    assert r.status_code == 400
