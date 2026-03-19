from typing import List, Dict, Any, Set

class MatchingEvaluator:
    """
    Expert Evaluation System for Resume-Job Matching Models.
    Computes ranking metrics like Precision@K, Recall@K, and Top-K Accuracy.
    """
    
    @staticmethod
    def precision_at_k(actual_relevant: Set[str], predicted_ranking: List[str], k: int) -> float:
        """
        Calculates Precision@K: (number of relevant items in top-K) / K
        """
        if k <= 0: return 0.0
        
        top_k_predictions = predicted_ranking[:k]
        relevant_in_top_k = [res_id for res_id in top_k_predictions if res_id in actual_relevant]
        
        return len(relevant_in_top_k) / k

    @staticmethod
    def recall_at_k(actual_relevant: Set[str], predicted_ranking: List[str], k: int) -> float:
        """
        Calculates Recall@K: (number of relevant items in top-K) / (total relevant items)
        """
        if not actual_relevant: return 1.0
        if k <= 0: return 0.0
        
        top_k_predictions = predicted_ranking[:k]
        relevant_in_top_k = [res_id for res_id in top_k_predictions if res_id in actual_relevant]
        
        return len(relevant_in_top_k) / len(actual_relevant)

    @staticmethod
    def top_k_accuracy(actual_relevant: Set[str], predicted_ranking: List[str], k: int) -> bool:
        """
        Calculates if at least ONE relevant item is in the top-K results.
        """
        top_k_predictions = predicted_ranking[:k]
        return any(res_id in actual_relevant for res_id in top_k_predictions)

    def evaluate_model(self, evaluation_dataset: List[Dict[str, Any]], ks: List[int] = [1, 3, 5]) -> Dict[str, Any]:
        """
        Evaluates the model across an entire dataset for various K values.
        """
        summary_metrics = {f"p@{k}": [] for k in ks}
        summary_metrics.update({f"r@{k}": [] for k in ks})
        summary_metrics.update({f"acc@{k}": [] for k in ks})
        
        for record in evaluation_dataset:
            actual = set(record["relevant_resumes"])
            predicted = record["predicted_ranking"]
            
            for k in ks:
                summary_metrics[f"p@{k}"].append(self.precision_at_k(actual, predicted, k))
                summary_metrics[f"r@{k}"].append(self.recall_at_k(actual, predicted, k))
                summary_metrics[f"acc@{k}"].append(1.0 if self.top_k_accuracy(actual, predicted, k) else 0.0)
                
        # Average results
        final_scores = {metric: round(sum(scores) / len(scores), 4) for metric, scores in summary_metrics.items()}
        return final_scores

if __name__ == "__main__":
    # Sample Dataset Format
    # Each record represents a single Job Description and its associated candidates.
    sample_dataset = [
        {
            "job_id": "JD_PYTHON_101",
            "relevant_resumes": ["RES_ALICE", "RES_BOB"], # Ground Truth (Experts say these are good)
            "predicted_ranking": ["RES_ALICE", "RES_CHARLIE", "RES_BOB", "RES_DAVID"] # Model's ranking output
        },
        {
            "job_id": "JD_REACT_202",
            "relevant_resumes": ["RES_EVE"], 
            "predicted_ranking": ["RES_DAVID", "RES_ALICE", "RES_EVE"] 
        }
    ]
    
    evaluator = MatchingEvaluator()
    results = evaluator.evaluate_model(sample_dataset, ks=[1, 3])
    
    print("--- Model Evaluation Summary ---")
    import json
    print(json.dumps(results, indent=2))
    
    # Expected Output:
    # {
    #   "p@1": 0.5,   # Alice (JD1) was top, David (JD2) wasn't. Avg = (1 + 0)/2 = 0.5
    #   "r@1": 0.25,  # Alice is 1/2 of JD1, David is 0/1 of JD2. Avg = (0.5 + 0)/2 = 0.25
    #   "acc@1": 0.5  # At least one correct in top 1 for JD1, but not JD2.
    #   ... etc
    # }
