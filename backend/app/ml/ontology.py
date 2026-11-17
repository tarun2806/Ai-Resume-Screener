import json
import os
from typing import Dict, List, Any

from app.ml.skill_taxonomy import SKILL_CATEGORIES, SKILL_RELATIONS

# Load base Ontology from JSON (legacy small graph, kept for compatibility)
ONTOLOGY_PATH = os.path.join(os.path.dirname(__file__), "skill_ontology.json")


def load_ontology() -> Dict[str, Any]:
    try:
        with open(ONTOLOGY_PATH, 'r') as f:
            return json.load(f)["skills"]
    except Exception as e:
        print(f"Error loading ontology: {e}")
        return {}


SKILL_ONTOLOGY = load_ontology()

# Merged relation graph: JSON ontology + taxonomy relations (taxonomy wins on conflict)
_MERGED_RELATIONS: Dict[str, Dict[str, float]] = {}
for canonical, data in SKILL_ONTOLOGY.items():
    _MERGED_RELATIONS[canonical.lower()] = {
        k.lower(): v for k, v in data.get("related", {}).items()
    }
for canonical, rels in SKILL_RELATIONS.items():
    key = canonical.lower()
    _MERGED_RELATIONS.setdefault(key, {}).update({k.lower(): v for k, v in rels.items()})


def expand_skills_semantically(skills: List[str]) -> Dict[str, float]:
    """
    Expands skills using ontology + taxonomy relations.
    - 1.0 for manual/direct matches.
    - 0.4-0.95 for semantic inferences based on skill relationships.
    """
    expanded = {s.lower(): 1.0 for s in skills}

    for skill in skills:
        skill_lower = skill.lower().strip()

        # Direct relation lookup (canonical or lowercase key)
        relations = _MERGED_RELATIONS.get(skill_lower) or _MERGED_RELATIONS.get(
            _canonical_key(skill_lower)
        )
        if relations:
            _apply_relations(relations, expanded)

        # JSON-ontology synonym handling (legacy)
        for canonical, data in SKILL_ONTOLOGY.items():
            if skill_lower in data.get("synonyms", []):
                expanded[canonical] = 1.0
                rel = _MERGED_RELATIONS.get(canonical, {})
                _apply_relations(rel, expanded)

    return expanded


def related_skills_for(skill_name: str) -> Dict[str, float]:
    """
    Return {related_skill_lower: weight} from the merged relation graph.
    Weights are relation strengths (0.4-0.95); they indicate relatedness,
    NOT equivalence — callers must treat them as partial credit only.
    """
    key = skill_name.lower().strip()
    from app.ml.skill_vocabulary import canonical_skill
    canonical = canonical_skill(key)
    if canonical:
        key = canonical.lower()
    return dict(_MERGED_RELATIONS.get(key, {}))


def _canonical_key(skill_lower: str) -> str:
    from app.ml.skill_vocabulary import canonical_skill
    c = canonical_skill(skill_lower)
    return c.lower() if c else skill_lower


def _apply_relations(relations: Dict[str, float], expanded_dict: Dict[str, float]):
    """Apply related-skill weights with decay for inferred skills."""
    for rel_skill, base_weight in relations.items():
        inferred_weight = base_weight * 0.85
        if rel_skill not in expanded_dict or inferred_weight > expanded_dict[rel_skill]:
            expanded_dict[rel_skill] = inferred_weight


def get_skill_category(skill_name: str) -> str:
    """Classifies a skill using taxonomy categories, then legacy ontology."""
    from app.ml.skill_vocabulary import canonical_skill

    canonical = canonical_skill(skill_name) or skill_name
    cat = SKILL_CATEGORIES.get(canonical)
    if cat:
        return cat.replace("_", " ").title()

    skill_lower = skill_name.lower().strip()
    if skill_lower in SKILL_ONTOLOGY:
        return SKILL_ONTOLOGY[skill_lower].get("category", "General Skill").title()
    for canonical_key, data in SKILL_ONTOLOGY.items():
        if skill_lower in data.get("synonyms", []):
            return data.get("category", "General Skill").title()
    return "Domain Skill"


if __name__ == "__main__":
    test_skills = ["Python", "JS", "ML"]
    expanded = expand_skills_semantically(test_skills)
    print("Test Expansion Results:")
    for s, w in sorted(expanded.items(), key=lambda x: x[1], reverse=True):
        print(f"- {s}: {w:.2f}")
