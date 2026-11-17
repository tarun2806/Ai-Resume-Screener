"""
Matching-engine benchmark. Compares semantic similarity strategies on the
labeled dataset in eval/dataset.json.

Engines:
  tfidf  - current production SemanticMatcher (TF-IDF cosine semantic component)
  sbert  - SentenceTransformer embeddings (all-MiniLM-L6-v2) for semantic component
  hybrid - mean of tfidf and sbert semantic components

Skill-overlap and experience components are identical across engines so the
comparison isolates semantic matching quality. Skill/experience weights come
from the production SemanticMatcher.

Metrics per job (candidates ranked by score):
  Precision@K, Recall@K (binary relevance >=1), NDCG@K (graded 0-2), MRR.

Run with the sbert venv:
  /tmp/sbert_venv/bin/python eval/run_evaluation.py
or without SBERT (tfidf only):
  python3 eval/run_evaluation.py --tfidf-only
"""

import argparse
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.nlp_processor import AdvancedNLPProcessor
from app.services.semantic_matcher import SemanticMatcher, _text_cosine
from app.services.analysis import extract_min_years
from app.ml.skill_vocabulary import find_skills_in_text

DATASET_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset.json")


def dcg(rels):
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def ndcg_at_k(ranked_rels, k):
    actual = [r for _, r in ranked_rels[:k]]
    ideal = sorted([r for _, r in ranked_rels], reverse=True)[:k]
    if not ideal or dcg(ideal) == 0:
        return 0.0
    return dcg(actual) / dcg(ideal)


def precision_at_k(ranked_rels, k):
    top = ranked_rels[:k]
    return sum(1 for _, r in top if r >= 1) / k if k else 0.0


def recall_at_k(ranked_rels, k, total_relevant):
    if not total_relevant:
        return 0.0
    return sum(1 for _, r in ranked_rels[:k] if r >= 1) / total_relevant


def mrr(ranked_rels):
    for i, (_, r) in enumerate(ranked_rels):
        if r >= 2:
            return 1.0 / (i + 1)
    for i, (_, r) in enumerate(ranked_rels):
        if r >= 1:
            return 1.0 / (i + 1)
    return 0.0


class SbertEncoder:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer
        t0 = time.time()
        self.model = SentenceTransformer(model_name)
        self.load_seconds = time.time() - t0

    def sim(self, a, b):
        import numpy as np
        emb = self.model.encode([a, b], normalize_embeddings=True)
        return float(np.dot(emb[0], emb[1]))


def components(resume_text, jd_text, resume_exp, jd_min_years, matcher):
    """Shared non-semantic components from production matcher logic."""
    resume_data = {
        "raw_text": resume_text,
        "skills": [h["name"] for h in find_skills_in_text(resume_text)],
        "experience_years": resume_exp,
        "name": "eval",
    }
    jd_data = {
        "raw_text": jd_text,
        "required_skills": [h["name"] for h in find_skills_in_text(jd_text)],
        "min_years_experience": jd_min_years or 0,
    }
    r = matcher.score_candidate(resume_data, jd_data)
    return r["breakdown"], resume_data, jd_data


def score_with_semantic(sem_sim, breakdown):
    """Mirror the production weighted formula (all five components)."""
    w = SemanticMatcher().weights
    return (
        sem_sim * w.get("semantic_similarity", 0.30)
        + (breakdown["skill_overlap"] / 100) * w.get("skill_overlap", 0.35)
        + (breakdown.get("preferred_match", breakdown["skill_overlap"]) / 100) * w.get("preferred_match", 0.05)
        + (breakdown["experience_fit"] / 100) * w.get("experience_fit", 0.15)
        + (breakdown.get("education_fit", 100.0) / 100) * w.get("education_fit", 0.15)
    ) * 100


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tfidf-only", action="store_true")
    ap.add_argument("--model", default="all-MiniLM-L6-v2")
    args = ap.parse_args()

    dataset = json.load(open(DATASET_PATH))
    processor = AdvancedNLPProcessor()
    matcher = SemanticMatcher()

    sbert = None
    if not args.tfidf_only:
        try:
            sbert = SbertEncoder(args.model)
            print(f"SBERT model loaded in {sbert.load_seconds:.1f}s")
        except Exception as e:
            print(f"SBERT unavailable: {e}")

    # Precompute parsed resume/JD once (shared across engines)
    jobs = []
    for job in dataset["jobs"]:
        jd_parsed = processor.process_jd(job["description"])
        jd_min = extract_min_years(job["description"])
        cands = []
        for c in job["candidates"]:
            parsed = processor.process_resume(c["resume"])
            exp = parsed["expert_data"]["experience"]["total_years"]
            cands.append({
                "id": c["id"],
                "relevance": c["relevance"],
                "raw_text": c["resume"],
                "exp": exp,
            })
        jobs.append({"id": job["id"], "jd_text": job["description"], "min_years": jd_min, "cands": cands})

    engines = ["tfidf"] + (["sbert", "hybrid"] if sbert else [])
    report = {}

    for engine in engines:
        per_job = {}
        latencies = []
        for job in jobs:
            scored = []
            for c in job["cands"]:
                t0 = time.time()
                breakdown, _, _ = components(c["raw_text"], job["jd_text"], c["exp"], job["min_years"], matcher)
                if engine == "tfidf":
                    sem = _text_cosine(c["raw_text"], job["jd_text"])
                elif engine == "sbert":
                    sem = sbert.sim(c["raw_text"], job["jd_text"])
                else:
                    sem = (_text_cosine(c["raw_text"], job["jd_text"]) + sbert.sim(c["raw_text"], job["jd_text"])) / 2
                latencies.append(time.time() - t0)
                scored.append((c["id"], c["relevance"], score_with_semantic(sem, breakdown)))
            scored.sort(key=lambda x: x[2], reverse=True)
            rels = [(cid, rel) for cid, rel, _ in scored]
            total_rel = sum(1 for _, r in rels if r >= 1)
            per_job[job["id"]] = {
                "ranking": [(cid, round(s, 1), rel) for cid, rel, s in scored],
                "p@2": precision_at_k(rels, 2),
                "p@3": precision_at_k(rels, 3),
                "r@2": recall_at_k(rels, 2, total_rel),
                "r@3": recall_at_k(rels, 3, total_rel),
                "ndcg@3": ndcg_at_k(rels, 3),
                "mrr": mrr(rels),
            }
        n = len(per_job)
        report[engine] = {
            "per_job": per_job,
            "avg": {
                "p@2": round(sum(j["p@2"] for j in per_job.values()) / n, 3),
                "p@3": round(sum(j["p@3"] for j in per_job.values()) / n, 3),
                "r@2": round(sum(j["r@2"] for j in per_job.values()) / n, 3),
                "r@3": round(sum(j["r@3"] for j in per_job.values()) / n, 3),
                "ndcg@3": round(sum(j["ndcg@3"] for j in per_job.values()) / n, 3),
                "mrr": round(sum(j["mrr"] for j in per_job.values()) / n, 3),
                "mean_latency_ms": round(sum(latencies) / len(latencies) * 1000, 1),
            },
        }

    # Determinism check: run tfidf twice on first job/candidate
    j0, c0 = jobs[0], jobs[0]["cands"][0]
    b1, _, _ = components(c0["raw_text"], j0["jd_text"], c0["exp"], j0["min_years"], matcher)
    s1 = score_with_semantic(_text_cosine(c0["raw_text"], j0["jd_text"]), b1)
    b2, _, _ = components(c0["raw_text"], j0["jd_text"], c0["exp"], j0["min_years"], matcher)
    s2 = score_with_semantic(_text_cosine(c0["raw_text"], j0["jd_text"]), b2)
    report["determinism"] = {"tfidf_identical": s1 == s2, "score": round(s1, 4)}

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps({e: report[e]["avg"] for e in engines}, indent=2))
    print(f"Report written to {out}")


if __name__ == "__main__":
    main()
