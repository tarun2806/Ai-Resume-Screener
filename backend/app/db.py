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
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    location = Column(String(255), default="")
    status = Column(String(20), default="open")  # open | closed | draft
    required_skills = Column(Text, default="[]")  # JSON list
    min_years = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    recruiter = relationship("User", back_populates="jobs")
    applications = relationship("Application", back_populates="job")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    candidate_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    candidate_name = Column(String(255), default="")
    candidate_email = Column(String(255), default="", index=True)
    resume_filename = Column(String(255), default="")
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


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
