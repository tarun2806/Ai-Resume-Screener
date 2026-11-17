"""
Centralized application configuration.

Fail-fast rules:
- ENVIRONMENT=production requires JWT_SECRET to be set to a strong value.
- ALLOWED_ORIGINS must be set explicitly in production (no implicit wildcards).
"""

import os
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_JWT_SECRET = "dev-insecure-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = os.getenv("ENVIRONMENT", "development")
    database_url: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ai_screenx.db')}"
    )
    jwt_secret: str = os.getenv("JWT_SECRET", "")
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", str(60 * 24)))
    allowed_origins: str = os.getenv("ALLOWED_ORIGINS", "")
    admin_email: str = os.getenv("ADMIN_EMAIL", "")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "5"))
    resume_retention_days: int = int(os.getenv("RESUME_RETENTION_DAYS", "365"))
    # Optional JSON override for explainable-score component weights.
    # Expected keys: skill_overlap, preferred_match, semantic_similarity,
    # experience_fit, education_fit (weights are renormalized to sum to 1).
    scoring_weights_json: str = os.getenv("SCORING_WEIGHTS", "")
    # Private resume storage: "local" (dev) or "s3" (S3-compatible, prod).
    storage_backend: str = os.getenv("STORAGE_BACKEND", "local")
    storage_dir: str = os.getenv("STORAGE_DIR", "")
    s3_bucket: str = os.getenv("S3_BUCKET", "")
    s3_endpoint_url: str = os.getenv("S3_ENDPOINT_URL", "")
    s3_region: str = os.getenv("AWS_REGION", "us-east-1")
    s3_access_key: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    s3_secret_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    # Background resume-processing worker (DB-backed queue).
    worker_enabled: bool = os.getenv("WORKER_ENABLED", "true").lower() != "false"
    worker_poll_seconds: float = float(os.getenv("WORKER_POLL_SECONDS", "1.0"))
    worker_lease_seconds: int = int(os.getenv("WORKER_LEASE_SECONDS", "900"))
    processing_max_attempts: int = int(os.getenv("PROCESSING_MAX_ATTEMPTS", "3"))
    processing_retry_base_seconds: int = int(os.getenv("PROCESSING_RETRY_BASE_SECONDS", "30"))

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def origins_list(self) -> list[str]:
        if self.allowed_origins.strip():
            return [o.strip().rstrip("/") for o in self.allowed_origins.split(",") if o.strip()]
        if self.is_production:
            return []
        return ["http://localhost:5173", "http://127.0.0.1:5173"]

    def validate_production(self) -> None:
        """Raise RuntimeError if production config is unsafe. Call at startup."""
        if not self.is_production:
            return
        problems = []
        if not self.jwt_secret or self.jwt_secret == _DEV_JWT_SECRET or len(self.jwt_secret) < 32:
            problems.append("JWT_SECRET must be set to a random value of at least 32 characters")
        if not self.allowed_origins.strip():
            problems.append("ALLOWED_ORIGINS must be set in production")
        if self.database_url.startswith("sqlite"):
            problems.append("DATABASE_URL must point to PostgreSQL in production")
        if problems:
            raise RuntimeError("Invalid production configuration: " + "; ".join(problems))


# Default explainable-scoring weights (sum to 1.0). Documented formula:
#   overall = 100 * ( w_skill*skill_overlap + w_pref*preferred_match
#                   + w_sem*semantic_similarity + w_exp*experience_fit
#                   + w_edu*education_fit )
# Neutral-component rules (documented in services/analysis.py):
#   - preferred_match with no preferred skills in JD -> equals skill_overlap
#   - education_fit with no degree requirement in JD -> 1.0
#   - experience_fit with unknown candidate years -> 0.5
DEFAULT_SCORING_WEIGHTS = {
    "skill_overlap": 0.35,
    "preferred_match": 0.05,
    "semantic_similarity": 0.30,
    "experience_fit": 0.15,
    "education_fit": 0.15,
}


def get_scoring_weights() -> dict:
    """Return scoring weights, honoring SCORING_WEIGHTS JSON env override."""
    import json

    if settings.scoring_weights_json.strip():
        try:
            override = json.loads(settings.scoring_weights_json)
            merged = dict(DEFAULT_SCORING_WEIGHTS)
            for k, v in override.items():
                if k in merged:
                    merged[k] = float(v)
            total = sum(merged.values())
            if total > 0:
                return {k: v / total for k, v in merged.items()}
        except (ValueError, TypeError):
            pass  # fall through to defaults
    return dict(DEFAULT_SCORING_WEIGHTS)


settings = Settings()


def resolve_jwt_secret() -> str:
    """Return the JWT signing secret, generating an ephemeral one in dev."""
    if settings.jwt_secret and settings.jwt_secret != _DEV_JWT_SECRET:
        return settings.jwt_secret
    if settings.is_production:
        # validate_production() should have caught this already
        raise RuntimeError("JWT_SECRET is not configured")
    # Dev fallback: stable per-process random secret (tokens invalidate on restart)
    return secrets.token_hex(32)
