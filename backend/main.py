from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import time
import uvicorn

# Import Routers
from app.api.resumes import router as resumes_router
from app.api.jobs import router as jobs_router
from app.api.matches import router as matches_router
from app.api.auth import router as auth_router
from app.api.ats import router as ats_router
from app.db import init_db

init_db()


def _seed_admin():
    """Create an admin user from env vars if provided and none exists."""
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
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
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

from app.ratelimit import limiter
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 🚦 Middleware: CORS & Timing
# In production, set ALLOWED_ORIGINS to your frontend origin(s), comma-separated.
# Fail closed: when unset we only allow local development origins.
raw_origins = os.getenv("ALLOWED_ORIGINS")
if raw_origins:
    allowed_origins = [o.strip().rstrip("/") for o in raw_origins.split(",") if o.strip()]
else:
    allowed_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False, # Set to False for wildcard support
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
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

@app.get("/", tags=["Health"])
async def health_check():
    """Check if the API and its AI components are live."""
    return {
        "status": "online",
        "service": "AI ScreenX API",
        "version": "2.0.0",
        "timestamp": time.time()
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
