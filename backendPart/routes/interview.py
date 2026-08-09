"""
POST /api/interview

Implements the exact contract defined in data/technical_spec.md:

Start:
    { "sessionId": "abc-123", "candidate": {...} }
    -> { "reply": "...", "done": false }

Turn:
    { "sessionId": "abc-123", "message": "..." }
    -> { "reply": "...", "done": false }

End:
    -> { "reply": "...", "done": true, "feedback": {"summary","strengths","gaps","next"} }

This module is intentionally thin: request validation + delegating to the
InterviewOrchestrator. All interview logic lives in backend/services/.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.interview_orchestrator import get_orchestrator

router = APIRouter()


class InterviewRequest(BaseModel):
    sessionId: str = Field(..., description="Client-supplied session identifier, stable across the interview.")
    candidate: dict[str, Any] | None = Field(
        default=None, description="Candidate profile, required on the FIRST request of a session."
    )
    message: str | None = Field(
        default=None, description="The candidate's latest response, required on every turn after the first."
    )


class Feedback(BaseModel):
    summary: str
    strengths: list[str]
    gaps: list[str]
    next: list[str]


class InterviewResponse(BaseModel):
    reply: str
    done: bool
    feedback: Feedback | None = None


@router.post("/api/interview", response_model=InterviewResponse)
def interview_turn(payload: InterviewRequest) -> InterviewResponse:
    if not payload.sessionId or not payload.sessionId.strip():
        raise HTTPException(status_code=422, detail="sessionId is required.")

    if payload.candidate is None and payload.message is None:
        raise HTTPException(
            status_code=422,
            detail="Request must include either 'candidate' (to start) or 'message' (to continue).",
        )

    orchestrator = get_orchestrator()
    result = orchestrator.handle_turn(
        session_id=payload.sessionId,
        candidate=payload.candidate,
        message=payload.message,
    )
    return InterviewResponse(**result)
