import csv
import io
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.db import Application, Job, User, get_db, utcnow
from app.services.analysis import run_analysis, extract_min_years
from app.services.nlp_processor import AdvancedNLPProcessor
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
        "created_at": app.created_at.isoformat() if app.created_at else None,
    }


def _get_job_or_404(db: Session, job_id: int, user: User) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if user.role != "admin" and job.recruiter_id != user.id:
        raise HTTPException(status_code=403, detail="Not your job")
    return job


def _screen_one(file_bytes: bytes, filename: str, job: Job) -> dict:
    """Parse + score a single resume against a job. Returns result dict."""
    text = extract_text(file_bytes, filename)
    if not text or len(text.strip()) < 50:
        raise ValueError("Could not extract enough text from resume")
    result = run_analysis(text, job.description)
    result["_resume_text"] = text
    return result


# ---------- jobs ----------

@router.post("/jobs")
async def create_job(
    body: JobCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("recruiter", "admin")),
):
    jd = processor.process_jd(body.description)
    job = Job(
        recruiter_id=user.id,
        title=body.title.strip(),
        description=body.description,
        location=body.location,
        status=body.status,
        required_skills=json.dumps(jd.get("explicit_skills", [])),
        min_years=extract_min_years(body.description),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _job_payload(job, db)


@router.get("/jobs")
async def list_jobs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Job)
    if user.role == "candidate":
        q = q.filter(Job.status == "open")
    elif user.role != "admin":
        q = q.filter(Job.recruiter_id == user.id)
    jobs = q.order_by(Job.created_at.desc()).all()
    return {"jobs": [_job_payload(j, db) for j in jobs]}


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
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
    job.title = body.title.strip()
    job.description = body.description
    job.location = body.location
    job.status = body.status
    jd = processor.process_jd(body.description)
    job.required_skills = json.dumps(jd.get("explicit_skills", []))
    job.min_years = extract_min_years(body.description)
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
    if len(files) > MAX_BULK_FILES:
        raise HTTPException(status_code=400, detail=f"Max {MAX_BULK_FILES} files per batch")

    results = []
    errors = []
    for f in files:
        try:
            content = await read_and_validate(f)
            analysis = _screen_one(content, f.filename or "resume", job)
        except UploadValidationError as e:
            errors.append({"file": f.filename, "error": str(e)})
            continue
        except Exception as e:
            errors.append({"file": f.filename, "error": f"Processing failed: {e}"})
            continue

        candidate = analysis.get("candidate", {})
        app = Application(
            job_id=job.id,
            candidate_name=candidate.get("name") or "",
            candidate_email=candidate.get("email") or "",
            resume_filename=f.filename or "",
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
        "errors": errors,
        "ranked": [_app_summary(a) for a in apps],
    }


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
    _get_job_or_404(db, app.job_id, user)
    if body.status is not None:
        app.status = body.status
    if body.notes is not None:
        app.recruiter_notes = body.notes
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
        analysis = _screen_one(content, file.filename or "resume", job)
    except UploadValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process resume: {e}")

    candidate = analysis.get("candidate", {})
    app = Application(
        job_id=job.id,
        candidate_id=user.id,
        candidate_name=user.name or candidate.get("name") or "",
        candidate_email=user.email,
        resume_filename=file.filename or "",
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


# ---------- export & analytics ----------

@router.get("/jobs/{job_id}/export.csv")
async def export_csv(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = _get_job_or_404(db, job_id, user)
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
            i, a.candidate_name, a.candidate_email, a.score, a.status,
            "; ".join(parsed.get("skills", [])),
            "; ".join(parsed.get("matched_skills", [])),
            "; ".join(parsed.get("missing_skills", [])),
            parsed.get("experience_years"), parsed.get("confidence"),
            a.recruiter_notes,
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
        job_q = job_q.filter(Job.recruiter_id == user.id)
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
    db.commit()
    return {"id": target.id, "role": target.role}
