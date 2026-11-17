"""Organization management endpoints: create, membership, invitations."""
import json
import secrets
from datetime import timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_roles
from app.db import (
    Application, Job, OrgInvitation, OrgMembership, Organization, User, get_db, utcnow,
)
from app.services.tenancy import ORG_ROLE_RANK, resolve_org, user_memberships
from app.services.audit import record as audit_record

router = APIRouter()

INVITE_TTL_HOURS = 72


class OrgCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)


class InviteCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    role: str = Field(default="recruiter", pattern="^(admin|recruiter|viewer)$")


class MemberRoleUpdate(BaseModel):
    role: str = Field(pattern="^(admin|recruiter|viewer|owner)$")


class InviteAccept(BaseModel):
    token: str = Field(min_length=10, max_length=128)


def _aware(dt):
    """Normalize DB datetimes (naive on SQLite) for comparison with utcnow()."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _membership_payload(db: Session, m: OrgMembership) -> dict:
    u = m.user
    return {
        "user_id": m.user_id,
        "name": u.name if u else None,
        "email": u.email if u else None,
        "role": m.role,
        "joined_at": m.created_at.isoformat() if m.created_at else None,
    }


def _org_payload(db: Session, org: Organization, user: User) -> dict:
    m = next((x for x in user_memberships(db, user) if x.org_id == org.id), None)
    return {
        "id": org.id,
        "name": org.name,
        "my_role": m.role if m else None,
        "created_at": org.created_at.isoformat() if org.created_at else None,
    }


def _get_org_or_404(db: Session, org_id: int) -> Organization:
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


def _require_org_admin(db: Session, user: User, org_id: int) -> OrgMembership:
    """Org-level admin: owner or admin role in THAT org."""
    for m in user_memberships(db, user):
        if m.org_id == org_id:
            if ORG_ROLE_RANK.get(m.role, 0) < ORG_ROLE_RANK["admin"]:
                raise HTTPException(status_code=403, detail="Organization admin role required")
            return m
    raise HTTPException(status_code=403, detail="Not a member of this organization")


# ---------- orgs ----------

@router.get("/orgs")
async def list_my_orgs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    out = []
    for m in user_memberships(db, user):
        org = db.query(Organization).filter(Organization.id == m.org_id).first()
        if org:
            out.append(_org_payload(db, org, user))
    return {"organizations": out}


@router.post("/orgs")
async def create_org(
    body: OrgCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("recruiter", "admin")),
):
    org = Organization(name=body.name.strip())
    db.add(org)
    db.flush()
    db.add(OrgMembership(org_id=org.id, user_id=user.id, role="owner"))
    audit_record(db, action="org_created", actor=user, organization_id=org.id,
                 resource_type="organization", resource_id=org.id,
                 metadata={"name": org.name})
    db.commit()
    db.refresh(org)
    return _org_payload(db, org, user)


@router.get("/orgs/{org_id}")
async def get_org(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    resolve_org(db, user, org_id)  # membership check
    org = _get_org_or_404(db, org_id)
    payload = _org_payload(db, org, user)
    members = db.query(OrgMembership).filter(OrgMembership.org_id == org.id).all()
    payload["members"] = [_membership_payload(db, m) for m in members]
    return payload


# ---------- invitations ----------

@router.post("/orgs/{org_id}/invites")
async def create_invite(
    org_id: int,
    body: InviteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_org_admin(db, user, org_id)
    _get_org_or_404(db, org_id)
    email = body.email.lower().strip()

    target = db.query(User).filter(User.email == email).first()
    if target:
        member = db.query(OrgMembership).filter(
            OrgMembership.org_id == org_id, OrgMembership.user_id == target.id).first()
        if member:
            raise HTTPException(status_code=409, detail="User is already a member")

    inv = OrgInvitation(
        org_id=org_id,
        email=email,
        role=body.role,
        token=secrets.token_urlsafe(32),
        invited_by=user.id,
        expires_at=utcnow() + timedelta(hours=INVITE_TTL_HOURS),
    )
    db.add(inv)
    audit_record(db, action="invite_created", actor=user, organization_id=org_id,
                 resource_type="invitation", resource_id=inv.id,
                 metadata={"email": email, "role": body.role})
    db.commit()
    db.refresh(inv)
    return {
        "id": inv.id,
        "email": inv.email,
        "role": inv.role,
        "token": inv.token,
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
    }


@router.get("/orgs/{org_id}/invites")
async def list_invites(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_org_admin(db, user, org_id)
    invs = (
        db.query(OrgInvitation)
        .filter(OrgInvitation.org_id == org_id,
                OrgInvitation.accepted_at.is_(None),
                OrgInvitation.revoked_at.is_(None))
        .all()
    )
    now = utcnow()
    return {"invites": [
        {
            "id": i.id,
            "email": i.email,
            "role": i.role,
            "expires_at": i.expires_at.isoformat() if i.expires_at else None,
            "expired": _aware(i.expires_at) is not None and _aware(i.expires_at) < now,
        }
        for i in invs
    ]}


@router.delete("/orgs/{org_id}/invites/{invite_id}")
async def revoke_invite(
    org_id: int,
    invite_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_org_admin(db, user, org_id)
    inv = db.query(OrgInvitation).filter(
        OrgInvitation.id == invite_id, OrgInvitation.org_id == org_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found")
    inv.revoked_at = utcnow()
    audit_record(db, action="invite_revoked", actor=user, organization_id=org_id,
                 resource_type="invitation", resource_id=inv.id)
    db.commit()
    return {"revoked": True}


@router.post("/orgs/invites/accept")
async def accept_invite(
    body: InviteAccept,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    inv = db.query(OrgInvitation).filter(OrgInvitation.token == body.token).first()
    if not inv or inv.accepted_at or inv.revoked_at:
        raise HTTPException(status_code=404, detail="Invalid invitation")
    if _aware(inv.expires_at) and _aware(inv.expires_at) < utcnow():
        raise HTTPException(status_code=410, detail="Invitation expired")
    if inv.email.lower() != user.email.lower():
        raise HTTPException(status_code=403, detail="Invitation is for a different email")
    existing = db.query(OrgMembership).filter(
        OrgMembership.org_id == inv.org_id, OrgMembership.user_id == user.id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Already a member")
    db.add(OrgMembership(org_id=inv.org_id, user_id=user.id, role=inv.role))
    inv.accepted_at = utcnow()
    audit_record(db, action="invite_accepted", actor=user, organization_id=inv.org_id,
                 resource_type="invitation", resource_id=inv.id,
                 metadata={"role": inv.role})
    db.commit()
    org = _get_org_or_404(db, inv.org_id)
    return {"organization": _org_payload(db, org, user), "role": inv.role}


# ---------- members ----------

@router.patch("/orgs/{org_id}/members/{user_id}")
async def set_member_role(
    org_id: int,
    user_id: int,
    body: MemberRoleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_org_admin(db, user, org_id)
    m = db.query(OrgMembership).filter(
        OrgMembership.org_id == org_id, OrgMembership.user_id == user_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    if m.role == "owner" and body.role != "owner":
        owners = db.query(OrgMembership).filter(
            OrgMembership.org_id == org_id, OrgMembership.role == "owner").count()
        if owners <= 1:
            raise HTTPException(status_code=400, detail="Cannot demote the last owner")
    old_role = m.role
    m.role = body.role
    audit_record(db, action="member_role_changed", actor=user, organization_id=org_id,
                 resource_type="membership", resource_id=m.id,
                 metadata={"target_user_id": user_id, "from": old_role, "to": body.role})
    db.commit()
    return _membership_payload(db, m)


@router.delete("/orgs/{org_id}/members/{user_id}")
async def remove_member(
    org_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    m = db.query(OrgMembership).filter(
        OrgMembership.org_id == org_id, OrgMembership.user_id == user_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    if user_id == user.id:
        resolve_org(db, user, org_id)
    else:
        _require_org_admin(db, user, org_id)
    if m.role == "owner":
        owners = db.query(OrgMembership).filter(
            OrgMembership.org_id == org_id, OrgMembership.role == "owner").count()
        if owners <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the last owner")
    removed_role = m.role
    db.delete(m)
    audit_record(db, action="member_removed", actor=user, organization_id=org_id,
                 resource_type="membership", resource_id=m.id,
                 metadata={"target_user_id": user_id, "role": removed_role})
    db.commit()
    return {"removed": True}


# ---------- org analytics ----------

@router.get("/orgs/{org_id}/analytics")
async def org_analytics(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    resolve_org(db, user, org_id)  # any org member may view analytics
    jobs = db.query(Job).filter(Job.organization_id == org_id).all()
    job_ids = [j.id for j in jobs]
    apps = (
        db.query(Application).filter(Application.job_id.in_(job_ids)).all()
        if job_ids else []
    )
    by_status: dict = {}
    scores = []
    for a in apps:
        by_status[a.status] = by_status.get(a.status, 0) + 1
        if a.score is not None:
            scores.append(a.score)
    return {
        "organization_id": org_id,
        "total_jobs": len(jobs),
        "total_applications": len(apps),
        "avg_score": round(sum(scores) / len(scores), 2) if scores else 0,
        "by_status": by_status,
    }


# ---------- audit ----------

@router.get("/orgs/{org_id}/audit")
async def org_audit_log(
    org_id: int,
    limit: int = 200,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Org-scoped audit trail. Org owner/admin only."""
    from app.db import AuditEvent
    _require_org_admin(db, user, org_id)
    _get_org_or_404(db, org_id)
    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.organization_id == org_id)
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(min(max(limit, 1), 500))
        .all()
    )
    return {"organization_id": org_id, "events": [
        {
            "id": e.id,
            "action": e.action,
            "outcome": e.outcome,
            "actor_email": e.actor_email or None,
            "resource_type": e.resource_type,
            "resource_id": e.resource_id,
            "request_id": e.request_id or None,
            "metadata": json.loads(e.metadata_json or "{}"),
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]}
