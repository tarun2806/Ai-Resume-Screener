"""In-process operational metrics (counters + latency buckets).

Single-process scope: resets on restart, which is acceptable for the
current deployment model. Values feed the admin-only /ats/admin/metrics
endpoint; nothing here is exposed publicly.
"""
import threading
import time
from collections import defaultdict

_lock = threading.Lock()
_requests = 0
_errors_4xx = 0
_errors_5xx = 0
_auth_failures = 0
_latency_sum = 0.0
_latency_count = 0
_buckets = [0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
_bucket_counts = [0] * len(_buckets)
_overflow = 0
_started_at = time.time()


def record_request(duration: float, status_code: int, path: str) -> None:
    global _requests, _errors_4xx, _errors_5xx, _auth_failures
    global _latency_sum, _latency_count, _overflow
    with _lock:
        _requests += 1
        _latency_sum += duration
        _latency_count += 1
        if status_code >= 500:
            _errors_5xx += 1
        elif status_code >= 400:
            _errors_4xx += 1
        if status_code == 401 and "/auth/" in path:
            _auth_failures += 1
        placed = False
        for i, b in enumerate(_buckets):
            if duration <= b:
                _bucket_counts[i] += 1
                placed = True
                break
        if not placed:
            _overflow += 1


def snapshot() -> dict:
    with _lock:
        total = _requests
        return {
            "uptime_seconds": round(time.time() - _started_at, 1),
            "requests_total": total,
            "errors_4xx": _errors_4xx,
            "errors_5xx": _errors_5xx,
            "error_rate": round((_errors_4xx + _errors_5xx) / total, 4) if total else 0.0,
            "auth_failures": _auth_failures,
            "latency": {
                "avg_seconds": round(_latency_sum / _latency_count, 4) if _latency_count else 0,
                "buckets_seconds": {f"<={b}": c for b, c in zip(_buckets, _bucket_counts)},
                "overflow": _overflow,
            },
        }
