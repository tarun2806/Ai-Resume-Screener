from typing import Dict, List, Set

# Enhanced Skill Ontology with Weighted Relationships
SKILL_ONTOLOGY = {
    "procure to pay": {
        "category": "domain",
        "synonyms": ["p2p", "procurement to payment"],
        "related": {
            "accounts payable": 1.0,
            "invoice processing": 1.0,
            "vendor reconciliation": 0.9,
            "payment validation": 0.8,
            "erp systems": 0.7,
            "sap": 0.7,
            "purchase orders": 0.9,
            "indirect procurement": 0.6
        }
    },
    "order to cash": {
        "category": "domain",
        "synonyms": ["o2c"],
        "related": {
            "sales orders": 1.0,
            "credit management": 0.9,
            "order fulfillment": 0.9,
            "invoicing": 1.0,
            "accounts receivable": 1.0,
            "collections": 0.8
        }
    },
    "machine learning": {
        "category": "domain",
        "synonyms": ["ml", "artificial intelligence", "ai"],
        "related": {
            "deep learning": 0.9,
            "neural networks": 0.8,
            "scikit-learn": 1.0,
            "tensorflow": 0.9,
            "pytorch": 0.9,
            "model evaluation": 0.8,
            "feature engineering": 0.9
        }
    },
    "data science": {
        "category": "domain",
        "related": {
            "data analysis": 1.0,
            "statistics": 0.9,
            "python": 0.8,
            "r": 0.8,
            "sql": 0.8,
            "data visualization": 0.7
        }
    },
    "erp systems": {
        "category": "tools",
        "related": {
            "sap": 0.9,
            "oracle": 0.9,
            "microsoft dynamics": 0.8,
            "netsuite": 0.8
        }
    }
}

# General Skill Categories for classification
CATEGORIES = {
    "tools": [
        "python", "java", "javascript", "react", "node.js", "fastapi", "sql", "postgresql", 
        "mongodb", "docker", "aws", "azure", "git", "ci/cd", "sap", "oracle", "tableau", 
        "power bi", "excel", "kubernetes", "typescript", "next.js", "terraform", "erp",
        "docker", "kubernetes", "jenkins", "jira", "confluence"
    ],
    "soft_skills": [
        "leadership", "communication", "teamwork", "problem solving", "time management", 
        "adaptability", "critical thinking", "collaboration", "presentation", "mentoring",
        "attention to detail", "stakeholder management", "process compliance"
    ]
}

def get_skill_category(skill_name: str) -> str:
    skill_lower = skill_name.lower()
    if skill_lower in CATEGORIES["tools"]:
        return "Tool/Technology"
    if skill_lower in CATEGORIES["soft_skills"]:
        return "Soft Skill"
    
    # Check if it belongs to a known domain in ontology
    for domain, data in SKILL_ONTOLOGY.items():
        if skill_lower == domain or skill_lower in data.get("synonyms", []) or skill_lower in data.get("related", {}):
            return "Domain Skill"
            
    return "Domain Skill" # Default

def expand_skills_semantically(skills: List[str]) -> Dict[str, float]:
    """Expands skills and assigns weights (1.0 for direct, <1.0 for inferred)."""
    expanded = {s.lower(): 1.0 for s in skills}
    
    for skill in skills:
        skill_lower = skill.lower()
        # Direct Match in Ontology
        if skill_lower in SKILL_ONTOLOGY:
            for related, weight in SKILL_ONTOLOGY[skill_lower]["related"].items():
                if related not in expanded or weight > expanded[related]:
                    expanded[related] = weight * 0.8 # Inferred skills get a slight penalty
        
        # Synonym Check
        for domain, data in SKILL_ONTOLOGY.items():
            if skill_lower in data.get("synonyms", []):
                # If they mention a synonym, they effectively mention the domain
                expanded[domain] = 1.0
                for related, weight in data.get("related", {}).items():
                    if related not in expanded or weight > expanded[related]:
                        expanded[related] = weight * 0.8
    
    return expanded
