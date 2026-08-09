"""
FastAPI application entrypoint for the AI Interview Agent.

Run with:
    uvicorn backend.app:app --reload

Swagger docs: http://localhost:8000/docs
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.routes.interview import router as interview_router

settings = get_settings()

app = FastAPI(
    title="AI Interview Agent",
    description=(
        "A conversational AI technical interviewer. Personalizes questions "
        "from a candidate profile and a 31-day AI engineering curriculum "
        "using retrieval-augmented generation, adapts difficulty in real "
        "time, and produces structured feedback at the end of the "
        "interview."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(interview_router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}
