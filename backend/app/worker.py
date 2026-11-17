"""Standalone resume-processing worker process.

Run: ``python -m app.worker``

Separate from the API so API replicas never auto-start workers
(WORKER_ENABLED=false on API services). WORKER_CONCURRENCY controls how
many drain threads share this process; claims are atomic at the DB level.
"""
import logging
import signal
import threading
import time

from app.config import settings
from app.db import init_db
from app.logging_setup import configure_logging
from app.services import processing as proc

log = logging.getLogger("ai-screenx.worker")


def main() -> None:
    configure_logging()
    init_db()
    n = max(1, settings.worker_concurrency)
    threads = [
        threading.Thread(target=proc.worker_loop, name=f"resume-worker-{i}", daemon=True)
        for i in range(n)
    ]
    for t in threads:
        t.start()
    log.info("worker process started", extra={})

    def _shutdown(*_):
        log.info("worker shutdown requested")
        proc.stop_worker()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # Wait for loops to finish their current drain, then exit.
    deadline = time.time() + max(30.0, settings.worker_lease_seconds)
    for t in threads:
        t.join(timeout=max(1.0, deadline - time.time()))
    log.info("worker process stopped")


if __name__ == "__main__":
    main()
