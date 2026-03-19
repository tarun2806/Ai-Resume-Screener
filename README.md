# AI ScreenX 🚀 | Advanced AI Resume Screener & Career Matcher

**AI ScreenX** is a production-ready, full-stack AI platform designed to transform how candidates apply and recruiters hire. By moving beyond simple keyword-matching, AI ScreenX uses **Deep Semantic Intelligence** and a **Domain-Specific Skill Ontology** to understand the intent, context, and trajectory of a professional profile.

---

## 🛠 Project Purpose
The project serves two core personas:
- **Recruiters**: Instantly rank thousands of resumes against a job description (JD) using semantic meaning rather than just exact words.
- **Candidates**: Act as an AI-powered career assistant, providing transparent scoring and a step-by-step optimization plan to help candidates better align with their target roles.

---

## 🌟 Key Features

### 1. 🧠 Semantic Skill Ontology System
Unlike traditional ATS which fail if a candidate uses "JS" instead of "JavaScript," AI ScreenX uses a custom-built Knowledge Graph:
- **Skill Normalization**: Automatically maps variations (e.g., `Py` → `Python`, `K8s` → `Kubernetes`).
- **Semantic Expansion**: When a JD asks for "Machine Learning," the system automatically grants partial relevant credit for related expertise like "Deep Learning" or "NLP."
- **Weighted Inference**: Direct matches get 1.0 weight, while inferred/related skills get a slight decay factor (e.g., 0.85), mimicking how a human expert evaluates a resume.

### 2. 🔍 Expert AI Parsing Engine
A robust NLP pipeline that extracts more than just text:
- **Section Identification**: Logically segments the document into "Experience," "Education," "Projects," and "Skills."
- **Experience Analytics**: Dynamically calculates total years of professional experience by parsing date ranges and tenures across resume sections.
- **Entity Extraction**: Uses high-speed regex and NLP heuristics to reliably identify personal info, emails, and phone numbers even in complex layouts.

### 3. � Multi-Factor Weighted Scoring
The "Match Score" isn't a random percentage. It’s a transparent, weighted aggregation of:
- **Skill Overlap (40%)**: Hard technical alignment.
- **Semantic Alignment (40%)**: Understanding of the "intent" of the candidate’s work history.
- **Experience Fit (20%)**: Structural alignment with seniority requirements (years of experience).

### 4. � Actionable AI Career Advice
The system acts as a mentor by generating:
- **Missing Skill Detection**: Identifying exactly which high-priority JD skills are absent from the resume.
- **Dynamic Optimization Tips**: Specific, contextual suggestions for improving the profile.
- **Estimated Score Boost**: Calculates the potential impact (e.g., "+15% Boost") of each improvement, giving candidates a clear goal.

---

## 📐 System Architecture

### **Backend (Python / FastAPI)**
- **Orchestration**: A unified asynchronous pipeline that processes resumes and job descriptions concurrently using `asyncio` for maximum speed.
- **NLP Processing**: Built with **SpaCy** and custom rule-based heuristics for high-speed text extraction.
- **Semantic Engine**: Designed for **Sentence-BERT (SBERT)** integration to handle high-dimensional vector embeddings and cosine similarity.
- **Vector Search**: Integrated with **FAISS** for ultra-low-latency similarity search across large datasets.

### **Frontend (React / TypeScript)**
- **Modern UI**: Styled with **Tailwind CSS** for an "Enterprise SOC Dashboard" aesthetic.
- **Interactive DataViz**: Uses **Recharts** for real-time match breakdown and scoring visualizations.
- **Performance**: Powered by **Vite** for sub-second hot-reloads and optimized production bundles.

---

## 🎯 Interview Talking Points (Technical FAQ)

### "What makes this different from a basic keyword matcher?"
> "Keyword matchers are fragile; if a JD asks for 'React' and I have 'Frontend Engineer,' a regular ATS might miss the connection. My project uses a **Skill Ontology** and **Semantic Embeddings** to understand that those concepts are professionally adjacent. This decreases 'false negatives' in recruitment."

### "How did you handle large ML dependencies in production?"
> "I designed the system to be **modular and resilient**. For instance, I implemented a robust **Rule-based fallback engine** that ensures the core logic (parsing and matching) remains 100% functional even in resource-constrained environments where heavy ML distributions like SBERT might not be immediately available."

### "Explain the scoring logic."
> "I implemented a **weighted multi-factor scoring system**. We compute three distinct scores: a raw skill overlap, a semantic vector similarity, and an experience-tenure fit. We then aggregate these using weights (40/40/20) to provide a balanced evaluation that is fairer than simple word-counting."

---

## 📁 Project Structure (Organized)
```text
├── backend/            # FastAPI & AI Engine
│   ├── app/
│   │   ├── api/        # Unified API Routers (Resumes, Jobs, Matches)
│   │   ├── services/   # Core Logic (ResumeParser, SemanticMatcher, CareerAssistant)
│   │   └── ml/         # AI Knowledge (Skill Ontology, Vector Engine)
│   └── main.py         # App Entry Point (Middleware & Error Handlers)
├── frontend/           # React + Tailwind Dashboard
│   ├── src/
│   │   ├── pages/      # Candidate & Recruiter Dashboards
│   │   └── components/ # UI Atoms & Visualizations
└── README.md           # Documentation
```

**Built with Precision to Bridge the Gap Between Talent and Opportunity.** 🚀
