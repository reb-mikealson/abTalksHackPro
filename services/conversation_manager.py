"""
conversation_manager.py — drives the interview flow: asks questions,
collects answers, decides on follow-ups, and tracks context across turns.

NOTE: `_collect_answer` is a stub. Wire it up to your real answer source
(e.g. a chat/voice frontend, or an LLM-simulated candidate for testing).
"""

from services.question_generator import generate_questions

FOLLOW_UP_TRIGGER_WORDS = ("not sure", "maybe", "i think", "kind of", "sort of")


def _collect_answer(question: str, context: list[dict]) -> str:
    """
    STUB: replace with real answer collection (frontend call, LLM-simulated
    candidate, recorded transcript lookup, etc). Kept isolated here so the
    rest of the flow doesn't need to change when you wire up the real thing.
    """
    return "[candidate answer placeholder]"


def _needs_follow_up(answer: str) -> bool:
    lowered = answer.lower()
    return any(trigger in lowered for trigger in FOLLOW_UP_TRIGGER_WORDS) or len(answer.split()) < 5


def _generate_follow_up(question: str, answer: str) -> str:
    """Simple templated follow-up; swap for an LLM call for something smarter."""
    return f"Can you elaborate a bit more on your answer to: \"{question}\"?"


def run_interview(candidate_profile: dict, curriculum: dict) -> dict:
    """
    Runs the full interview loop and returns:
        {"transcript": [ {day, topic, question, answer, follow_up: bool}, ... ]}
    """
    base_questions = generate_questions(curriculum)

    transcript: list[dict] = []
    context: list[dict] = []  # running history, used to keep follow-ups relevant

    for q in base_questions:
        answer = _collect_answer(q["question"], context)
        entry = {
            "day": q["day"],
            "topic": q["topic"],
            "question": q["question"],
            "answer": answer,
            "follow_up": False,
        }
        transcript.append(entry)
        context.append(entry)

        if _needs_follow_up(answer):
            follow_up_question = _generate_follow_up(q["question"], answer)
            follow_up_answer = _collect_answer(follow_up_question, context)
            follow_up_entry = {
                "day": q["day"],
                "topic": q["topic"],
                "question": follow_up_question,
                "answer": follow_up_answer,
                "follow_up": True,
            }
            transcript.append(follow_up_entry)
            context.append(follow_up_entry)

    return {"transcript": transcript, "candidate": candidate_profile.get("name", "Unknown")}