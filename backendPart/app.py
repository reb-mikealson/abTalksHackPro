"""
app.py — API entrypoint / orchestrator for the AI Interviewer.

This module is intentionally "thin": it only handles HTTP routing,
request validation, and orchestration. All business logic lives in
services/*.

Expected service interfaces (implement these in services/):

    services/data_loader.py
        load_candidate_profile(candidate_id: str) -> dict
        load_curriculum() -> dict

    services/conversation_manager.py
        run_interview(candidate_profile: dict, curriculum: dict) -> dict
            -> {"transcript": [ {question, answer, day, follow_up: bool}, ... ]}

    services/feedback_generator.py
        generate_feedback(transcript: list[dict]) -> dict
            -> {"summary": str, "scores": dict, "strengths": [...], "improvements": [...]}
"""

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.data_loader import load_candidate_profile, load_curriculum
from services.conversation_manager import run_interview
from services.feedback_generator import generate_feedback

# --------------------------------------------------------------------------
# Config / constants
# --------------------------------------------------------------------------

MIN_QUESTIONS = 8
MIN_CURRICULUM_DAYS = 4

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("interview_api")

app = FastAPI(
    title="AI Interviewer API",
    description="Orchestrates candidate interviews: questions, follow-ups, and feedback.",
    version="1.0.0",
)


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------

class StartInterviewRequest(BaseModel):
    candidate_id: str = Field(..., min_length=1, description="Unique candidate identifier")


class ErrorResponse(BaseModel):
    error: str


# --------------------------------------------------------------------------
# Custom exceptions (keep service layer free of HTTP concerns)
# --------------------------------------------------------------------------

class CandidateNotFoundError(Exception):
    pass


class CurriculumLoadError(Exception):
    pass


class InterviewExecutionError(Exception):
    pass


# --------------------------------------------------------------------------
# Exception handlers -> consistent JSON error shape
# --------------------------------------------------------------------------

@app.exception_handler(CandidateNotFoundError)
async def candidate_not_found_handler(_, exc: CandidateNotFoundError):
    return JSONResponse(status_code=404, content={"error": str(exc)})


@app.exception_handler(CurriculumLoadError)
async def curriculum_load_handler(_, exc: CurriculumLoadError):
    return JSONResponse(status_code=500, content={"error": str(exc)})


@app.exception_handler(InterviewExecutionError)
async def interview_execution_handler(_, exc: InterviewExecutionError):
    return JSONResponse(status_code=500, content={"error": str(exc)})


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _validate_interview_result(transcript: list[dict[str, Any]]) -> None:
    """Enforce hackathon minimum requirements before returning a result."""
    if len(transcript) < MIN_QUESTIONS:
        raise InterviewExecutionError(
            f"Interview produced only {len(transcript)} questions "
            f"(minimum required: {MIN_QUESTIONS})."
        )

    days_covered = {q.get("day") for q in transcript if q.get("day") is not None}
    if len(days_covered) < MIN_CURRICULUM_DAYS:
        raise InterviewExecutionError(
            f"Interview covered only {len(days_covered)} curriculum day(s) "
            f"(minimum required: {MIN_CURRICULUM_DAYS})."
        )


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post(
    "/start-interview",
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
def start_interview(request: StartInterviewRequest) -> dict:
    """
    Orchestrates a full interview run:
      1. Load candidate profile
      2. Load curriculum
      3. Run the interview flow (questions + follow-ups + context tracking)
      4. Validate it meets hackathon minimums
      5. Generate structured feedback
      6. Return transcript + feedback
    """
    candidate_id = request.candidate_id
    logger.info("Starting interview for candidate_id=%s", candidate_id)

    # Step 1: candidate profile
    try:
        profile = load_candidate_profile(candidate_id)
    except FileNotFoundError:
        raise CandidateNotFoundError(f"Candidate '{candidate_id}' not found")
    except Exception as exc:
        logger.exception("Failed loading candidate profile")
        raise CandidateNotFoundError(f"Could not load candidate '{candidate_id}': {exc}")

    # Step 2: curriculum
    try:
        curriculum = load_curriculum()
    except FileNotFoundError:
        raise CurriculumLoadError("Curriculum file missing")
    except Exception as exc:
        logger.exception("Failed loading curriculum")
        raise CurriculumLoadError(f"Could not load curriculum: {exc}")

    # Step 3: run the interview flow
    try:
        interview_result = run_interview(profile, curriculum)
        transcript = interview_result["transcript"]
    except Exception as exc:
        logger.exception("Interview flow crashed")
        raise InterviewExecutionError(f"Interview flow failed: {exc}")

    # Step 4: enforce hackathon minimums
    _validate_interview_result(transcript)

    # Step 5: feedback
    try:
        feedback = generate_feedback(transcript)
    except Exception as exc:
        logger.exception("Feedback generation failed")
        raise InterviewExecutionError(f"Feedback generation failed: {exc}")

    logger.info("Interview complete for candidate_id=%s (%d questions)", candidate_id, len(transcript))

    # Step 6: response
    return {
        "candidate_id": candidate_id,
        "transcript": transcript,
        "feedback": feedback,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)