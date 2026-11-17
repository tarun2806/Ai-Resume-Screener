import csv
import hashlib
import io
import json
from datetime import timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.db import Application, Job, User, get_db, utcnow
from app.services.analysis import run_analysis, extract_min_years
from app.services.storage import generate_key, get_storage
from app.services import processing as proc
from app.services.audit import record as audit_record
from app.services.scanner import MalwareDetected, ScannerUnavailable, scan_bytes, scan_counters
from app.services.nlp_processor import AdvancedNLPProcessor
from app.services.tenancy import (
    get_org_job_or_404,
    org_ids_for_user,
    requested_org_id,
    require_job_write,
    require_org_write,
    resolve_org,
)
from app.utils.parser import extract_text
from app.utils.uploads import read_and_validate, UploadValidationError, MAX_UPLOAD_BYTES
from app.ratelimit import limiter

router = APIRouter()
processor = AdvancedNLPProcessor()

MAX_BULK_FILES = 25
VALID_STATUSES = {"new", "reviewed", "shortlisted", "rejected", "interview"}


# ---------- schemas ----------

class JobCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=50)
    location: str = Field(default="", max_length=255)
    status: str = Field(default="open", pattern="^(open|closed|draft)$")


class ApplicationUpdate(BaseModel):
    status: Optional[str] = Field(default=None, pattern="^(new|reviewed|shortlisted|rejected|interview)$")
    notes: Optional[str] = Field(default=None, max_length=5000)


class RoleUpdate(BaseModel):
    role: str = Field(pattern="^(candidate|recruiter|admin)$")


# ---------- helpers ----------


def _job_payload(job: Job, db: Session) -> dict:
    apps = db.query(Application).filter(Application.job_id == job.id).all()
    scores = [a.score for a in apps]
    return {
        "id": job.id,
        "title": job.title,
        "description": job.description,
        "location": job.location,
        "status": job.status,
        "required_skills": json.loads(job.required_skills or "[]"),
        "min_years": job.min_years,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "application_count": len(apps),
        "avg_score": round(sum(scores) / len(scores), 2) if scores else 0,
    }


def _app_summary(app: Application) -> dict:
    parsed = {}
    try:
        parsed = json.loads(app.parsed_profile or "{}")
    except Exception:
        pass
    return {
        "id": app.id,
        "job_id": app.job_id,
        "job_title": app.job.title if app.job else "",
        "candidate_name": app.candidate_name,
        "candidate_email": app.candidate_email,
        "resume_filename": app.resume_filename,
        "score": app.score,
        "status": app.status,
        "recruiter_notes": app.recruiter_notes,
        "skills": parsed.get("skills", []),
        "experience_years": parsed.get("experience_years"),
        "matched_skills": parsed.get("matched_skills", []),
        "missing_skills": parsed.get("missing_skills", []),
        "confidence": parsed.get("confidence"),
        "processing_status": app.processing_status or "none",
        "created_at": app.created_at.isoformat() if app.created_at else None,
    }


def _get_job_or_404(db: Session, job_id: int, user: User) -> Job:
    """Org-scoped job lookup: recruiter-facing access requires membership
    in the job's organization. Returns 404 (not 403) cross-tenant to avoid
    leaking job existence."""
    return get_org_job_or_404(db, job_id, user)


def _screen_one(file_bytes: bytes, filename: str, job: Job) -> dict:
    """Parse + score a single resume against a job. Returns result dict."""
    text = extract_text(file_bytes, filename)
    if not text or len(text.strip()) < 50:
        raise ValueError("Could not extract enough text from resume")
    result = run_analysis(text, job.description)
    result["_resume_text"] = text
    return result


def _scan_or_raise(content: bytes, filename: str, db: Session, user: User, job: Job) -> str | None:
    """Run malware scan. Returns error string or None when clean/skipped.
    Raises HTTPException when scanner is required but unavailable."""
    try:
        result = scan_bytes(content)
    except MalwareDetected as e:
        audit_record(db, action="malware_detected", actor=user,
                     resource_type="job", resource_id=job.id,
                     outcome="denied",
                     metadata={"file": (filename or "")[:120], "signature": e.signature})
        db.commit()
        return "File rejected by malware scan"
    except ScannerUnavailable:
        raise HTTPException(status_code=503, detail="Malware scanner unavailable")
    return None


def _store_resume(org_id: int | None, content: bytes, filename: str) -> tuple[str, str]:
    """Persist original resume bytes to private storage.
    Returns (storage_key, sha256 content hash). Raises on storage failure —
    callers must not create an application without its stored file."""
    import os
    ext = os.path.splitext(filename or "")[1].lower()
    key = generate_key(org_id, ext)
    get_storage().put(key, content)
    return key, hashlib.sha256(content).hexdigest()


# ---------- jobs ----------

@router.post("/jobs")
async def create_job(
    request: Request,
    body: JobCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("recruiter", "admin")),
):
    membership = require_org_write(db, user, requested_org_id(request))
    jd = processor.process_jd(body.description)
    job = Job(
        recruiter_id=user.id,
        organization_id=membership.org_id,
        title=body.title.strip(),
        description=body.description,
        location=body.location,
        status=body.status,
        required_skills=json.dumps(jd.get("explicit_skills", [])),
        min_years=extract_min_years(body.description),
    )
    db.add(job)
    audit_record(db, action="job_created", actor=user, organization_id=membership.org_id,
                 resource_type="job", resource_id=job.id, metadata={"title": job.title})
    db.commit()
    db.refresh(job)
    return _job_payload(job, db)


@router.get("/jobs")
async def list_jobs(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Job)
    if user.role == "candidate":
        # Global job board: open jobs across all organizations.
        q = q.filter(Job.status == "open")
    elif user.role == "admin":
        pass  # platform admin sees everything
    else:
        req_org = requested_org_id(request)
        org_ids = [req_org] if req_org is not None else org_ids_for_user(db, user)
        # requested_org_id already validated against membership via resolve below
        if req_org is not None:
            resolve_org(db, user, req_org)
        q = q.filter(Job.organization_id.in_(org_ids)) if org_ids else q.filter(Job.id == -1)
    jobs = q.order_by(Job.created_at.desc()).all()
    return {"jobs": [_job_payload(j, db) for j in jobs]}


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == "candidate":
        # Candidates browse the global job board: open jobs only.
        job = db.query(Job).filter(Job.id == job_id, Job.status == "open").first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return _job_payload(job, db)
    job = _get_job_or_404(db, job_id, user)
    return _job_payload(job, db)


@router.patch("/jobs/{job_id}")
async def update_job(
    job_id: int,
    body: JobCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("recruiter", "admin")),
):
    job = _get_job_or_404(db, job_id, user)
    require_job_write(db, user, job)
    job.title = body.title.strip()
    job.description = body.description
    job.location = body.location
    job.status = body.status
    jd = processor.process_jd(body.description)
    job.required_skills = json.dumps(jd.get("explicit_skills", []))
    job.min_years = extract_min_years(body.description)
    audit_record(db, action="job_updated", actor=user,
                 resource_type="job", resource_id=job.id, metadata={"title": job.title})
    db.commit()
    return _job_payload(job, db)


# ---------- screening ----------

@router.post("/jobs/{job_id}/screen")
@limiter.limit("10/minute")
async def screen_resumes(
    request: Request,
    job_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("recruiter", "admin")),
):
    job = _get_job_or_404(db, job_id, user)
    require_job_write(db, user, job)
    if len(files) > MAX_BULK_FILES:
        raise HTTPException(status_code=400, detail=f"Max {MAX_BULK_FILES} files per batch")

    results = []
    errors = []
    skipped = []
    for f in files:
        try:
            content = await read_and_validate(f)
            scan_err = _scan_or_raise(content, f.filename or "", db, user, job)
            if scan_err:
                errors.append({"file": f.filename, "error": scan_err})
                continue
            chash = hashlib.sha256(content).hexdigest()
            dup = db.query(Application).filter(
                Application.job_id == job.id, Application.content_hash == chash).first()
            if dup:
                skipped.append({"file": f.filename, "reason": "duplicate_resume",
                                "application_id": dup.id})
                continue
            analysis = _screen_one(content, f.filename or "resume", job)
        except UploadValidationError as e:
            errors.append({"file": f.filename, "error": str(e)})
            continue
        except Exception as e:
            errors.append({"file": f.filename, "error": f"Processing failed: {e}"})
            continue

        storage_key, content_hash = _store_resume(job.organization_id, content, f.filename or "")
        candidate = analysis.get("candidate", {})
        app = Application(
            job_id=job.id,
            candidate_name=candidate.get("name") or "",
            candidate_email=candidate.get("email") or "",
            resume_filename=f.filename or "",
            resume_storage_key=storage_key,
            content_hash=content_hash,
            resume_text=analysis.pop("_resume_text", ""),
            parsed_profile=json.dumps({
                "skills": candidate.get("skills", []),
                "experience_years": candidate.get("experience_years"),
                "matched_skills": analysis.get("matched_skills", []),
                "missing_skills": analysis.get("missing_skills", []),
                "confidence": analysis.get("confidence"),
                "education": candidate.get("education"),
            }),
            match_result=json.dumps(analysis),
            score=analysis.get("overall_score", 0.0),
        )
        db.add(app)
        results.append({"file": f.filename, "score": app.score, "id": None})

    audit_record(db, action="screening_submitted", actor=user,
                 resource_type="job", resource_id=job.id,
                 metadata={"files": len(files), "screened": len(results),
                           "skipped": len(skipped), "errors": len(errors)})
    db.commit()

    # refresh ids + return ranked
    apps = (
        db.query(Application)
        .filter(Application.job_id == job.id)
        .order_by(Application.score.desc())
        .all()
    )
    return {
        "screened": len(results),
        "skipped": skipped,
        "errors": errors,
        "ranked": [_app_summary(a) for a in apps],
    }


# ---------- async processing ----------

@router.post("/jobs/{job_id}/screen/async")
@limiter.limit("10/minute")
async def screen_resumes_async(
    request: Request,
    job_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("recruiter", "admin")),
):
    """Store resumes privately and queue durable background processing.
    Returns immediately with per-file queued application ids."""
    job = _get_job_or_404(db, job_id, user)
    require_job_write(db, user, job)
    if len(files) > MAX_BULK_FILES:
        raise HTTPException(status_code=400, detail=f"Max {MAX_BULK_FILES} files per batch")

    batch_id = proc.new_batch_id()
    queued, skipped, errors = [], [], []
    storage = get_storage()

    for f in files:
        try:
            content = await read_and_validate(f)
        except UploadValidationError as e:
            errors.append({"file": f.filename, "error": str(e)})
            continue
        except Exception:
            errors.append({"file": f.filename, "error": "Upload failed"})
            continue
        try:
            scan_err = _scan_or_raise(content, f.filename or "", db, user, job)
        except HTTPException as e:
            raise e
        if scan_err:
            errors.append({"file": f.filename, "error": scan_err})
            continue

        chash = hashlib.sha256(content).hexdigest()
        dup = db.query(Application).filter(
            Application.job_id == job.id, Application.content_hash == chash).first()
        if dup:
            skipped.append({"file": f.filename, "reason": "duplicate_resume",
                            "application_id": dup.id})
            continue

        try:
            ext = (f.filename or "").rsplit(".", 1)[-1].lower()
            storage_key = generate_key(job.organization_id, "." + ext if ext in ("pdf", "docx") else ".pdf")
            storage.put(storage_key, content)
        except Exception:
            errors.append({"file": f.filename, "error": "Storage failed"})
            continue

        app = Application(
            job_id=job.id,
            candidate_name="",
            candidate_email="",
            resume_filename=f.filename or "",
            resume_storage_key=storage_key,
            content_hash=chash,
            processing_status="queued",
        )
        db.add(app)
        db.flush()
        proc.enqueue(db, organization_id=job.organization_id, job_id=job.id,
                     application_id=app.id, candidate_id=None,
                     storage_key=storage_key, batch_id=batch_id)
        queued.append({"file": f.filename, "application_id": app.id,
                       "status": "queued"})

    audit_record(db, action="screening_queued", actor=user,
                 resource_type="job", resource_id=job.id,
                 metadata={"batch_id": batch_id, "queued": len(queued),
                           "skipped": len(skipped), "errors": len(errors)})
    db.commit()
    proc.ensure_worker_started()
    return {"batch_id": batch_id, "queued": queued, "skipped": skipped, "errors": errors}


def _processing_payload(pj) -> dict:
    return {
        "id": pj.id,
        "application_id": pj.application_id,
        "status": pj.status,
        "attempt_count": pj.attempt_count,
        "max_attempts": pj.max_attempts,
        "last_error_code": pj.last_error_code or None,
        "batch_id": pj.batch_id,
        "created_at": pj.created_at.isoformat() if pj.created_at else None,
        "started_at": pj.started_at.isoformat() if pj.started_at else None,
        "completed_at": pj.completed_at.isoformat() if pj.completed_at else None,
        "retry_after": pj.retry_after.isoformat() if pj.retry_after else None,
    }


@router.get("/jobs/{job_id}/processing")
async def batch_processing_status(
    job_id: int,
    batch_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Batch progress for a job (optionally one batch_id). Org members only."""
    job = _get_job_or_404(db, job_id, user)
    q = db.query(proc.ProcessingJob).filter(proc.ProcessingJob.job_id == job.id)
    if batch_id:
        q = q.filter(proc.ProcessingJob.batch_id == batch_id)
    jobs = q.order_by(proc.ProcessingJob.id.desc()).limit(500).all()
    counts: dict = {}
    for pj in jobs:
        counts[pj.status] = counts.get(pj.status, 0) + 1
    return {
        "job_id": job.id,
        "batch_id": batch_id,
        "counts": counts,
        "total": len(jobs),
        "items": [_processing_payload(pj) for pj in jobs],
    }


@router.get("/applications/{app_id}/processing")
async def application_processing_status(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Latest processing state for one application.
    Candidates see only their own application's status."""
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if user.role == "candidate" and app.candidate_id != user.id:
        raise HTTPException(status_code=403, detail="Not your application")
    if user.role == "recruiter":
        _get_job_or_404(db, app.job_id, user)
    pj = proc.latest_job_for_application(db, app_id)
    if pj is None:
        return {"application_id": app_id, "status": app.processing_status or "none",
                "processing": None}
    return {"application_id": app_id, "status": app.processing_status or pj.status,
            "processing": _processing_payload(pj)}


@router.post("/applications/{app_id}/processing/retry")
async def retry_processing(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("recruiter", "admin")),
):
    """Requeue a failed processing job (org write access required)."""
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    job = _get_job_or_404(db, app.job_id, user)
    require_job_write(db, user, job)
    pj = proc.latest_job_for_application(db, app_id)
    if pj is None or pj.status != "failed":
        raise HTTPException(status_code=409, detail="Only failed jobs can be retried")
    pj.attempt_count = 0
    pj.last_error_code = ""
    pj.retry_after = None
    pj.locked_at = None
    pj.completed_at = None
    proc.transition(pj, "queued")
    app.processing_status = "queued"
    audit_record(db, action="processing_retry", actor=user,
                 resource_type="application", resource_id=app.id)
    db.commit()
    proc.ensure_worker_started()
    return {"application_id": app_id, "status": "queued"}


# ---------- applications ----------

@router.get("/jobs/{job_id}/applications")
async def list_applications(
    job_id: int,
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    sort: str = "score_desc",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = _get_job_or_404(db, job_id, user)
    q = db.query(Application).filter(Application.job_id == job.id)
    if user.role == "candidate":
        q = q.filter(Application.candidate_id == user.id)
    if status:
        q = q.filter(Application.status == status)
    if min_score is not None:
        q = q.filter(Application.score >= min_score)

    if sort == "score_asc":
        q = q.order_by(Application.score.asc())
    elif sort == "newest":
        q = q.order_by(Application.created_at.desc())
    else:
        q = q.order_by(Application.score.desc())

    return {"applications": [_app_summary(a) for a in q.limit(500).all()]}


@router.get("/jobs/{job_id}/compare")
async def compare_candidates(
    job_id: int,
    ids: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("recruiter", "admin")),
):
    """Side-by-side comparison of up to 5 applicants for one job."""
    job = _get_job_or_404(db, job_id, user)
    id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()][:5]
    if not id_list:
        raise HTTPException(status_code=400, detail="Provide application ids via ?ids=1,2,3")

    apps = (
        db.query(Application)
        .filter(Application.job_id == job.id, Application.id.in_(id_list))
        .all()
    )
    if not apps:
        raise HTTPException(status_code=404, detail="No matching applications for this job")

    candidates = []
    skill_states: dict = {}  # skill_lower -> {app_id: "matched"|"missing"}
    for app in apps:
        summary = _app_summary(app)
        mr = json.loads(app.match_result or "{}")
        breakdown = mr.get("score_breakdown") or []
        matched = { (s or "").lower() for s in summary.get("matched_skills", []) }
        missing = { (s or "").lower() for s in summary.get("missing_skills", []) }
        for s in matched | missing:
            skill_states.setdefault(s, {})[str(app.id)] = (
                "matched" if s in matched else "missing"
            )
        candidates.append({
            "id": app.id,
            "candidate_name": summary["candidate_name"],
            "candidate_email": summary["candidate_email"],
            "score": app.score,
            "status": app.status,
            "experience_years": summary.get("experience_years"),
            "confidence": summary.get("confidence"),
            "matched_skills": summary.get("matched_skills", []),
            "missing_skills": summary.get("missing_skills", []),
            "preferred_skills_matched": mr.get("preferred_skills_matched", []),
            "score_breakdown": breakdown,
            "verdict": mr.get("verdict"),
            "extraction_limitations": mr.get("extraction_limitations", []),
        })

    # Deterministic ranking: score desc, then id asc for ties
    candidates.sort(key=lambda c: (-c["score"], c["id"]))
    return {
        "job_id": job.id,
        "candidates": candidates,
        "skill_matrix": {
            skill: states for skill, states in sorted(skill_states.items())
        },
    }


@router.get("/jobs/{job_id}/insights")
async def job_insights(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("recruiter", "admin")),
):
    """Recruiting funnel + skill-gap analytics for one job."""
    job = _get_job_or_404(db, job_id, user)
    apps = db.query(Application).filter(Application.job_id == job.id).all()

    by_status: dict = {}
    scores = []
    confs = []
    missing_freq: dict = {}
    matched_freq: dict = {}
    for app in apps:
        by_status[app.status] = by_status.get(app.status, 0) + 1
        if app.score is not None:
            scores.append(app.score)
        parsed = {}
        try:
            parsed = json.loads(app.parsed_profile or "{}")
        except Exception:
            pass
        if parsed.get("confidence") is not None:
            confs.append(parsed["confidence"])
        for s in parsed.get("missing_skills", []):
            missing_freq[s] = missing_freq.get(s, 0) + 1
        for s in parsed.get("matched_skills", []):
            matched_freq[s] = matched_freq.get(s, 0) + 1

    n = len(apps)
    return {
        "job_id": job.id,
        "total_applications": n,
        "by_status": by_status,
        "score": {
            "avg": round(sum(scores) / len(scores), 2) if scores else None,
            "min": min(scores) if scores else None,
            "max": max(scores) if scores else None,
        },
        "avg_confidence": round(sum(confs) / len(confs), 1) if confs else None,
        "top_missing_skills": sorted(missing_freq.items(), key=lambda kv: (-kv[1], kv[0]))[:10],
        "top_matched_skills": sorted(matched_freq.items(), key=lambda kv: (-kv[1], kv[0]))[:10],
    }


@router.get("/applications/{app_id}")
async def get_application(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if user.role == "candidate" and app.candidate_id != user.id:
        raise HTTPException(status_code=403, detail="Not your application")
    if user.role == "recruiter":
        _get_job_or_404(db, app.job_id, user)
    summary = _app_summary(app)
    summary["match_result"] = json.loads(app.match_result or "{}")
    summary["parsed_profile_full"] = json.loads(app.parsed_profile or "{}")
    summary["updated_at"] = app.updated_at.isoformat() if app.updated_at else None
    return summary


@router.get("/applications/{app_id}/resume")
async def download_resume(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Stream the stored original resume. Never a public URL — every
    download is authorized: candidates get only their own file, recruiters
    must be a member of the job's organization."""
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if user.role == "candidate" and app.candidate_id != user.id:
        raise HTTPException(status_code=403, detail="Not your application")
    if user.role == "recruiter":
        _get_job_or_404(db, app.job_id, user)
    if not app.resume_storage_key:
        raise HTTPException(status_code=404, detail="No stored resume for this application")
    try:
        content = get_storage().get(app.resume_storage_key)
    except Exception:
        raise HTTPException(status_code=404, detail="Stored resume unavailable")
    # Sanitize filename for Content-Disposition (no path components)
    safe_name = (app.resume_filename or "resume").replace('"', "").replace(chr(92), "/").split("/")[-1] or "resume"
    audit_record(db, action="resume_downloaded", actor=user,
                 resource_type="application", resource_id=app.id)
    db.commit()
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=\"" + safe_name + "\""},
    )


@router.patch("/applications/{app_id}")
async def update_application(
    app_id: int,
    body: ApplicationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("recruiter", "admin")),
):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    job = _get_job_or_404(db, app.job_id, user)
    require_job_write(db, user, job)
    actions = []
    if body.status is not None:
        old_status = app.status
        app.status = body.status
        actions.append(("application_status_changed",
                        {"from": old_status, "to": body.status}))
    if body.notes is not None:
        app.recruiter_notes = body.notes
        actions.append(("application_notes_updated", {}))
    for act, meta in actions:
        audit_record(db, action=act, actor=user,
                     resource_type="application", resource_id=app.id, metadata=meta)
    db.commit()
    return _app_summary(app)


# ---------- candidate actions ----------

@router.post("/jobs/{job_id}/apply")
async def apply_to_job(
    job_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("candidate")),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job or job.status != "open":
        raise HTTPException(status_code=404, detail="Job not found or closed")

    existing = (
        db.query(Application)
        .filter(Application.job_id == job.id, Application.candidate_id == user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Already applied to this job")

    try:
        content = await read_and_validate(file)
    except UploadValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    scan_err = _scan_or_raise(content, file.filename or "", db, user, job)
    if scan_err:
        raise HTTPException(status_code=400, detail=scan_err)
    try:
        analysis = _screen_one(content, file.filename or "resume", job)
    except UploadValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process resume: {e}")

    storage_key, content_hash = _store_resume(job.organization_id, content, file.filename or "")
    candidate = analysis.get("candidate", {})
    app = Application(
        job_id=job.id,
        candidate_id=user.id,
        candidate_name=user.name or candidate.get("name") or "",
        candidate_email=user.email,
        resume_filename=file.filename or "",
        resume_storage_key=storage_key,
        content_hash=content_hash,
        resume_text=analysis.pop("_resume_text", ""),
        parsed_profile=json.dumps({
            "skills": candidate.get("skills", []),
            "experience_years": candidate.get("experience_years"),
            "matched_skills": analysis.get("matched_skills", []),
            "missing_skills": analysis.get("missing_skills", []),
            "confidence": analysis.get("confidence"),
            "education": candidate.get("education"),
        }),
        match_result=json.dumps(analysis),
        score=analysis.get("overall_score", 0.0),
    )
    db.add(app)
    audit_record(db, action="application_submitted", actor=user,
                 resource_type="job", resource_id=job.id,
                 metadata={"application_id": app.id})
    db.commit()
    db.refresh(app)
    return _app_summary(app)


@router.get("/me/applications")
async def my_applications(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("candidate")),
):
    apps = (
        db.query(Application)
        .filter(Application.candidate_id == user.id)
        .order_by(Application.created_at.desc())
        .all()
    )
    return {"applications": [_app_summary(a) for a in apps]}


@router.get("/me/export")
async def export_my_data(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """GDPR-style data export: everything we hold about this user."""
    apps = (
        db.query(Application)
        .filter(Application.candidate_id == user.id)
        .order_by(Application.created_at.desc())
        .all()
    )
    audit_record(db, action="candidate_data_exported", actor=user,
                 resource_type="user", resource_id=user.id)
    db.commit()
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "applications": [
            {
                **_app_summary(a),
                "resume_text": a.resume_text,
                "match_result": json.loads(a.match_result or "{}"),
                "updated_at": a.updated_at.isoformat() if a.updated_at else None,
            }
            for a in apps
        ],
    }


@router.delete("/me")
async def delete_my_account(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("candidate")),
):
    """Permanently delete the account and all associated candidate data.
    Recruiter/admin accounts must be deleted by an administrator to avoid
    orphaning jobs and applicant records."""
    apps = db.query(Application).filter(Application.candidate_id == user.id).all()
    storage = get_storage()
    for a in apps:
        if a.resume_storage_key:
            try:
                storage.delete(a.resume_storage_key)
            except Exception:
                pass  # best-effort; DB record deletion proceeds regardless
    uid = user.id
    email = user.email
    # Detach audit references: actor_id FK would block user deletion.
    # actor_email is retained so the trail stays attributable.
    from app.db import AuditEvent
    db.query(AuditEvent).filter(AuditEvent.actor_id == uid).update(
        {AuditEvent.actor_id: None})
    db.query(Application).filter(Application.candidate_id == user.id).delete()
    db.delete(user)
    from app.request_context import request_id_var
    db.add(AuditEvent(
        actor_id=None, actor_email=email[:255],
        action="account_deleted", resource_type="user", resource_id=str(uid),
        outcome="success", request_id=request_id_var.get()[:64],
        metadata_json='{"self_service": true}',
    ))
    db.commit()
    return {"deleted": True}


def _csv_safe(value) -> str:
    """Neutralize spreadsheet formula injection in CSV cells."""
    s = "" if value is None else str(value)
    if s[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


@router.get("/applications/{app_id}/history")
async def application_history(
    app_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Activity timeline for one application. Org members see recruiter
    events; the owning candidate sees the same timeline for their own app."""
    from app.db import AuditEvent
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if user.role == "candidate" and app.candidate_id != user.id:
        raise HTTPException(status_code=403, detail="Not your application")
    if user.role == "recruiter":
        _get_job_or_404(db, app.job_id, user)
    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.resource_type == "application",
                AuditEvent.resource_id == str(app_id))
        .order_by(AuditEvent.created_at.asc(), AuditEvent.id.asc())
        .limit(500)
        .all()
    )
    return {"application_id": app_id, "events": [
        {
            "id": e.id,
            "action": e.action,
            "outcome": e.outcome,
            "actor_email": e.actor_email or None,
            "metadata": json.loads(e.metadata_json or "{}"),
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]}


# ---------- export & analytics ----------

@router.get("/jobs/{job_id}/export.csv")
async def export_csv(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = _get_job_or_404(db, job_id, user)
    require_job_write(db, user, job)
    audit_record(db, action="csv_exported", actor=user,
                 resource_type="job", resource_id=job.id)
    db.commit()
    apps = (
        db.query(Application)
        .filter(Application.job_id == job.id)
        .order_by(Application.score.desc())
        .all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "rank", "candidate_name", "email", "score", "status",
        "skills", "matched_skills", "missing_skills",
        "experience_years", "confidence", "notes", "applied_at",
    ])
    for i, a in enumerate(apps, 1):
        parsed = json.loads(a.parsed_profile or "{}")
        writer.writerow([
            i, _csv_safe(a.candidate_name), _csv_safe(a.candidate_email), a.score, a.status,
            _csv_safe("; ".join(parsed.get("skills", []))),
            _csv_safe("; ".join(parsed.get("matched_skills", []))),
            _csv_safe("; ".join(parsed.get("missing_skills", []))),
            parsed.get("experience_years"), parsed.get("confidence"),
            _csv_safe(a.recruiter_notes),
            a.created_at.isoformat() if a.created_at else "",
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="job_{job.id}_candidates.csv"'},
    )


@router.get("/analytics")
async def analytics(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("recruiter", "admin")),
):
    job_q = db.query(Job)
    if user.role != "admin":
        org_ids = org_ids_for_user(db, user)
        job_q = job_q.filter(Job.organization_id.in_(org_ids)) if org_ids else job_q.filter(Job.id == -1)
    jobs = job_q.all()
    job_ids = [j.id for j in jobs]

    apps = db.query(Application).filter(Application.job_id.in_(job_ids)).all() if job_ids else []
    by_status = {}
    for a in apps:
        by_status[a.status] = by_status.get(a.status, 0) + 1

    scores = [a.score for a in apps]
    per_job = []
    for j in jobs:
        japps = [a for a in apps if a.job_id == j.id]
        per_job.append({
            "job_id": j.id,
            "title": j.title,
            "status": j.status,
            "applications": len(japps),
            "avg_score": round(sum(a.score for a in japps) / len(japps), 2) if japps else 0,
            "shortlisted": sum(1 for a in japps if a.status == "shortlisted"),
        })

    return {
        "total_jobs": len(jobs),
        "total_applications": len(apps),
        "avg_score": round(sum(scores) / len(scores), 2) if scores else 0,
        "by_status": by_status,
        "per_job": per_job,
    }


# ---------- admin ----------

@router.get("/admin/users")
async def list_users(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return {
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "role": u.role,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ]
    }


@router.post("/admin/maintenance/purge-resume-text")
async def purge_expired_resume_text(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    """
    Retention control: blank out stored resume text / match payloads for
    applications older than RESUME_RETENTION_DAYS (default 365).
    Scores, statuses and notes are preserved; raw PII is removed.
    """
    from app.config import settings

    days = settings.resume_retention_days
    if days <= 0:
        return {"purged": 0, "retention_days": days, "note": "retention disabled"}

    cutoff = utcnow() - timedelta(days=days)
    stale = db.query(Application).filter(Application.created_at < cutoff).all()
    purged = 0
    storage = get_storage()
    for a in stale:
        if a.resume_text or a.match_result not in ("", "{}") or a.resume_storage_key:
            if a.resume_storage_key:
                try:
                    storage.delete(a.resume_storage_key)
                except Exception:
                    pass
            a.resume_storage_key = ""
            a.resume_text = ""
            a.match_result = "{}"
            a.parsed_profile = "{}"
            purged += 1
    audit_record(db, action="retention_purge", actor=user,
                 resource_type="application", resource_id="*",
                 metadata={"purged": purged, "retention_days": days})
    db.commit()
    return {"purged": purged, "retention_days": days}


@router.get("/admin/metrics")
async def admin_metrics(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    """Operational metrics for platform admins. Internal detail — never public."""
    from app import metrics as app_metrics
    from app.db import engine, ProcessingJob
    from app.services import processing as proc
    from app.services.storage import get_storage, generate_key
    from app.config import settings as app_settings
    from datetime import timedelta as _td

    # DB pool utilization (QueuePool on PostgreSQL; NullPool/simple on SQLite)
    pool = {}
    try:
        pool = engine.pool.status() if hasattr(engine.pool, "status") else {}
    except Exception:
        pool = {"error": "unavailable"}

    # Storage writability probe (put + delete a tiny object)
    storage_status = "ok"
    try:
        probe_key = generate_key(0, ".pdf")
        get_storage().put(probe_key, b"%PDF-1.4 probe")
        get_storage().delete(probe_key)
    except Exception:
        storage_status = "error"

    # Stale processing jobs (locked past lease)
    cutoff = utcnow() - _td(seconds=app_settings.worker_lease_seconds)
    stale = db.query(ProcessingJob).filter(
        ProcessingJob.status == "processing", ProcessingJob.locked_at < cutoff).count()

    return {
        "api": app_metrics.snapshot(),
        "database": {"pool": pool},
        "worker": proc.worker_health(),
        "queue": {"stale_processing": stale},
        "storage": {"status": storage_status,
                    "backend": app_settings.storage_backend},
        "scanner": {"enabled": bool(app_settings.clamav_host),
                    "required": app_settings.clamav_required,
                    "counters": scan_counters()},
    }


@router.post("/admin/maintenance/purge-audit")
async def purge_audit_events(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    """Retention control for the audit log (default 730 days)."""
    from app.config import settings
    from app.db import AuditEvent
    days = settings.audit_retention_days
    if days <= 0:
        return {"purged": 0, "retention_days": days, "note": "retention disabled"}
    cutoff = utcnow() - timedelta(days=days)
    n = db.query(AuditEvent).filter(AuditEvent.created_at < cutoff).delete()
    audit_record(db, action="audit_purge", actor=user,
                 resource_type="audit_event", resource_id="*",
                 metadata={"purged": n, "retention_days": days})
    db.commit()
    return {"purged": n, "retention_days": days}


@router.patch("/admin/users/{user_id}/role")
async def set_user_role(
    user_id: int,
    body: RoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id and body.role != "admin":
        raise HTTPException(status_code=400, detail="Cannot demote yourself")
    target.role = body.role
    audit_record(db, action="admin_role_changed", actor=user,
                 resource_type="user", resource_id=target.id,
                 metadata={"role": body.role})
    db.commit()
    return {"id": target.id, "role": target.role}
