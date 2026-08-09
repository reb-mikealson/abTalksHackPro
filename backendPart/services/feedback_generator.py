"""
Generates the final structured feedback for a completed interview.

Output shape follows technical_spec.md exactly:
  { "summary": str, "strengths": [str], "gaps": [str], "next": [str] }

Internally we compute a richer breakdown (topic-wise scores, technical
level, communication quality) and fold the most useful signal into the
spec-required fields, while also returning the richer object for callers
(tests, docs, an optional debug endpoint) that want more detail.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.services.conversation_manager import InterviewState
from backend.services.llm_client import BaseLLMClient, get_llm_client
from backend.services.retrieval import get_retriever
from backend.utils.helpers import average

_SYSTEM_PERSONA = (
    "You are a senior technical interviewer writing a final, honest "
    "candidate evaluation after a completed technical interview. Be "
    "specific and evidence-based, referencing what the candidate actually "
    "said. Avoid generic filler."
)


@dataclass
class TopicScore:
    day: int
    title: str
    score: float


def _topic_scores(state: InterviewState) -> list[TopicScore]:
    retriever = get_retriever()
    by_day: dict[int, list[int]] = {}
    for q in state.questions:
        if q.evaluation is not None:
            by_day.setdefault(q.day, []).append(q.evaluation.get("score", 0))

    scores = []
    for day, values in by_day.items():
        chunk = retriever.get_day(day)
        title = chunk.title if chunk else f"Day {day}"
        scores.append(TopicScore(day=day, title=title, score=round(average(values), 1)))
    return sorted(scores, key=lambda t: t.score)


def _technical_level(overall_score: float, candidate: dict) -> str:
    years = candidate.get("member", {}).get("yearsExperience", 0)
    if overall_score >= 80:
        return "Advanced"
    if overall_score >= 60:
        return "Intermediate" if years < 8 else "Solid Mid-to-Senior"
    if overall_score >= 40:
        return "Developing"
    return "Foundational — needs significant reinforcement"


def _collect_misconceptions(state: InterviewState) -> list[str]:
    seen = []
    for q in state.questions:
        if q.evaluation:
            for m in q.evaluation.get("misconceptions", []) or []:
                if m and m not in seen:
                    seen.append(m)
    return seen


class FeedbackGenerator:
    def __init__(self, llm: BaseLLMClient | None = None) -> None:
        self._llm = llm or get_llm_client()

    def generate(self, state: InterviewState) -> dict:
        topic_scores = _topic_scores(state)
        all_scores = [q.evaluation.get("score", 0) for q in state.questions if q.evaluation]
        overall_score = round(average(all_scores), 1)
        technical_level = _technical_level(overall_score, state.candidate)
        misconceptions = _collect_misconceptions(state)

        comm_qualities = [
            q.evaluation.get("communication_quality", "adequate")
            for q in state.questions
            if q.evaluation
        ]
        communication_quality = max(set(comm_qualities), key=comm_qualities.count) if comm_qualities else "adequate"

        weakest_topics = [t.title for t in topic_scores[:3] if t.score < 65]
        strongest_topics = [t.title for t in reversed(topic_scores) if t.score >= 70][:3]

        transcript_lines = []
        for q in state.questions:
            if q.answer is None:
                continue
            transcript_lines.append(
                f"[Day {q.day} | {q.topic_title} | {'follow-up' if q.is_followup else 'main'} | "
                f"score={q.evaluation.get('score') if q.evaluation else 'n/a'}]\n"
                f"Q: {q.question}\nA: {q.answer}"
            )
        transcript = "\n\n".join(transcript_lines)

        candidate = state.candidate.get("member", {})

        user_prompt = f"""
CANDIDATE
{candidate.get('name', 'Candidate')} — {candidate.get('jobRole', 'Unknown role')}, {candidate.get('yearsExperience', 0)} yrs experience.

OVERALL SCORE: {overall_score}/100
TECHNICAL LEVEL: {technical_level}
COMMUNICATION QUALITY: {communication_quality}
STRONGEST TOPICS: {', '.join(strongest_topics) or 'none clearly standout'}
WEAKEST TOPICS: {', '.join(weakest_topics) or 'none clearly weak'}
MISCONCEPTIONS OBSERVED: {', '.join(misconceptions) or 'none observed'}

FULL INTERVIEW TRANSCRIPT
{transcript}

Write final interview feedback as a JSON object with exactly these fields:
{{
  "summary": "<3-5 sentence overall assessment, specific to this candidate's actual answers>",
  "strengths": [<3-5 short, specific, evidence-based strengths>],
  "gaps": [<2-4 short, specific, evidence-based gaps or weaknesses>],
  "next": [<3-4 short, concrete, actionable next steps for the candidate to improve>]
}}
""".strip()

        result = self._llm.complete_json(_SYSTEM_PERSONA, user_prompt)

        feedback = {
            "summary": result.get("summary") or self._fallback_summary(overall_score, technical_level),
            "strengths": result.get("strengths") or strongest_topics or ["Completed the interview end-to-end."],
            "gaps": result.get("gaps") or weakest_topics or ["No major gaps identified in this session."],
            "next": result.get("next") or ["Review the topics flagged above.", "Practice explaining trade-offs concisely."],
        }

        # Extra detail, useful for docs/tests/an optional richer UI — not
        # part of the required spec response but harmless to attach.
        feedback["_detail"] = {
            "overall_score": overall_score,
            "technical_level": technical_level,
            "communication_quality": communication_quality,
            "topic_scores": [t.__dict__ for t in topic_scores],
            "misconceptions": misconceptions,
        }
        return feedback

    @staticmethod
    def _fallback_summary(overall_score: float, technical_level: str) -> str:
        return (
            f"The candidate completed the interview with an overall score of {overall_score}/100, "
            f"placing them at a {technical_level.lower()} level based on the topics covered."
        )


_feedback_singleton: FeedbackGenerator | None = None


def get_feedback_generator() -> FeedbackGenerator:
    global _feedback_singleton
    if _feedback_singleton is None:
        _feedback_singleton = FeedbackGenerator()
    return _feedback_singleton
