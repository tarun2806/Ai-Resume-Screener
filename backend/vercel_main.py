from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import time

# Import Routers
from app.api.resumes import router as resumes_router
from app.api.jobs import router as jobs_router
from app.api.matches import router as matches_router

# Initialize FastAPI App (Vercel uses an 'app' instance)
app = FastAPI(
    title="AI ScreenX Lite",
    description="Optimized AI Resume Screener using Serverless-friendly NLP.",
    version="2.0.0"
)

# 🚦 Simplified CORS for Easy Deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🛣 Routes
app.include_router(resumes_router, prefix="/api/v1/resumes", tags=["Resumes"])
app.include_router(jobs_router, prefix="/api/v1/jobs", tags=["Jobs"])
app.include_router(matches_router, prefix="/api/v1/matches", tags=["Matching Engine"])

@app.get("/", tags=["Health"])
async def health_check():
    return {"status": "online", "mode": "Vercel Serverless Lite", "timestamp": time.time()}

# Note: In Vercel, the file must be in the 'api' folder or specific config.
# For simplicity, we keep this as the main export.
