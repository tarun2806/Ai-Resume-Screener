"""Malware scanning via clamd INSTREAM (TCP). No external deps.

Behavior matrix:
- CLAMAV_HOST unset            -> scanning disabled (returns "skipped")
- infected                     -> raises MalwareDetected
- scanner error + required     -> raises ScannerUnavailable (fail closed)
- scanner error + optional     -> returns "error" (caller decides; we allow
                                  with a warning metric so uploads aren't
                                  blocked by scanner outages in dev)

This is real malware scanning, distinct from extension/magic-byte checks.
"""
import logging
import socket
import struct

from app.config import settings

log = logging.getLogger("ai-screenx.scanner")

_scan_ok = 0
_scan_infected = 0
_scan_errors = 0


class MalwareDetected(Exception):
    def __init__(self, signature: str = ""):
        super().__init__("Malware detected")
        self.signature = signature


class ScannerUnavailable(Exception):
    pass


def scan_bytes(content: bytes) -> str:
    """Scan content. Returns 'clean' | 'skipped' | 'error'.
    Raises MalwareDetected / ScannerUnavailable."""
    global _scan_ok, _scan_infected, _scan_errors
    if not settings.clamav_host:
        return "skipped"
    try:
        with socket.create_connection(
            (settings.clamav_host, settings.clamav_port),
            timeout=settings.clamav_timeout_seconds,
        ) as sock:
            sock.sendall(b"zINSTREAM\x00")
            # chunk size must fit uint32; send in 64KB chunks
            for i in range(0, len(content), 65536):
                chunk = content[i:i + 65536]
                sock.sendall(struct.pack(">I", len(chunk)) + chunk)
            sock.sendall(struct.pack(">I", 0))
            resp = b""
            while not resp.endswith(b"\x00") and len(resp) < 4096:
                data = sock.recv(4096)
                if not data:
                    break
                resp += data
    except (OSError, socket.timeout) as e:
        _scan_errors += 1
        log.warning("clamav scan error: %s", type(e).__name__)
        if settings.clamav_required:
            raise ScannerUnavailable("Malware scanner unavailable") from e
        return "error"

    text = resp.decode("utf-8", "replace").strip().rstrip("\x00")
    # clamd replies like "stream: OK" or "stream: Eicar-Test-Signature FOUND"
    if " FOUND" in text or text.endswith("FOUND"):
        _scan_infected += 1
        sig = text.split(":", 1)[-1].replace("FOUND", "").strip()
        raise MalwareDetected(sig)
    _scan_ok += 1
    return "clean"


def scan_counters() -> dict:
    return {"clean": _scan_ok, "infected": _scan_infected, "errors": _scan_errors}
