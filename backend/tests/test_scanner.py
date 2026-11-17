"""Malware scanning tests (ClamAV clamd INSTREAM, fail-closed modes)."""
import os
import socket
import sys
import tempfile
import threading

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_storage = tempfile.mkdtemp(prefix="scanner-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["STORAGE_DIR"] = _storage
os.environ["WORKER_ENABLED"] = "false"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from main import app

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


@pytest.fixture(scope="module")
def env():
    a = _register("scan-a@t.com", "recruiter", "Scan A")
    r = client.post("/api/v1/ats/jobs", json={"title": "Scan Job", "description": JD},
                    headers=_auth(a["token"]))
    assert r.status_code == 200, r.text
    return {"a": a, "job": r.json()["id"]}


class FakeClamd:
    """Minimal clamd INSTREAM responder for tests."""
    def __init__(self, reply: bytes):
        self.reply = reply
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.sock.listen(1)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        try:
            conn, _ = self.sock.accept()
            with conn:
                conn.recv(65536)
                conn.settimeout(2)
                try:
                    while True:
                        d = conn.recv(65536)
                        if not d or b"\x00" in d[-5:]:
                            break
                except socket.timeout:
                    pass
                conn.sendall(self.reply)
        except Exception:
            pass

    def close(self):
        self.sock.close()


def _set_clamav(host="", port=3310, required="false"):
    from app.config import settings
    settings.clamav_host = host
    settings.clamav_port = port
    settings.clamav_required = required == "true"


# ---------- malware scanning ----------

class FakeClamd:
    """Minimal clamd INSTREAM responder for tests."""
    def __init__(self, reply: bytes):
        self.reply = reply
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.sock.listen(1)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        try:
            conn, _ = self.sock.accept()
            with conn:
                conn.recv(65536)  # command + first chunk(s)
                # drain until zero-length chunk seen
                conn.settimeout(2)
                try:
                    while True:
                        d = conn.recv(65536)
                        if not d or b"\x00" in d[-5:]:
                            break
                except socket.timeout:
                    pass
                conn.sendall(self.reply)
        except Exception:
            pass

    def close(self):
        self.sock.close()


def _set_clamav(host="", port=3310, required="false"):
    from app.config import settings
    settings.clamav_host = host
    settings.clamav_port = port
    settings.clamav_required = required == "true"


def test_clamav_clean_scan_passes(env):
    fake = FakeClamd(b"stream: OK\x00")
    try:
        _set_clamav("127.0.0.1", fake.port)
        from app.services.scanner import scan_bytes
        assert scan_bytes(DOCX) == "clean"
    finally:
        fake.close()
        _set_clamav("")


def test_clamav_infected_rejected(env):
    fake = FakeClamd(b"stream: Eicar-Test-Signature FOUND\x00")
    tok, job = env["a"]["token"], env["job"]
    try:
        _set_clamav("127.0.0.1", fake.port)
        r = client.post(f"/api/v1/ats/jobs/{job}/screen",
                        files={"files": ("evil.docx", DOCX, MIME)}, headers=_auth(tok))
        assert r.status_code == 200
        assert r.json()["screened"] == 0
        assert "malware" in r.json()["errors"][0]["error"].lower()
        from app.db import AuditEvent, SessionLocal
        db = SessionLocal()
        acts = [e.action for e in db.query(AuditEvent)
                .filter(AuditEvent.action == "malware_detected")]
        db.close()
        assert "malware_detected" in acts
    finally:
        fake.close()
        _set_clamav("")


def test_clamav_unavailable_optional_allows_unavailable_required_blocks(env):
    from app.services.scanner import scan_bytes, ScannerUnavailable, MalwareDetected
    # required + unreachable -> raises
    _set_clamav("127.0.0.1", 1, "true")
    import app.config as cfg
    cfg.settings.clamav_port = 1  # nothing listening
    try:
        with pytest.raises(ScannerUnavailable):
            scan_bytes(DOCX)
    finally:
        _set_clamav("")
    # optional + unreachable -> 'error', does not raise
    cfg.settings.clamav_host = "127.0.0.1"
    cfg.settings.clamav_port = 1
    cfg.settings.clamav_required = False
    try:
        assert scan_bytes(DOCX) == "error"
    finally:
        _set_clamav("")


def test_scanner_disabled_returns_skipped():
    from app.services.scanner import scan_bytes
    assert scan_bytes(DOCX) == "skipped"
