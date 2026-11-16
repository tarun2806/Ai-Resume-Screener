from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import time

# Import Routers
from app.api.resumes import router as resumes_router
from app.api.jobs import router as jobs_router
from app.api.matches import router as matches_router
from app.api.auth import router as auth_router
from app.api.ats import router as ats_router
from app.db import init_db

# Initialize FastAPI App (Vercel uses an 'app' instance)
app = FastAPI(
    title="AI ScreenX",
    description="AI Resume Screener & ATS.",
    version="2.0.0"
)

# Best-effort DB init (serverless filesystems may be read-only; the ATS
# endpoints will return errors if persistence is unavailable)
try:
    init_db()
except Exception:
    pass

from app.ratelimit import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 🚦 Simplified CORS for Easy Deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
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
    return {"status": "online", "mode": "Vercel Serverless", "timestamp": time.time()}

# Note: SQLite persistence does not survive serverless invocations.
# For production ATS use, deploy the Docker backend (Railway/Render/Fly) instead.
