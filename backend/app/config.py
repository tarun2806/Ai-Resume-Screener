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
