# 🧠 AI ScreenX – Explainable AI Resume Screener & Job Matcher

AI ScreenX is an **Explainable AI–powered resume screening system** that intelligently matches candidate resumes with job descriptions using **semantic understanding, partial skill matching, and transparent scoring**.

Unlike traditional keyword-based ATS tools, AI ScreenX focuses on **contextual relevance, transferable skills, and fairness**, making it suitable for real-world hiring and career optimization.

---

## 🚀 Key Features

### 🔍 Semantic Resume–Job Matching
- Uses **SBERT (Sentence-BERT) embeddings** for deep semantic similarity
- Detects **partial and transferable skill matches**
- Avoids strict keyword dependency

### 📊 Explainable AI Scoring
- Transparent score breakdown:
  - **Skills Match (40%)**
  - **Experience Relevance (30%)**
  - **Semantic Alignment (20%)**
  - **Resume Quality (10%)**
- Confidence banding:
  - Weak | Partial | **Potential** | Strong Match

### 🧩 Semantic Skill Audit
Skills are grouped into:
- **Domain Skills**
- **Tools & Technologies**
- **Soft Skills**

Each skill is labeled as:
- ✅ Detected (explicitly present)
- ⚠️ Inferred (semantically derived)
- ❌ Missing (required but absent)

### 🧠 AI-Driven Improvement Plan
- JD-aware, gap-based recommendations
- Each suggestion includes **estimated score impact**
- Acts as a **career assistant**, not just a scorer

### ⚖️ Fair & Bias-Aware Design
- Reduces over-penalization for non-traditional backgrounds
- Focuses on **skills and experience**, not brand bias
- Encourages achievable improvement paths


### Backend
- **Python**
- **FastAPI**
- **Sentence-BERT (SBERT)**
- **spaCy**
- **Scikit-learn**

### Frontend
- **React**
- **Tailwind CSS**
- **Modern Dashboard UI**

### AI Techniques
- Transformer-based embeddings
- Cosine similarity
- Skill ontology expansion
- Partial & fuzzy matching
- Explainable scoring logic

---
