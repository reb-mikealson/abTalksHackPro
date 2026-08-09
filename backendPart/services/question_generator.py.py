"""
question_generator.py — selects interview questions from the curriculum.

Curriculum shape expected in data/curriculum.json:
{
    "day_1": {"topic": "...", "questions": ["...", "..."]},
    "day_2": {"topic": "...", "questions": ["...", "..."]},
    ...
}
"""

import random

MIN_QUESTIONS = 8
MIN_DAYS = 4


def generate_questions(curriculum: dict, count: int = MIN_QUESTIONS, min_days: int = MIN_DAYS) -> list[dict]:
    """
    Picks `count` questions spread across at least `min_days` distinct curriculum days.
    Returns a list of {"day": str, "topic": str, "question": str}.
    """
    days = list(curriculum.keys())
    if len(days) < min_days:
        raise ValueError(
            f"Curriculum only has {len(days)} day(s); need at least {min_days} to build an interview."
        )

    selected_days = random.sample(days, k=min_days) if len(days) > min_days else days
    questions: list[dict] = []

    # Take at least one question per selected day first, to guarantee day coverage.
    for day in selected_days:
        day_questions = curriculum[day].get("questions", [])
        if not day_questions:
            continue
        questions.append({
            "day": day,
            "topic": curriculum[day].get("topic", day),
            "question": random.choice(day_questions),
        })

    # Fill remaining slots randomly from any day until we hit `count`.
    all_pairs = [
        (day, curriculum[day].get("topic", day), q)
        for day in curriculum
        for q in curriculum[day].get("questions", [])
    ]
    random.shuffle(all_pairs)

    for day, topic, q in all_pairs:
        if len(questions) >= count:
            break
        questions.append({"day": day, "topic": topic, "question": q})

    return questions[:max(count, len(selected_days))]