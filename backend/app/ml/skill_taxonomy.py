"""
Skill taxonomy: categories and semantic relations for the canonical
vocabulary in skill_vocabulary.py.

Categories: language | frontend | backend | database | cloud | devops |
data | ai_ml | security | testing | architecture | practices | tool

RELATED maps a canonical skill to adjacent skills with a weight in (0,1].
Relations are used ONLY for partial credit / suggestions — never treated as
equivalent qualifications.
"""

from __future__ import annotations

SKILL_CATEGORIES: dict[str, str] = {
    # Languages
    "Python": "language", "Java": "language", "JavaScript": "language",
    "TypeScript": "language", "C": "language", "C++": "language",
    "C#": "language", "Go": "language", "Rust": "language", "Ruby": "language",
    "PHP": "language", "Swift": "language", "Kotlin": "language",
    "Scala": "language", "R": "language", "MATLAB": "language",
    "SQL": "language", "HTML": "language", "CSS": "language",
    "Dart": "language", "Shell": "language", "Perl": "language",
    # Frontend
    "React": "frontend", "Next.js": "frontend", "Angular": "frontend",
    "Vue.js": "frontend", "Redux": "frontend", "RxJS": "frontend",
    "Tailwind CSS": "frontend",
    "Bootstrap": "frontend", "Sass": "frontend", "Three.js": "frontend",
    "Flutter": "frontend", "React Native": "frontend", "jQuery": "frontend",
    "Web Development": "frontend",
    # Backend
    "Node.js": "backend", "Express": "backend", "Django": "backend",
    "Flask": "backend", "FastAPI": "backend", "Spring": "backend",
    "Spring Boot": "backend", "Laravel": "backend", "ASP.NET": "backend",
    # Databases
    "PostgreSQL": "database", "MySQL": "database", "MongoDB": "database",
    "Redis": "database", "SQLite": "database", "Oracle DB": "database",
    "SQL Server": "database", "Cassandra": "database",
    "Elasticsearch": "database", "DynamoDB": "database",
    # Cloud
    "AWS": "cloud", "Azure": "cloud", "GCP": "cloud", "Firebase": "cloud",
    # DevOps
    "Docker": "devops", "Kubernetes": "devops", "Terraform": "devops",
    "Ansible": "devops", "Jenkins": "devops", "GitHub Actions": "devops",
    "GitLab CI": "devops", "CircleCI": "devops", "Nginx": "devops",
    "Apache": "devops", "Linux": "devops", "VMware": "devops", "Helm": "devops",
    "Prometheus": "devops", "Grafana": "devops", "DevOps": "devops",
    "CI/CD": "devops",
    # Data
    "Spark": "data", "Hadoop": "data", "Pandas": "data", "NumPy": "data",
    "SciPy": "data", "Tableau": "data", "Power BI": "data", "Excel": "data",
    "ETL": "data", "Airflow": "data", "Kafka": "data", "dbt": "data",
    "Looker": "data", "Data Science": "data", "Data Engineering": "data",
    "Data Analysis": "data", "Business Intelligence": "data",
    # AI/ML
    "Machine Learning": "ai_ml", "Deep Learning": "ai_ml",
    "Natural Language Processing": "ai_ml", "Computer Vision": "ai_ml",
    "TensorFlow": "ai_ml", "PyTorch": "ai_ml", "Keras": "ai_ml",
    "scikit-learn": "ai_ml",
    # Security
    "Cybersecurity": "security", "SIEM": "security",
    "Incident Response": "security", "Network Security": "security",
    "Risk Assessment": "security", "Compliance": "security",
    "Penetration Testing": "security",
    "SageMaker": "ai_ml", "MLOps": "ai_ml", "CUDA": "ai_ml",
    # Testing
    "jUnit": "testing", "pytest": "testing", "Mocha": "testing",
    "Jest": "testing", "Cypress": "testing", "Testing": "testing", "TDD": "testing",
    # Architecture & practices
    "GraphQL": "architecture", "REST API": "architecture",
    "System Design": "architecture", "Microservices": "architecture",
    "OOP": "architecture", "API Design": "architecture", "Full Stack": "architecture",
    # Databases (extended)
    "Snowflake": "database", "BigQuery": "database", "Redshift": "database",
    "Supabase": "database",
    # Cloud (extended)
    "Lambda": "cloud", "EC2": "cloud", "S3": "cloud", "CloudFormation": "cloud",
    # Backend (extended)
    "Pydantic": "backend",
    # AI/ML (extended)
    "Transformers": "ai_ml",
    # Data (extended)
    "Statistics": "data",
    # Practices (extended)
    "Scrum": "practices", "Distributed Systems": "architecture",
    "Architecture": "architecture",
    "Agile": "practices", "Git": "practices", "Project Management": "practices",
    "Leadership": "practices",
}

# Related skills: canonical -> {related canonical: weight}
SKILL_RELATIONS: dict[str, dict[str, float]] = {
    "Python": {"Django": 0.9, "Flask": 0.85, "FastAPI": 0.85, "Pandas": 0.7,
               "NumPy": 0.7, "scikit-learn": 0.75, "PyTorch": 0.7, "TensorFlow": 0.7,
               "Spark": 0.6, "Airflow": 0.6},
    "JavaScript": {"React": 0.9, "Node.js": 0.85, "TypeScript": 0.8, "Vue.js": 0.7,
                   "Angular": 0.7, "Next.js": 0.8, "Express": 0.7},
    "TypeScript": {"JavaScript": 0.9, "React": 0.85, "Angular": 0.8, "Node.js": 0.75,
                   "Next.js": 0.8, "Vue.js": 0.7},
    "Java": {"Spring": 0.9, "Spring Boot": 0.9, "Kotlin": 0.7, "Scala": 0.7,
             "Microservices": 0.6},
    "React": {"Next.js": 0.9, "JavaScript": 0.9, "TypeScript": 0.85, "Redux": 0.8,
              "Tailwind CSS": 0.7, "GraphQL": 0.6, "Node.js": 0.6},
    "Cybersecurity": {"SIEM": 0.8, "Incident Response": 0.8, "Network Security": 0.85,
                      "Penetration Testing": 0.75, "Risk Assessment": 0.7, "Compliance": 0.6},
    "SIEM": {"Cybersecurity": 0.8, "Incident Response": 0.85, "Network Security": 0.75},
    "Incident Response": {"Cybersecurity": 0.8, "SIEM": 0.85, "Network Security": 0.7},
    "Network Security": {"Cybersecurity": 0.85, "SIEM": 0.75},
    "Risk Assessment": {"Cybersecurity": 0.7, "Compliance": 0.7},
    "Compliance": {"Cybersecurity": 0.6, "Risk Assessment": 0.7},
    "Penetration Testing": {"Cybersecurity": 0.75, "Network Security": 0.7},
    "SageMaker": {"AWS": 0.85, "MLOps": 0.8, "PyTorch": 0.6, "TensorFlow": 0.6},
    "MLOps": {"SageMaker": 0.8, "Docker": 0.7, "Kubernetes": 0.65, "CI/CD": 0.7},
    "Vue.js": {"React": 0.6, "Angular": 0.55, "JavaScript": 0.8, "TypeScript": 0.75,
               "Next.js": 0.5, "Node.js": 0.6},
    "Angular": {"TypeScript": 0.85, "JavaScript": 0.8, "React": 0.55, "Vue.js": 0.55,
                "RxJS": 0.6},
    "Redux": {"React": 0.85, "JavaScript": 0.8, "TypeScript": 0.8},
    "Node.js": {"Express": 0.9, "JavaScript": 0.85, "React": 0.7, "GraphQL": 0.7,
                "MongoDB": 0.7, "PostgreSQL": 0.6},
    "Django": {"Python": 0.95, "Flask": 0.7, "PostgreSQL": 0.7, "REST API": 0.7},
    "Flask": {"Python": 0.95, "Django": 0.7, "REST API": 0.7},
    "FastAPI": {"Python": 0.95, "Flask": 0.75, "REST API": 0.85, "Pydantic": 0.8},
    "PostgreSQL": {"SQL": 0.95, "MySQL": 0.8, "MongoDB": 0.6, "Redis": 0.6,
                   "Django": 0.6, "Supabase": 0.8},
    "MySQL": {"SQL": 0.95, "PostgreSQL": 0.8, "MongoDB": 0.6},
    "MongoDB": {"SQL": 0.6, "Node.js": 0.7, "DynamoDB": 0.7, "Firebase": 0.7},
    "AWS": {"Docker": 0.7, "Kubernetes": 0.7, "Terraform": 0.7, "Lambda": 0.8,
            "EC2": 0.8, "S3": 0.7, "CloudFormation": 0.7, "Azure": 0.5, "GCP": 0.5},
    "Azure": {"AWS": 0.5, "GCP": 0.6, "Docker": 0.6, "Kubernetes": 0.6},
    "GCP": {"AWS": 0.5, "Azure": 0.6, "Docker": 0.6, "Kubernetes": 0.6,
            "BigQuery": 0.8},
    "Docker": {"Kubernetes": 0.85, "Linux": 0.7, "CI/CD": 0.7, "Terraform": 0.6,
               "AWS": 0.7, "Azure": 0.6, "GCP": 0.6},
    "Kubernetes": {"Docker": 0.85, "Helm": 0.8, "Linux": 0.7, "Terraform": 0.6,
                   "CI/CD": 0.6, "AWS": 0.7, "Azure": 0.6, "GCP": 0.6},
    "Terraform": {"AWS": 0.7, "Azure": 0.6, "GCP": 0.6, "Ansible": 0.7,
                  "Kubernetes": 0.6, "Docker": 0.5},
    "Machine Learning": {"Deep Learning": 0.9, "scikit-learn": 0.85, "PyTorch": 0.85,
                         "TensorFlow": 0.85, "Pandas": 0.7, "NumPy": 0.7,
                         "Natural Language Processing": 0.75, "Computer Vision": 0.75,
                         "Data Science": 0.8},
    "Deep Learning": {"Machine Learning": 0.95, "PyTorch": 0.9, "TensorFlow": 0.9,
                      "Keras": 0.85, "Computer Vision": 0.8, "Natural Language Processing": 0.8},
    "Natural Language Processing": {"Machine Learning": 0.85, "Deep Learning": 0.8,
                                    "Python": 0.7, "Transformers": 0.9},
    "Data Engineering": {"Python": 0.8, "SQL": 0.9, "Spark": 0.9, "Airflow": 0.85,
                         "dbt": 0.85, "Kafka": 0.7, "ETL": 0.9, "Snowflake": 0.8,
                         "BigQuery": 0.8, "Data Analysis": 0.6},
    "Data Science": {"Python": 0.85, "SQL": 0.8, "Pandas": 0.9, "NumPy": 0.8,
                     "scikit-learn": 0.9, "Machine Learning": 0.85, "Tableau": 0.7,
                     "Statistics": 0.8},
    "Spark": {"Python": 0.7, "Scala": 0.8, "Hadoop": 0.8, "Kafka": 0.7, "ETL": 0.7,
              "Airflow": 0.6, "Data Engineering": 0.8},
    "Airflow": {"Python": 0.8, "Data Engineering": 0.9, "ETL": 0.8, "Kafka": 0.6,
                "Docker": 0.5},
    "Kafka": {"Spark": 0.7, "Data Engineering": 0.8, "Microservices": 0.6},
    "dbt": {"SQL": 0.9, "Data Engineering": 0.9, "Snowflake": 0.8, "BigQuery": 0.7},
    "Tableau": {"Data Analysis": 0.9, "Business Intelligence": 0.9, "SQL": 0.7,
                "Excel": 0.6, "Data Science": 0.6},
    "Power BI": {"Tableau": 0.8, "Data Analysis": 0.9, "Business Intelligence": 0.9,
                 "SQL": 0.7, "Excel": 0.7},
    "REST API": {"Node.js": 0.7, "Express": 0.7, "FastAPI": 0.7, "Django": 0.7,
                 "Flask": 0.7, "Spring Boot": 0.7, "API Design": 0.9,
                 "Microservices": 0.7, "GraphQL": 0.6},
    "GraphQL": {"REST API": 0.8, "Node.js": 0.8, "React": 0.7, "TypeScript": 0.7,
                "API Design": 0.8},
    "CI/CD": {"Jenkins": 0.9, "GitHub Actions": 0.9, "GitLab CI": 0.85, "Docker": 0.7,
              "Kubernetes": 0.6, "Terraform": 0.6, "Linux": 0.6},
    "Git": {"GitHub": 0.9, "GitLab": 0.8, "CI/CD": 0.7, "Agile": 0.6},
    "Testing": {"pytest": 0.9, "jUnit": 0.9, "Jest": 0.9, "Cypress": 0.8,
                "TDD": 0.85},
    "Microservices": {"Docker": 0.8, "Kubernetes": 0.8, "System Design": 0.9,
                      "REST API": 0.8, "Spring Boot": 0.7, "Node.js": 0.6},
    "System Design": {"Microservices": 0.9, "Distributed Systems": 0.9,
                      "Architecture": 0.9},
    "Linux": {"Docker": 0.7, "Kubernetes": 0.7, "Shell": 0.8, "DevOps": 0.8},
    "Agile": {"Scrum": 0.9, "Project Management": 0.7, "Leadership": 0.6},
}
