import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.auth import create_token, get_current_user, hash_password, verify_password
from app.db import OrgMembership, Organization, User, get_db
from app.ratelimit import limiter

def _provision_personal_org(db: Session, user: User) -> None:
    """Recruiters get a personal organization with owner membership so they
    can create org-scoped jobs immediately. Candidates stay global."""
    if user.role != "recruiter":
        return
    org = Organization(name=f"{user.name or user.email}'s Organization")
    db.add(org)
    db.flush()
    db.add(OrgMembership(org_id=org.id, user_id=user.id, role="owner"))


router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    role: str = Field(default="candidate", pattern="^(candidate|recruiter)$")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def _user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.post("/register")
@limiter.limit("10/minute")
async def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=email,
        password_hash=hash_password(body.password),
        name=body.name.strip(),
        role=body.role,
    )
    db.add(user)
    db.flush()
    _provision_personal_org(db, user)
    db.commit()
    db.refresh(user)
    return {"token": create_token(user), "user": _user_payload(user)}


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower().strip()).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"token": create_token(user), "user": _user_payload(user)}


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {"user": _user_payload(user)}
