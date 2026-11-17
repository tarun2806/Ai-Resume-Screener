import os
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, ForeignKey, create_engine, event
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from app.config import settings

DB_PATH = settings.database_url

def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


if _is_sqlite(DB_PATH):
    engine = create_engine(DB_PATH, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()
else:
    engine = create_engine(
        DB_PATH,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=1800,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="candidate")  # candidate | recruiter | admin
    created_at = Column(DateTime, default=utcnow)

    jobs = relationship("Job", back_populates="recruiter")
    applications = relationship("Application", back_populates="candidate")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    recruiter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    location = Column(String(255), default="")
    status = Column(String(20), default="open")  # open | closed | draft
    required_skills = Column(Text, default="[]")  # JSON list
    min_years = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    recruiter = relationship("User", back_populates="jobs")
    organization = relationship("Organization")
    applications = relationship("Application", back_populates="job")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    candidate_name = Column(String(255), default="")
    candidate_email = Column(String(255), default="", index=True)
    resume_filename = Column(String(255), default="")
    resume_storage_key = Column(String(300), default="", index=True)
    content_hash = Column(String(64), default="", index=True)
    processing_status = Column(String(20), default="none", index=True)  # none|queued|processing|retry_wait|completed|failed
    resume_text = Column(Text, default="")
    parsed_profile = Column(Text, default="{}")   # JSON
    match_result = Column(Text, default="{}")      # JSON
    score = Column(Float, default=0.0, index=True)
    status = Column(String(20), default="new", index=True)  # new|reviewed|shortlisted|rejected|interview
    recruiter_notes = Column(Text, default="")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    job = relationship("Job", back_populates="applications")
    candidate = relationship("User", back_populates="applications")


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utcnow)

    memberships = relationship("OrgMembership", back_populates="organization",
                               cascade="all, delete-orphan")


class OrgMembership(Base):
    __tablename__ = "organization_memberships"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # owner > admin > recruiter > viewer
    role = Column(String(20), nullable=False, default="recruiter")
    created_at = Column(DateTime, default=utcnow)

    organization = relationship("Organization", back_populates="memberships")
    user = relationship("User")


class OrgInvitation(Base):
    __tablename__ = "organization_invitations"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    role = Column(String(20), nullable=False, default="recruiter")
    token = Column(String(64), unique=True, nullable=False, index=True)
    invited_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    organization = relationship("Organization")


class ProcessingJob(Base):
    """Durable resume-processing queue row. The database is the source of
    truth; workers claim rows atomically. State machine:

        queued -> processing -> completed
        processing -> retry_wait -> queued   (retry with backoff)
        processing -> failed                (attempts exhausted)
        failed -> queued                    (manual recruiter retry)
    """
    __tablename__ = "processing_jobs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    storage_key = Column(String(300), nullable=False)
    batch_id = Column(String(64), default="", index=True)
    status = Column(String(20), default="queued", index=True)
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    last_error_code = Column(String(60), default="")
    created_at = Column(DateTime, default=utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    retry_after = Column(DateTime, nullable=True)
    locked_at = Column(DateTime, nullable=True)  # crash-recovery lease

    organization = relationship("Organization")
    job = relationship("Job")
    application = relationship("Application")


class AuditEvent(Base):
    """Append-only audit log. No update/delete API exists; retention is
    enforced only by the admin purge endpoint. Never stores secrets,
    tokens, resume contents, or unnecessary PII."""
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    actor_email = Column(String(255), default="")   # operational identifier, not full PII payload
    action = Column(String(60), nullable=False, index=True)
    resource_type = Column(String(40), default="")
    resource_id = Column(String(64), default="")
    outcome = Column(String(20), default="success")  # success|denied|failure
    request_id = Column(String(64), default="", index=True)
    metadata_json = Column(Text, default="{}")       # sanitized, small
    created_at = Column(DateTime, default=utcnow, index=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
