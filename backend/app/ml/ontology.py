import json
import os
from typing import Dict, List, Set, Any

# Load Ontology from JSON
ONTOLOGY_PATH = os.path.join(os.path.dirname(__file__), "skill_ontology.json")

def load_ontology() -> Dict[str, Any]:
    try:
        with open(ONTOLOGY_PATH, 'r') as f:
            return json.load(f)["skills"]
    except Exception as e:
        print(f"Error loading ontology: {e}")
        return {}

SKILL_ONTOLOGY = load_ontology()

def expand_skills_semantically(skills: List[str]) -> Dict[str, float]:
    """
    Expands skills using the ontology.
    - 1.0 for manual/direct matches.
    - 0.8-0.9 for semantic inferences based on ontology relationships.
    """
    expanded = {s.lower(): 1.0 for s in skills}
    
    for skill in skills:
        skill_lower = skill.lower().strip()
        
        # 1. Direct Match in Ontology
        if skill_lower in SKILL_ONTOLOGY:
            _apply_relations(skill_lower, expanded)
        
        # 2. Synonym / Implicit Match
        for canonical, data in SKILL_ONTOLOGY.items():
            if skill_lower in data.get("synonyms", []):
                expanded[canonical] = 1.0 # If they mention a synonym, they mention the canonical
                _apply_relations(canonical, expanded)
                
    return expanded

def _apply_relations(skill_key: str, expanded_dict: Dict[str, float]):
    """Recursively applies related skill weights."""
    related = SKILL_ONTOLOGY[skill_key].get("related", {})
    for rel_skill, base_weight in related.items():
        # Apply a small decay factor for inferred vs direct skills
        inferred_weight = base_weight * 0.85
        if rel_skill not in expanded_dict or inferred_weight > expanded_dict[rel_skill]:
            expanded_dict[rel_skill.lower()] = inferred_weight

def get_skill_category(skill_name: str) -> str:
    """Classifies skills using ontology categories."""
    skill_lower = skill_name.lower().strip()
    
    # 1. Direct Check
    if skill_lower in SKILL_ONTOLOGY:
        return SKILL_ONTOLOGY[skill_lower].get("category", "General Skill").title()
    
    # 2. Check Synonyms
    for canonical, data in SKILL_ONTOLOGY.items():
        if skill_lower in data.get("synonyms", []):
            return data.get("category", "General Skill").title()
            
    # 3. Check if it's a related skill of something we know
    for canonical, data in SKILL_ONTOLOGY.items():
        if skill_lower in data.get("related", {}):
            return "Domain Skill"
            
    return "Domain Skill"

if __name__ == "__main__":
    # Test
    test_skills = ["Python", "JS", "ML"]
    expanded = expand_skills_semantically(test_skills)
    print("Test Expansion Results:")
    for s, w in sorted(expanded.items(), key=lambda x: x[1], reverse=True):
        print(f"- {s}: {w:.2f}")
