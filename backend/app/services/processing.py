"""Durable DB-backed resume processing queue + worker.

The ``processing_jobs`` table is the queue and the source of truth —
no broker required, survives API restarts, and dispatch is transactional
with application creation (outbox pattern). Messages carry only opaque
IDs; the worker re-loads the file from private storage.

State machine:
    queued -> processing -> completed
    processing -> retry_wait -> queued   (exponential backoff)
    processing -> failed                (attempts exhausted)
    failed -> queued                    (manual retry via API)
"""
import logging
import os
import socket
import threading
import time
import uuid
from datetime import timedelta

from sqlalchemy import and_, or_

from app.config import settings
from app.db import (
    Application, Job, ProcessingJob, SessionLocal, WorkerHeartbeat, get_db, utcnow,
)
from app.services.analysis import run_analysis
from app.services.storage import get_storage
from app.services.audit import record as audit_record
from app.utils.parser import extract_text
from app.utils.uploads import UploadValidationError, validate_upload

log = logging.getLogger("ai-screenx.worker")

VALID_TRANSITIONS = {
    "queued": {"processing"},
    "processing": {"completed", "retry_wait", "failed"},
    "retry_wait": {"queued"},
    "failed": {"queued"},
    "completed": set(),
}

# Sanitized error codes only — never store exception text (may contain PII).
ERR_STORAGE = "storage_missing"
ERR_VALIDATION = "validation_failed"
ERR_EXTRACT = "extract_failed"
ERR_ANALYSIS = "analysis_failed"
ERR_INTERNAL = "internal_error"

_worker_thread = None
_worker_stop = threading.Event()
_worker_last_tick = None
_jobs_completed = 0
_jobs_failed = 0
_WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"
_heartbeat_lock = threading.Lock()


def _heartbeat(db) -> None:
    """Persist worker liveness + counters so the API can report health for
    workers running in separate processes. Serialized per process."""
    with _heartbeat_lock:
        row = db.query(WorkerHeartbeat).filter(WorkerHeartbeat.worker_id == _WORKER_ID).first()
        if row is None:
            row = WorkerHeartbeat(worker_id=_WORKER_ID, hostname=socket.gethostname(),
                                  pid=os.getpid())
            db.add(row)
        row.last_tick_at = utcnow()
        row.jobs_completed = _jobs_completed
        row.jobs_failed = _jobs_failed
        db.commit()


def worker_health() -> dict:
    """Operational health snapshot for the processing worker(s)."""
    import time as _t
    from datetime import timezone
    db = SessionLocal()
    try:
        from sqlalchemy import func
        depth = dict(db.query(ProcessingJob.status, func.count()).group_by(ProcessingJob.status).all())
        hbs = db.query(WorkerHeartbeat).all()
    finally:
        db.close()
    now = _t.time()
    alive_window = max(30.0, settings.worker_poll_seconds * 5)
    workers = []
    for hb in hbs:
        tick = hb.last_tick_at
        if tick is not None and tick.tzinfo is None:
            tick = tick.replace(tzinfo=timezone.utc)
        age = (now - tick.timestamp()) if tick else None
        workers.append({
            "worker_id": hb.worker_id,
            "hostname": hb.hostname,
            "pid": hb.pid,
            "last_tick_age_seconds": round(age, 1) if age is not None else None,
            "alive": age is not None and age <= alive_window,
            "jobs_completed": hb.jobs_completed,
            "jobs_failed": hb.jobs_failed,
            "started_at": hb.started_at.isoformat() if hb.started_at else None,
        })
    age = (_t.time() - _worker_last_tick) if _worker_last_tick else None
    return {
        "enabled": settings.worker_enabled,
        "thread_alive": bool(_worker_thread and _worker_thread.is_alive()),
        "last_tick_age_seconds": round(age, 1) if age is not None else None,
        "jobs_completed": _jobs_completed,
        "jobs_failed": _jobs_failed,
        "queue_depth": depth,
        "workers": workers,
        "external_workers_alive": sum(1 for w in workers if w["alive"]),
    }


def _aware(dt):
    from datetime import timezone
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def transition(job: ProcessingJob, to_status: str) -> None:
    """Validate and apply a state transition. Raises ValueError on illegal moves."""
    allowed = VALID_TRANSITIONS.get(job.status, set())
    if to_status not in allowed:
        raise ValueError(f"Illegal transition {job.status} -> {to_status}")
    job.status = to_status


def enqueue(db, *, organization_id, job_id, application_id, candidate_id,
            storage_key, batch_id=None) -> ProcessingJob:
    """Create a queued processing job. Call inside the same transaction as
    the Application insert so dispatch can never be lost."""
    pj = ProcessingJob(
        organization_id=organization_id,
        job_id=job_id,
        application_id=application_id,
        candidate_id=candidate_id,
        storage_key=storage_key,
        batch_id=batch_id or uuid.uuid4().hex,
        status="queued",
        max_attempts=settings.processing_max_attempts,
    )
    db.add(pj)
    return pj


def new_batch_id() -> str:
    return uuid.uuid4().hex


def active_job_for_application(db, application_id: int):
    return (
        db.query(ProcessingJob)
        .filter(ProcessingJob.application_id == application_id,
                ProcessingJob.status.in_(["queued", "processing", "retry_wait"]))
        .order_by(ProcessingJob.id.desc())
        .first()
    )


def latest_job_for_application(db, application_id: int):
    return (
        db.query(ProcessingJob)
        .filter(ProcessingJob.application_id == application_id)
        .order_by(ProcessingJob.id.desc())
        .first()
    )


def claim_next(db) -> ProcessingJob | None:
    """Atomically claim the oldest runnable job. Returns None if queue empty."""
    now = utcnow()
    job = (
        db.query(ProcessingJob)
        .filter(or_(
            ProcessingJob.status == "queued",
            and_(ProcessingJob.status == "retry_wait",
                 ProcessingJob.retry_after <= now),
        ))
        .order_by(ProcessingJob.id)
        .first()
    )
    if job is None:
        return None
    # Guarded update: only succeeds if status unchanged since read.
    from sqlalchemy import update
    res = db.execute(
        update(ProcessingJob)
        .where(ProcessingJob.id == job.id, ProcessingJob.status == job.status)
        .values(status="processing", started_at=now, locked_at=now,
                attempt_count=ProcessingJob.attempt_count + 1)
    )
    db.commit()
    if res.rowcount != 1:
        return None  # lost the race; caller may retry
    db.refresh(job)
    return job


def _error_code(exc: Exception) -> str:
    if isinstance(exc, UploadValidationError):
        return ERR_VALIDATION
    if isinstance(exc, FileNotFoundError):
        return ERR_STORAGE
    msg = str(exc).lower()
    if "storage" in msg or "object not found" in msg:
        return ERR_STORAGE
    if "extract" in msg:
        return ERR_EXTRACT
    return ERR_ANALYSIS


def _fail_or_retry(db, job: ProcessingJob, exc: Exception) -> None:
    global _jobs_failed
    _jobs_failed += 1
    job.last_error_code = _error_code(exc)
    app = db.query(Application).filter(Application.id == job.application_id).first()
    if app:
        app.processing_status = "retry_wait" if job.attempt_count < job.max_attempts else "failed"
    if job.attempt_count < job.max_attempts:
        backoff = settings.processing_retry_base_seconds * (2 ** (job.attempt_count - 1))
        transition(job, "retry_wait")
        job.retry_after = utcnow() + timedelta(seconds=backoff)
    else:
        transition(job, "failed")
        job.completed_at = utcnow()
    audit_record(db, action="screening_failed", organization_id=job.organization_id,
                 actor=None, resource_type="application", resource_id=job.application_id,
                 outcome="failure",
                 metadata={"job_id": job.job_id, "attempt": job.attempt_count,
                           "error_code": job.last_error_code})
    db.commit()
    log.warning("processing job %s attempt %s failed: %s", job.id, job.attempt_count, job.last_error_code)


def process_job(job_id: int) -> str:
    """Execute one claimed job end-to-end. Returns final status."""
    db = SessionLocal()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if job is None or job.status != "processing":
            return job.status if job else "missing"

        app = db.query(Application).filter(Application.id == job.application_id).first()
        ats_job = db.query(Job).filter(Job.id == job.job_id).first()
        # Tenant safety: never process across mismatched org/job.
        if app is None or ats_job is None or app.job_id != job.job_id:
            _fail_or_retry(db, job, ValueError("tenant mismatch"))
            return job.status
        if job.organization_id and ats_job.organization_id != job.organization_id:
            _fail_or_retry(db, job, ValueError("tenant mismatch"))
            return job.status

        try:
            content = get_storage().get(job.storage_key)
            validate_upload(app.resume_filename or "resume.pdf", content)
            text = extract_text(content, app.resume_filename or "resume.pdf")
            if not text or len(text.strip()) < 50:
                raise ValueError("Could not extract enough text from resume")
            analysis = run_analysis(text, ats_job.description)
        except Exception as e:
            _fail_or_retry(db, job, e)
            return job.status

        candidate = analysis.get("candidate", {})
        app.candidate_name = app.candidate_name or candidate.get("name") or ""
        app.candidate_email = app.candidate_email or candidate.get("email") or ""
        app.resume_text = analysis.pop("_resume_text", text)
        import json as _json
        app.parsed_profile = _json.dumps({
            "skills": candidate.get("skills", []),
            "experience_years": candidate.get("experience_years"),
            "matched_skills": analysis.get("matched_skills", []),
            "missing_skills": analysis.get("missing_skills", []),
            "confidence": analysis.get("confidence"),
            "education": candidate.get("education"),
        })
        app.match_result = _json.dumps(analysis)
        app.score = analysis.get("overall_score", 0.0)
        global _jobs_completed
        _jobs_completed += 1
        app.processing_status = "completed"
        transition(job, "completed")
        job.completed_at = utcnow()
        audit_record(db, action="screening_completed", organization_id=job.organization_id,
                     actor=None, resource_type="application", resource_id=app.id,
                     metadata={"job_id": job.job_id, "score": app.score,
                               "attempt": job.attempt_count})
        db.commit()
        return "completed"
    except Exception:
        log.exception("processing job %s crashed", job_id)
        try:
            db.rollback()
            job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
            if job and job.status == "processing":
                _fail_or_retry(db, job, RuntimeError("worker crash"))
        except Exception:
            pass
        return "failed"
    finally:
        db.close()


def requeue_stale(db, lease_seconds: int | None = None) -> int:
    """Crash recovery: 'processing' jobs whose lease expired go back to
    queued (or failed if attempts exhausted)."""
    lease = lease_seconds or settings.worker_lease_seconds
    cutoff = utcnow() - timedelta(seconds=lease)
    stale = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.status == "processing",
                ProcessingJob.locked_at < cutoff)
        .all()
    )
    n = 0
    for job in stale:
        app = db.query(Application).filter(Application.id == job.application_id).first()
        if job.attempt_count >= job.max_attempts:
            transition(job, "failed")
            job.completed_at = utcnow()
            if app:
                app.processing_status = "failed"
        else:
            transition(job, "retry_wait")
            job.retry_after = utcnow()
            job.locked_at = None
            if app:
                app.processing_status = "retry_wait"
        n += 1
    if n:
        db.commit()
    return n


def drain(limit: int | None = None) -> int:
    """Synchronously process all runnable jobs. Used by tests and the worker."""
    processed = 0
    while limit is None or processed < limit:
        db = SessionLocal()
        try:
            requeue_stale(db)
            job = claim_next(db)
        finally:
            db.close()
        if job is None:
            break
        process_job(job.id)
        processed += 1
    return processed


def worker_loop() -> None:
    """Poll loop for a worker thread (embedded or standalone process)."""
    db = SessionLocal()
    try:
        requeue_stale(db)
        _heartbeat(db)
    finally:
        db.close()
    global _worker_last_tick
    while not _worker_stop.is_set():
        try:
            drain(limit=10)
            _worker_last_tick = time.time()
        except Exception:
            log.exception("worker drain failed")
        try:
            db = SessionLocal()
            try:
                _heartbeat(db)
            finally:
                db.close()
        except Exception:
            log.exception("worker heartbeat failed")
        _worker_stop.wait(settings.worker_poll_seconds)


def ensure_worker_started() -> None:
    """Start the daemon worker thread once (idempotent)."""
    global _worker_thread
    if not settings.worker_enabled or (_worker_thread and _worker_thread.is_alive()):
        return
    _worker_thread = threading.Thread(target=worker_loop, name="resume-worker", daemon=True)
    _worker_thread.start()
    log.info("resume processing worker started")


def stop_worker() -> None:
    _worker_stop.set()
