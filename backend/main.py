from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import logging
import os
import time
import uvicorn


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        from app.request_context import org_id_var, request_id_var, user_id_var
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "service": "ai-screenx",
            "env": settings.environment if "settings" in dir() else "development",
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = request_id_var.get()
        if rid:
            payload["request_id"] = rid
        uid = user_id_var.get()
        if uid is not None:
            payload["user_id"] = uid
        oid = org_id_var.get()
        if oid is not None:
            payload["org_id"] = oid
        return json.dumps(payload, default=str)


_handler = logging.StreamHandler()
_handler.setFormatter(JsonFormatter())
_root = logging.getLogger()
_root.handlers = [_handler]
_root.setLevel(logging.INFO)
log = logging.getLogger("ai-screenx")

# Import Routers
from app.api.resumes import router as resumes_router
from app.api.jobs import router as jobs_router
from app.api.matches import router as matches_router
from app.api.auth import router as auth_router
from app.api.ats import router as ats_router
from app.api.orgs import router as orgs_router
from app.config import settings
from app.db import init_db

init_db()

from app.services.processing import ensure_worker_started
ensure_worker_started()

settings.validate_production()


def _seed_admin():
    """Create an admin user from env vars if provided and none exists."""
    admin_email = settings.admin_email
    admin_password = settings.admin_password
    if not admin_email or not admin_password:
        return
    from app.db import SessionLocal, User
    from app.auth import hash_password

    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == admin_email.lower()).first():
            db.add(User(
                email=admin_email.lower(),
                password_hash=hash_password(admin_password),
                name="Admin",
                role="admin",
            ))
            db.commit()
    finally:
        db.close()


_seed_admin()

# Initialize FastAPI App
app = FastAPI(
    title="AI ScreenX | Advanced AI Resume Screener",
    description="A production-ready NLP system for semantic resume-job matching using SBERT and custom ontologies.",
    version="2.0.0",
    docs_url=None if settings.is_production else "/api/docs",
    redoc_url=None if settings.is_production else "/api/redoc",
    openapi_url=None if settings.is_production else "/api/openapi.json",
)

from app.ratelimit import limiter
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 🚦 Middleware: CORS & Timing
# In production, set ALLOWED_ORIGINS to your frontend origin(s), comma-separated.
# Fail closed: when unset we only allow local development origins.
raw_origins = settings.allowed_origins
allowed_origins = settings.origins_list

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False, # Set to False for wildcard support
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    from app.request_context import new_request_id, set_request_id
    from app import metrics as app_metrics
    rid = request.headers.get("x-request-id") or new_request_id()
    set_request_id(rid[:64])
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    app_metrics.record_request(process_time, response.status_code, request.url.path)
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-Request-ID"] = rid[:64]
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Audit denied access to API endpoints (no PII, path template only)
    if response.status_code in (401, 403) and request.url.path.startswith("/api/v1/"):
        try:
            from app.db import AuditEvent, SessionLocal
            from app.request_context import user_id_var, user_email_var
            db = SessionLocal()
            try:
                db.add(AuditEvent(
                    actor_id=user_id_var.get(),
                    actor_email=(user_email_var.get() or "")[:255],
                    action="access_denied",
                    resource_type="endpoint",
                    resource_id=request.url.path[:64],
                    outcome="denied",
                    request_id=rid[:64],
                    metadata_json="{}",
                ))
                db.commit()
            finally:
                db.close()
        except Exception:
            pass
    return response

# 🚨 Global Error Handling
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": True, "message": exc.detail, "type": "HTTPException"}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    import logging
    logging.getLogger("ai-screenx").exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": True, "message": "An unexpected error occurred", "type": "InternalServerError"}
    )

# 🛣 Routes
app.include_router(resumes_router, prefix="/api/v1/resumes", tags=["Resumes"])
app.include_router(jobs_router, prefix="/api/v1/jobs", tags=["Jobs"])
app.include_router(matches_router, prefix="/api/v1/matches", tags=["Matching Engine"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(ats_router, prefix="/api/v1/ats", tags=["ATS"])
app.include_router(orgs_router, prefix="/api/v1", tags=["Organizations"])

@app.get("/", tags=["Health"])
async def health_check():
    """Liveness probe — process is up."""
    return {
        "status": "online",
        "service": "AI ScreenX API",
        "version": "2.0.0",
        "timestamp": time.time()
    }


@app.get("/health", tags=["Health"])
async def health_deep():
    """Readiness probe — verifies database connectivity."""
    from sqlalchemy import text
    from app.db import SessionLocal

    checks = {"api": "ok"}
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            checks["database"] = "ok"
        finally:
            db.close()
    except Exception as exc:
        log.error("health check db failure: %s", exc)
        checks["database"] = "error"
        return JSONResponse(status_code=503, content={"status": "degraded", "checks": checks})
    return {"status": "ok", "checks": checks}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
