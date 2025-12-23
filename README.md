# AI ScreenX 🚀 | Advanced AI Resume Screener & Career Matcher

**AI ScreenX** is a sophisticated, full-stack AI platform designed to bridge the gap between candidates and recruiters using state-of-the-art Natural Language Processing (NLP). Unlike traditional keyword-matchers, AI ScreenX uses semantic vector embeddings and a custom domain ontology to understand **intent**, **transferable skills**, and **career trajectory**.

---

## 🌟 Key Features

### 🧠 Semantic Intelligence

- **Transformer-based SBERT Integration**: Uses `all-MiniLM-L6-v2` to generate 384-dimensional dense vectors for semantic similarity analysis.
- **Fuzzy Skill Matching**: Rewards candidates with "Inferred Skills" (e.g., recognizing that an 'ERP' background maps to 'SAP' or 'Oracle').
- **Weighted Scoring Fairness**: Aggregates Skill Match (40%), Experience Relevance (30%), Semantic Alignment (20%), and Resume Quality (10%).

### 🔍 Explainable AI (XAI)

- **Score Breakdown**: Transparent visualization of exactly how a candidate was scored.
- **Natural Language Explanations**: AI-generated reasoning for the match score.
- **AI Improvement Plan**: Dynamic, JD-aware suggestions that specify the "Estimated Score Impact" for each resume optimization.

### 💼 Dual Dashboards

- **Candidate Hub**: Upload resumes and receive instant, actionable feedback to align with target JDs.
- **Recruiter Command Center**: Rank hundreds of candidates instantly based on AI-calculated fit rather than simple keywords.

---

## 🛠 Tech Stack

- **Backend**: Python, FastAPI, SpaCy (NLP), Sentence-Transformers (BERT), PyMuPDF.
- **Frontend**: React, TypeScript, Tailwind CSS, Lucide-React, Recharts.
- **Environment**: Virtual Environment (Venv), Docker-ready.

---

## 📐 System Architecture

1. **Extraction Layer**: PyMuPDF and python-docx extract raw text from candidate credentials.
2. **NLP Engine**: SpaCy cleans the text and extracts explicit skills, entities, and education.
3. **Ontology Layer**: A custom domain ontology expands JD requirements into related semantic concepts.
4. **Vector Analysis**: Sentence-BERT computes the Cosine Similarity between the Resume and the Job Description vectors.
5. **Heuristic Filter**: Final scoring logic applies weights to calculate structural quality and experience relevance.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- Node.js 18+

### 1. Backend Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 -m spacy download en_core_web_md
python main.py
```

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

---

## 🎯 Interview Talking Points (Technical FAQ)

- **Why SBERT?** "Keywords are fragile. SBERT captures context. It understands that 'Financial Operations' and 'Accounts Payable' are professionally adjacent."
- **Bias Mitigation**: "The system is structure-blind. It evaluates candidates based on the mathematical vector of their experience, not their choice of template or fonts."
- **Transferable Skills**: "By using a weighted ontology, we ensure that a candidate with 'Procure to Pay' experience is rewarded when a JD asks for 'Invoicing'—even if the exact word is missing."

---

## 📁 Project Structure

```text
├── backend/            # FastAPI & AI Logic
│   ├── app/
│   │   ├── api/        # Routers
│   │   ├── services/   # Semantic Engine & Parser
│   │   └── ml/         # Domain Ontology
├── frontend/           # React + Tailwind Dashboard
│   ├── src/
│   │   ├── pages/      # Candidate & Recruiter Views
│   │   └── components/ # UI Atoms
└── README.md           # Documentation
```

---

**Developed with Precision as a Career AI Assistant.** 🚀
