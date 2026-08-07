"""
feedback_generator.py — turns a transcript into structured feedback.

Replace the scoring heuristic with a real evaluator (rubric-based or
LLM-based) when ready; the shape of the output is what app.py depends on.
"""


def generate_feedback(transcript: list[dict]) -> dict:
    days_covered = sorted({entry["day"] for entry in transcript})
    follow_up_count = sum(1 for entry in transcript if entry.get("follow_up"))

    # Placeholder scoring — swap for real evaluation logic.
    scores = {
        "coverage": min(10, len(days_covered) * 2),
        "depth": min(10, follow_up_count * 2),
        "communication": 7,  # TODO: derive from actual answer quality
    }

    return {
        "summary": (
            f"Candidate answered {len(transcript)} question(s) across "
            f"{len(days_covered)} curriculum day(s), with {follow_up_count} follow-up(s)."
        ),
        "scores": scores,
        "strengths": [],       # TODO: populate from analysis
        "improvements": [],    # TODO: populate from analysis
        "days_covered": days_covered,
    }