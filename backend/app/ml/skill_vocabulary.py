from __future__ import annotations

"""
Deterministic skill vocabulary for resume/JD parsing.

Maps canonical skill names to lowercase aliases. Used for exact,
explainable skill extraction — no ML model required.
"""

SKILL_VOCABULARY: dict[str, list[str]] = {
    # Languages
    "Python": ["python", "py", "python3"],
    "Java": ["java"],
    "JavaScript": ["javascript", "js", "es6", "ecmascript"],
    "TypeScript": ["typescript", "ts"],
    "C": ["c language", " c "],
    "C++": ["c++", "cpp", "c plus plus"],
    "C#": ["c#", "c sharp", "csharp"],
    "Go": ["golang", " go programming", "go lang"],
    "Rust": ["rust"],
    "Ruby": ["ruby"],
    "PHP": ["php"],
    "Swift": ["swift"],
    "Kotlin": ["kotlin"],
    "Scala": ["scala"],
    "R": ["r programming", " r "],
    "MATLAB": ["matlab"],
    "SQL": ["sql", "structured query language"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "Dart": ["dart"],
    "Shell": ["bash", "shell scripting", "shell script", "sh scripting"],
    "Perl": ["perl"],
    # Frameworks & Libraries
    "React": ["react", "reactjs", "react.js"],
    "Next.js": ["next.js", "nextjs", "next js"],
    "Angular": ["angular", "angularjs", "angular.js"],
    "Vue.js": ["vue", "vue.js", "vuejs"],
    "Node.js": ["node", "nodejs", "node.js"],
    "Express": ["express", "express.js", "expressjs"],
    "Django": ["django"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi", "fast api"],
    "Spring": ["spring", "spring boot", "springboot"],
    "Spring Boot": ["spring boot", "springboot"],
    "Laravel": ["laravel"],
    "ASP.NET": ["asp.net", "aspnet", "asp net"],
    "jQuery": ["jquery"],
    "TensorFlow": ["tensorflow"],
    "PyTorch": ["pytorch", "torch"],
    "Keras": ["keras"],
    "scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy", "numPy".lower()],
    "SciPy": ["scipy"],
    "Spark": ["spark", "pyspark", "apache spark"],
    "Hadoop": ["hadoop", "apache hadoop"],
    "Redux": ["redux"],
    "RxJS": ["rxjs", "reactive extensions"],
    "Tailwind CSS": ["tailwind", "tailwindcss", "tailwind css"],
    "Bootstrap": ["bootstrap"],
    "Sass": ["sass", "scss"],
    "Three.js": ["three.js", "threejs"],
    "Flutter": ["flutter"],
    "React Native": ["react native", "reactnative"],
    "jUnit": ["junit", "j-unit"],
    "pytest": ["pytest"],
    "Mocha": ["mocha"],
    "Jest": ["jest"],
    "Cypress": ["cypress"],
    # Databases & Storage
    "PostgreSQL": ["postgresql", "postgres", "psql"],
    "MySQL": ["mysql"],
    "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis"],
    "SQLite": ["sqlite"],
    "Oracle DB": ["oracle", "oracle db", "oracle database"],
    "SQL Server": ["sql server", "mssql", "ms sql"],
    "Cassandra": ["cassandra", "apache cassandra"],
    "Elasticsearch": ["elasticsearch", "elastic search", "elk"],
    "DynamoDB": ["dynamodb"],
    "Firebase": ["firebase"],
    "GraphQL": ["graphql", "graph ql"],
    "REST API": ["rest", "restful", "rest api", "restful api"],
    # Cloud & DevOps
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure", "microsoft azure"],
    "GCP": ["gcp", "google cloud", "google cloud platform"],
    "Docker": ["docker", "dockerfile", "containerization"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Terraform": ["terraform"],
    "Ansible": ["ansible"],
    "Jenkins": ["jenkins"],
    "GitHub Actions": ["github actions", "gha"],
    "GitLab CI": ["gitlab ci", "gitlabci"],
    "CircleCI": ["circleci"],
    "Nginx": ["nginx"],
    "Apache": ["apache"],
    "Linux": ["linux", "unix", "ubuntu"],
    "VMware": ["vmware"],
    "Helm": ["helm"],
    "Prometheus": ["prometheus"],
    "Grafana": ["grafana"],
    # Data & AI/ML
    "Machine Learning": ["machine learning", "ml"],
    "Deep Learning": ["deep learning", "dl"],
    "Natural Language Processing": ["natural language processing", "nlp"],
    "Computer Vision": ["computer vision", "cv"],
    "Data Science": ["data science", "data scientist"],
    "Data Engineering": ["data engineering", "data engineer"],
    "Data Analysis": ["data analysis", "data analytics", "data analyst"],
    "Business Intelligence": ["business intelligence", "bi", "tableau", "power bi"],
    "Tableau": ["tableau"],
    "Power BI": ["power bi", "powerbi"],
    "Excel": ["excel", "ms excel", "microsoft excel", "spreadsheet"],
    "ETL": ["etl", "extract transform load"],
    "Airflow": ["airflow", "apache airflow"],
    "Kafka": ["kafka", "apache kafka"],
    "dbt": ["dbt"],
    "Looker": ["looker"],
    # Soft skills & practices
    "Agile": ["agile", "scrum", "kanban"],
    "DevOps": ["devops"],
    "CI/CD": ["ci/cd", "cicd", "continuous integration", "continuous deployment"],
    "Git": ["git", "github", "gitlab", "bitbucket", "version control"],
    "Testing": ["unit testing", "test automation", "qa", "quality assurance"],
    "TDD": ["tdd", "test driven development", "test-driven development"],
    "System Design": ["system design", "system architecture", "microservices"],
    "Microservices": ["microservices", "micro-services"],
    "OOP": ["oop", "object oriented", "object-oriented programming"],
    "API Design": ["api design", "api development"],
    "Web Development": ["web development", "web developer"],
    "Full Stack": ["full stack", "full-stack", "fullstack"],
    "Project Management": ["project management", "project manager"],
    "Leadership": ["leadership", "team lead", "tech lead"],
    # Additional cloud/data/security/testing terms referenced by the taxonomy
    "Snowflake": ["snowflake"],
    "BigQuery": ["bigquery", "big query"],
    "Redshift": ["redshift"],
    "Lambda": ["lambda", "aws lambda"],
    "EC2": ["ec2", "elastic compute cloud"],
    "S3": ["s3", "simple storage service"],
    "CloudFormation": ["cloudformation", "cloud formation"],
    "Supabase": ["supabase"],
    "Pydantic": ["pydantic"],
    "Transformers": ["transformers", "hugging face", "huggingface"],
    "Statistics": ["statistics", "statistical"],
    "Scrum": ["scrum"],
    "Distributed Systems": ["distributed systems", "distributed system"],
    "Architecture": ["software architecture", "system architecture"],
    "Cybersecurity": ["cybersecurity", "cyber security", "infosec", "information security"],
    "SIEM": ["siem", "security information and event management", "splunk", "qradar", "sentinel"],
    "Incident Response": ["incident response", "ir planning", "security incident"],
    "Network Security": ["network security", "netsec", "firewall", "ids", "ips"],
    "Risk Assessment": ["risk assessment", "risk analysis", "risk management", "grc"],
    "Compliance": ["compliance", "soc 2", "soc2", "iso 27001", "iso27001", "hipaa", "gdpr", "pci dss"],
    "Penetration Testing": ["penetration testing", "pentest", "ethical hacking", "offensive security"],
    "SageMaker": ["sagemaker", "aws sagemaker", "sagemaker sdk"],
    "MLOps": ["mlops", "ml ops", "model deployment", "model serving"],
    "CUDA": ["cuda", "gpu computing"],
}

# Build alias -> canonical lookup (first canonical wins for duplicate aliases)
ALIAS_TO_CANONICAL: dict[str, str] = {}
for canonical, aliases in SKILL_VOCABULARY.items():
    for alias in aliases:
        key = alias.lower().strip()
        if key and key not in ALIAS_TO_CANONICAL:
            ALIAS_TO_CANONICAL[key] = canonical

ALL_CANONICAL_SKILLS = list(SKILL_VOCABULARY.keys())

# Reverse map: canonical -> all aliases (for evidence lookup)
CANONICAL_TO_ALIASES: dict[str, list[str]] = {
    canonical: list(aliases) for canonical, aliases in SKILL_VOCABULARY.items()
}


def canonical_skill(name: str) -> str | None:
    """Return canonical name for a skill/alias, or None."""
    return ALIAS_TO_CANONICAL.get(name.lower().strip())


def find_skills_in_text(text: str) -> list[dict]:
    """
    Extract skills from free text. Returns list of
    {"name": canonical, "matched_alias": alias} in order of first appearance.
    Deterministic: sorted by position in text, then canonical name.
    """
    import re

    lowered = text.lower()
    hits: list[tuple[int, str, str]] = []  # (position, canonical, alias)
    seen: set[str] = set()

    for alias, canonical in ALIAS_TO_CANONICAL.items():
        # Use boundaries that work for aliases containing dots/pluses
        pattern = r"(?<![\w+#.-])" + re.escape(alias) + r"(?![\w+#.-])"
        m = re.search(pattern, lowered)
        if m and canonical not in seen:
            seen.add(canonical)
            hits.append((m.start(), canonical, alias))

    hits.sort(key=lambda h: (h[0], h[1]))
    return [{"name": c, "matched_alias": a} for _, c, a in hits]
