"""Seed synthetic demo data for the public placement demo.

Idempotent: safe to re-run. Use --reset to remove only demo-org data
(demo organization, its jobs/applications/memberships, and demo users)
before reseeding. Never touches unrelated users or organizations.

Run from the backend directory with production env vars set:
    python seed_demo.py [--reset]
"""
import hashlib
import io
import json
import os
import sys

os.environ.setdefault("ENVIRONMENT", "production")

from docx import Document  # noqa: E402

from app.auth import hash_password  # noqa: E402
from app.db import (  # noqa: E402
    Application, Job, Organization, OrgMembership, SessionLocal, User, init_db,
)
from app.services.analysis import run_analysis  # noqa: E402
from app.services.storage import generate_key, get_storage  # noqa: E402
from app.utils.parser import extract_text  # noqa: E402

DEMO_ORG_NAME = "AI ScreenX Demo"
DEMO_RECRUITER_EMAIL = os.getenv("DEMO_RECRUITER_EMAIL", "demo@aiscreenx.app")
DEMO_RECRUITER_PASSWORD = os.getenv("DEMO_RECRUITER_PASSWORD", "DemoScreenX2025")
DEMO_CANDIDATE_DOMAIN = "@demo-candidates.aiscreenx.app"

JOBS = [
    {
        "title": "Senior Backend Engineer (Python)",
        "location": "Bengaluru / Remote",
        "description": (
            "We are hiring a Senior Backend Engineer to design and operate our "
            "core platform. Requirements: 5+ years of professional software "
            "engineering experience, strong Python skills, FastAPI or Flask, "
            "PostgreSQL, SQLAlchemy, REST API design, Docker, and experience "
            "with asynchronous task queues such as Celery or Redis. Nice to "
            "have: Kubernetes, AWS, Terraform, machine learning experience. "
            "You will build scalable services, write clean tested code, and "
            "mentor junior engineers."
        ),
        "required_skills": ["python", "fastapi", "postgresql", "docker", "rest api"],
        "min_years": 5.0,
    },
    {
        "title": "Frontend Engineer (React)",
        "location": "Remote",
        "description": (
            "Join our product team as a Frontend Engineer. Requirements: 3+ "
            "years building production web applications, strong React and "
            "TypeScript skills, HTML, CSS, Tailwind CSS, state management with "
            "Redux or Zustand, REST API integration, and responsive design. "
            "Experience with Vite, Playwright testing, and accessibility is a "
            "plus. You will own UI features end to end and work closely with "
            "backend engineers."
        ),
        "required_skills": ["react", "typescript", "javascript", "tailwind css", "rest api"],
        "min_years": 3.0,
    },
    {
        "title": "Machine Learning Engineer",
        "location": "Hyderabad / Remote",
        "description": (
            "We are looking for a Machine Learning Engineer to build ranking "
            "and matching models. Requirements: 3+ years of ML experience, "
            "Python, PyTorch or TensorFlow, scikit-learn, NLP fundamentals, "
            "feature engineering, model evaluation, and experience deploying "
            "models to production. Experience with TF-IDF, embeddings, and "
            "explainable AI is highly valued."
        ),
        "required_skills": ["python", "machine learning", "pytorch", "scikit-learn", "nlp"],
        "min_years": 3.0,
    },
]

# Synthetic personas. Content is deliberately varied so matching produces
# meaningful matched/missing skill splits.
PERSONAS = [
    {
        "name": "Arjun Mehta", "email": "arjun.mehta" + DEMO_CANDIDATE_DOMAIN,
        "filename": "arjun_mehta_backend.docx",
        "text": """ARJUN MEHTA
Senior Backend Engineer | arjun.mehta@demo-candidates.aiscreenx.app | Bengaluru

SUMMARY
Backend engineer with 6 years of experience building scalable Python services.

EXPERIENCE
Senior Software Engineer, FinEdge Systems (2021-2025)
- Built FastAPI microservices handling 2M requests/day
- Designed PostgreSQL schemas with SQLAlchemy ORM
- Implemented Docker-based CI/CD pipelines on AWS
- Owned asynchronous job processing with Redis queues
Software Engineer, DataWorks (2019-2021)
- Developed REST APIs in Python and Flask
- Wrote unit tests with pytest

SKILLS
Python, FastAPI, Flask, PostgreSQL, SQLAlchemy, Docker, Redis, REST API,
AWS, Git, Linux, Kubernetes

EDUCATION
B.Tech Computer Science, VTU (2015-2019)
""",
    },
    {
        "name": "Priya Sharma", "email": "priya.sharma" + DEMO_CANDIDATE_DOMAIN,
        "filename": "priya_sharma_frontend.docx",
        "text": """PRIYA SHARMA
Frontend Engineer | priya.sharma@demo-candidates.aiscreenx.app | Remote

SUMMARY
Frontend engineer with 4 years building React applications.

EXPERIENCE
Frontend Developer, ShopSphere (2022-2025)
- Built React and TypeScript dashboards serving 50k users
- Implemented responsive designs with Tailwind CSS
- Integrated REST APIs with axios and React Query
UI Developer, PixelCraft (2021-2022)
- Developed JavaScript and CSS components

SKILLS
React, TypeScript, JavaScript, HTML, CSS, Tailwind CSS, Redux, REST API,
Vite, Git

EDUCATION
B.E. Information Technology, Mumbai University (2017-2021)
""",
    },
    {
        "name": "Rahul Verma", "email": "rahul.verma" + DEMO_CANDIDATE_DOMAIN,
        "filename": "rahul_verma_ml.docx",
        "text": """RAHUL VERMA
Machine Learning Engineer | rahul.verma@demo-candidates.aiscreenx.app | Hyderabad

SUMMARY
ML engineer with 4 years applying NLP and ranking models.

EXPERIENCE
Machine Learning Engineer, Rankify AI (2022-2025)
- Built TF-IDF and embedding-based candidate-job matching
- Trained scikit-learn and PyTorch ranking models
- Designed explainable scoring with feature attribution
Data Scientist, Insight Labs (2021-2022)
- Performed feature engineering and model evaluation

SKILLS
Python, Machine Learning, PyTorch, scikit-learn, NLP, TF-IDF, pandas,
numpy, SQL, Docker, Git

EDUCATION
M.Tech Artificial Intelligence, IIT Hyderabad (2019-2021)
""",
    },
    {
        "name": "Sneha Iyer", "email": "sneha.iyer" + DEMO_CANDIDATE_DOMAIN,
        "filename": "sneha_iyer_fullstack.docx",
        "text": """SNEHA IYER
Full Stack Developer | sneha.iyer@demo-candidates.aiscreenx.app | Bengaluru

SUMMARY
Full stack developer with 5 years across React frontends and Python backends.

EXPERIENCE
Software Engineer, CloudKart (2021-2025)
- Built React TypeScript storefront and FastAPI order services
- Worked with PostgreSQL, Docker, and Redis queues
- Implemented REST APIs consumed by mobile and web clients
Junior Developer, WebGen (2020-2021)
- Developed JavaScript and Node.js features

SKILLS
React, TypeScript, JavaScript, Python, FastAPI, Node.js, PostgreSQL,
Docker, REST API, Tailwind CSS, Git

EDUCATION
B.Tech Computer Science, Anna University (2016-2020)
""",
    },
    {
        "name": "Vikram Singh", "email": "vikram.singh" + DEMO_CANDIDATE_DOMAIN,
        "filename": "vikram_singh_devops.docx",
        "text": """VIKRAM SINGH
DevOps Engineer | vikram.singh@demo-candidates.aiscreenx.app | Pune

SUMMARY
DevOps engineer focused on infrastructure, CI/CD, and cloud.

EXPERIENCE
DevOps Engineer, InfraScale (2022-2025)
- Managed Kubernetes clusters and Terraform on AWS
- Built deployment pipelines with Docker and GitLab CI
- Implemented monitoring with Prometheus and Grafana
System Administrator, NetServe (2020-2022)
- Administered Linux servers and nginx

SKILLS
Kubernetes, Docker, AWS, Terraform, Linux, CI/CD, Python (scripting),
Git, Jenkins, Prometheus

EDUCATION
B.E. Electronics, Pune University (2016-2020)
""",
    },
    {
        "name": "Ananya Rao", "email": "ananya.rao" + DEMO_CANDIDATE_DOMAIN,
        "filename": "ananya_rao_junior.docx",
        "text": """ANANYA RAO
Junior Software Developer | ananya.rao@demo-candidates.aiscreenx.app | Chennai

SUMMARY
Recent graduate with internship experience in web development.

EXPERIENCE
Software Intern, WebSoft (2024)
- Assisted in building React components and fixing bugs
- Wrote JavaScript and basic Python scripts
- Participated in code reviews

SKILLS
JavaScript, React (basics), HTML, CSS, Python (basics), Git

EDUCATION
B.Tech Computer Science, SRM University (2020-2024)
""",
    },
    {
        "name": "Karan Patel", "email": "karan.patel" + DEMO_CANDIDATE_DOMAIN,
        "filename": "karan_patel_data.docx",
        "text": """KARAN PATEL
Data Analyst | karan.patel@demo-candidates.aiscreenx.app | Ahmedabad

SUMMARY
Data analyst with 3 years turning data into decisions.

EXPERIENCE
Data Analyst, RetailMetrics (2022-2025)
- Built dashboards in SQL and Python pandas
- Ran A/B analyses and cohort studies
- Automated reporting with Excel and Looker
Business Analyst, FinServe (2021-2022)
- Gathered requirements and wrote SQL queries

SKILLS
SQL, Python, pandas, Excel, data visualization, statistics,
Tableau, REST API basics, Git

EDUCATION
B.Sc Statistics, Gujarat University (2018-2021)
""",
    },
    {
        "name": "Meera Nair", "email": "meera.nair" + DEMO_CANDIDATE_DOMAIN,
        "filename": "meera_nair_ml.docx",
        "text": """MEERA NAIR
Applied Scientist | meera.nair@demo-candidates.aiscreenx.app | Kochi

SUMMARY
Applied scientist with 5 years in NLP and recommendation systems.

EXPERIENCE
Applied Scientist, ContentRank (2021-2025)
- Built transformer-based ranking and TF-IDF retrieval systems
- Evaluated models with offline metrics and A/B tests
- Published internal papers on explainable recommendations
Research Assistant, IIIT (2019-2021)
- Implemented NLP pipelines in Python and scikit-learn

SKILLS
Python, Machine Learning, PyTorch, TensorFlow, scikit-learn, NLP,
TF-IDF, embeddings, pandas, numpy, SQL, Docker, Git

EDUCATION
Ph.D. Computer Science, IISc Bangalore (2015-2021)
""",
    },
]

STATUSES = ["new", "reviewed", "shortlisted", "interview", "new", "rejected", "reviewed", "interview"]


def _docx_bytes(text: str) -> bytes:
    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _reset_demo(db) -> None:
    org = db.query(Organization).filter(Organization.name == DEMO_ORG_NAME).first()
    if org:
        job_ids = [j.id for j in db.query(Job).filter(Job.organization_id == org.id).all()]
        if job_ids:
            db.query(Application).filter(Application.job_id.in_(job_ids)).delete(
                synchronize_session=False)
        db.query(Job).filter(Job.organization_id == org.id).delete(synchronize_session=False)
        member_ids = [m.user_id for m in db.query(OrgMembership).filter(
            OrgMembership.org_id == org.id).all()]
        db.query(OrgMembership).filter(OrgMembership.org_id == org.id).delete(
            synchronize_session=False)
        demo_emails = [DEMO_RECRUITER_EMAIL] + [p["email"] for p in PERSONAS]
        db.query(User).filter(User.email.in_(demo_emails)).delete(synchronize_session=False)
        db.delete(org)
    db.commit()


def main() -> None:
    reset = "--reset" in sys.argv
    init_db()
    db = SessionLocal()
    try:
        if reset:
            _reset_demo(db)

        org = db.query(Organization).filter(Organization.name == DEMO_ORG_NAME).first()
        if not org:
            org = Organization(name=DEMO_ORG_NAME)
            db.add(org)
            db.flush()

        recruiter = db.query(User).filter(User.email == DEMO_RECRUITER_EMAIL).first()
        if not recruiter:
            recruiter = User(
                email=DEMO_RECRUITER_EMAIL,
                password_hash=hash_password(DEMO_RECRUITER_PASSWORD),
                name="Demo Recruiter",
                role="recruiter",
            )
            db.add(recruiter)
            db.flush()
        if not db.query(OrgMembership).filter(
                OrgMembership.org_id == org.id, OrgMembership.user_id == recruiter.id).first():
            db.add(OrgMembership(org_id=org.id, user_id=recruiter.id, role="owner"))

        existing_jobs = {j.title: j for j in db.query(Job).filter(
            Job.organization_id == org.id).all()}
        jobs = []
        for spec in JOBS:
            job = existing_jobs.get(spec["title"])
            if not job:
                job = Job(
                    recruiter_id=recruiter.id,
                    organization_id=org.id,
                    title=spec["title"],
                    description=spec["description"],
                    location=spec["location"],
                    status="open",
                    required_skills=json.dumps(spec["required_skills"]),
                    min_years=spec["min_years"],
                )
                db.add(job)
                db.flush()
            jobs.append(job)

        storage = get_storage()
        created = 0
        for persona in PERSONAS:
            content = _docx_bytes(persona["text"])
            filename = persona["filename"]
            chash = hashlib.sha256(content).hexdigest()
            text = extract_text(content, filename)
            for job in jobs:
                dup = db.query(Application).filter(
                    Application.job_id == job.id, Application.content_hash == chash).first()
                if dup:
                    continue
                analysis = run_analysis(text, job.description)
                analysis.pop("_resume_text", None)
                candidate = analysis.get("candidate", {})
                storage_key = generate_key(org.id, ".docx")
                try:
                    storage.put(storage_key, content)
                except Exception as exc:
                    print(f"storage put failed for {filename}: {exc}")
                    storage_key = ""
                app = Application(
                    job_id=job.id,
                    candidate_name=candidate.get("name") or persona["name"],
                    candidate_email=persona["email"],
                    resume_filename=filename,
                    resume_storage_key=storage_key,
                    content_hash=chash,
                    resume_text=text,
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
                    status=STATUSES[created % len(STATUSES)],
                    processing_status="completed" if storage_key else "none",
                )
                db.add(app)
                created += 1
        db.commit()
        print(f"Demo seeded: org '{DEMO_ORG_NAME}' (id={org.id}), "
              f"recruiter {DEMO_RECRUITER_EMAIL}, {len(jobs)} jobs, "
              f"{created} new applications.")
        print(f"Demo login password: {DEMO_RECRUITER_PASSWORD} "
              f"(override with DEMO_RECRUITER_PASSWORD env var)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
