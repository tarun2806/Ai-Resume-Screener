"""
Server-side tenant (organization) resolution.

Rules:
- The active organization is derived from the authenticated user's
  memberships — never trusted from a client-supplied org id alone.
- An optional `X-Org-Id` header selects among orgs the user belongs to;
  anything else is rejected with 403.
- Org roles: owner(4) > admin(3) > recruiter(2) > viewer(1).
- Candidates are global accounts and have no org memberships; org-scoped
  recruiter endpoints are not reachable for them.
"""
from typing import List, Optional

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.db import Job, OrgMembership, Organization, User

ORG_ROLE_RANK = {"viewer": 1, "recruiter": 2, "admin": 3, "owner": 4}
ORG_ROLES = set(ORG_ROLE_RANK)
WRITE_ROLES = {"owner", "admin", "recruiter"}
READ_ROLES = {"owner", "admin", "recruiter", "viewer"}


def user_memberships(db: Session, user: User) -> List[OrgMembership]:
    return (
        db.query(OrgMembership)
        .filter(OrgMembership.user_id == user.id)
        .order_by(OrgMembership.created_at.asc())
        .all()
    )


def resolve_org(
    db: Session,
    user: User,
    requested_org_id: Optional[int] = None,
) -> OrgMembership:
    """
    Return the active OrgMembership for `user`.
    - requested_org_id must match a membership (else 403).
    - No request -> first membership by creation order (else 404).
    """
    memberships = user_memberships(db, user)
    if not memberships:
        raise HTTPException(status_code=404, detail="No organization membership")
    if requested_org_id is None:
        return memberships[0]
    for m in memberships:
        if m.org_id == requested_org_id:
            return m
    raise HTTPException(status_code=403, detail="Not a member of this organization")


def org_ids_for_user(db: Session, user: User) -> List[int]:
    return [m.org_id for m in user_memberships(db, user)]


def require_org_write(db: Session, user: User, requested_org_id: Optional[int] = None) -> OrgMembership:
    m = resolve_org(db, user, requested_org_id)
    if m.role not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Read-only organization role")
    return m


def require_job_write(db: Session, user: User, job: Job) -> OrgMembership:
    """Enforce org membership AND a write-capable org role for a job."""
    if user.role == "admin":
        # platform admin: synthesize check bypass
        memberships = user_memberships(db, user)
        if memberships:
            return memberships[0]
        raise HTTPException(status_code=403, detail="Admin has no organization")
    if job.organization_id is None:
        if job.recruiter_id != user.id:
            raise HTTPException(status_code=404, detail="Job not found")
        memberships = user_memberships(db, user)
        if not memberships:
            raise HTTPException(status_code=403, detail="No organization membership")
        return memberships[0]
    for m in user_memberships(db, user):
        if m.org_id == job.organization_id:
            if m.role not in WRITE_ROLES:
                raise HTTPException(status_code=403, detail="Read-only organization role")
            return m
    raise HTTPException(status_code=404, detail="Job not found")


def job_in_user_orgs(db: Session, job: Job, user: User) -> bool:
    """True if the job's organization is one the user belongs to."""
    if job.organization_id is None:
        # Legacy/unassigned job: fall back to creator ownership
        return job.recruiter_id == user.id or user.role == "admin"
    return job.organization_id in org_ids_for_user(db, user)


def get_org_job_or_404(db: Session, job_id: int, user: User) -> Job:
    """Fetch a job and enforce org membership (recruiter-facing)."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if user.role == "admin":
        return job
    if not job_in_user_orgs(db, job, user):
        # 404 rather than 403 to avoid leaking existence across tenants
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def requested_org_id(request: Optional[Request]) -> Optional[int]:
    if request is None:
        return None
    raw = request.headers.get("x-org-id")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-Org-Id header")
