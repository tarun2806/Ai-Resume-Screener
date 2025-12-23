# Implementation Plan - AI Resume Screener & Job Matcher

## Project Overview
A production-grade AI system to parse resumes, match them with job descriptions using transformer embeddings, and provide explainable scores and skill recommendations.

## Tech Stack
- **Backend**: FastAPI, Python 3.10+, SQLAlchemy (PostgreSQL).
- **AI/ML**: SpaCy (NLP), Sentence-Transformers (Embeddings), Scikit-learn, PyMuPDF (PDF parsing).
- **Frontend**: React (Vite), Tailwind CSS, Lucide-react (Icons), Recharts (Charts).
- **Tooling**: Docker, Pip.

## Phase 1: Foundation & Setup
- [ ] Initialize project structure (`backend/`, `frontend/`).
- [ ] Backend setup: FastAPI, DB models (PostgreSQL compatibility), logging.
- [ ] Frontend setup: Vite + React + Tailwind + Lucide.

## Phase 2: AI Core (The "Brain")
- [ ] **Resume Parser**:
    - Extract text from PDF/DOCX.
    - Use SpaCy for NER (Name, Contact, Education, Org).
    - Pattern matching for Skills extraction.
- [ ] **Embedding Engine**:
    - Load `all-MiniLM-L6-v2` via Sentence-Transformers.
    - Function to vectorize text (Resumes and JDs).
- [ ] **Matching Logic**:
    - Weighted scoring algorithm:
        - Embeddings Similarity (40%)
        - Skill Overlap (40%)
        - Experience/Education Factor (20%)

## Phase 3: Backend API Development
- [ ] Resume CRUD & Upload.
- [ ] Job Description CRUD.
- [ ] Match API: Process match request and return detailed breakdown.
- [ ] Recommendation API: Identify missing skills.

## Phase 4: Frontend Development (Premium UI/UX)
- [ ] **Shared Components**: Layout, Sidebar, Uploaders, Score Cards.
- [ ] **Recruiter Dashboard**: 
    - JD Management.
    - Candidate Ranking List.
    - Comparison View.
- [ ] **Candidate Dashboard**:
    - Resume Upload.
    - "Why I matched?" Explanation.
    - Skill Gap Analysis visualization.

## Phase 5: Polish & Explainable AI
- [ ] Integrate SHAP or custom attention-based visualization for match reasoning.
- [ ] Add bulk upload feature.
- [ ] Final UI/UX pass (animations, glassmorphism).

## Phase 6: Deployment & Documentation
- [ ] Dockerfile & Docker-compose.
- [ ] README.md with setup instructions.
- [ ] Sample data generation script.
