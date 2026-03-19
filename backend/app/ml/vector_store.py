import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional

class ResumeVectorStore:
    """
    Expert Scalable Semantic Search system using FAISS (Facebook AI Similarity Search).
    """
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2', dimension: int = 384):
        # 1. Initialize SBERT for Emebddings (default is 384 for MiniLM)
        self.model = SentenceTransformer(model_name)
        self.dimension = dimension
        
        # 2. Initialize FAISS Index (L2 Distance for Similarity)
        # Using IndexFlatIP for Cosine Similarity (requires normalized vectors)
        self.index = faiss.IndexFlatIP(self.dimension)
        
        # 3. Resume ID mapping
        self.resume_ids: List[str] = []

    def add_resumes(self, resumes: List[Dict[str, Any]]):
        """
        Embeds a batch of resumes and adds them to the FAISS index.
        """
        if not resumes:
            return
            
        texts = [res["raw_text"] for res in resumes]
        ids = [res["id"] for res in resumes]
        
        # Create Embeddings
        embeddings = self.model.encode(texts, convert_to_tensor=False)
        embeddings = np.array(embeddings).astype('float32')
        
        # Normalize for Cosine Similarity
        faiss.normalize_L2(embeddings)
        
        # Add to index
        self.index.add(embeddings)
        self.resume_ids.extend(ids)
        
        print(f"Index Update: Added {len(resumes)} resumes. Total in index: {self.index.ntotal}")

    def search(self, jd_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Performs a semantic similarity search for a given Job Description.
        """
        # Embed JD
        jd_emb = self.model.encode([jd_text], convert_to_tensor=False)
        jd_emb = np.array(jd_emb).astype('float32')
        faiss.normalize_L2(jd_emb)
        
        # Search FAISS
        # D: distances (cosine similarity since we normalized)
        # I: indices
        D, I = self.index.search(jd_emb, min(top_k, self.index.ntotal))
        
        results = []
        for dist, idx in zip(D[0], I[0]):
            if idx == -1: continue # No more results
            
            results.append({
                "resume_id": self.resume_ids[idx],
                "similarity_score": round(float(dist) * 100, 2)
            })
            
        return results

    def save_index(self, path: str):
        """Save the FAISS index to disk."""
        faiss.write_index(self.index, f"{path}.index")
        # You'd also save self.resume_ids as a separate mapping file.

if __name__ == "__main__":
    # Example Usage
    resumes = [
      {"id": "RES_1", "raw_text": "Senior Data Scientist at Google, 10 years experience with Python and ML."},
      {"id": "RES_2", "raw_text": "Junior Frontend Dev with React and Tailwind experience."},
      {"id": "RES_3", "raw_text": "DevOps Engineer with AWS, Kubernetes and Docker."},
      {"id": "RES_4", "raw_text": "Product Manager with 5 years experience in SaaS."}
    ]
    
    # 1. Initialize and Index
    store = ResumeVectorStore()
    store.add_resumes(resumes)
    
    # 2. Search for a JD
    jd_query = "Looking for a specialist in cloud infrastructure and container orchestration."
    top_matches = store.search(jd_query, top_k=2)
    
    print("\n--- Semantic Search Results ---")
    import json
    print(json.dumps(top_matches, indent=2))
    
    # Expected: RES_3 (DevOps) should be #1.
