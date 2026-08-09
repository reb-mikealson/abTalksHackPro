"""
Decides, after each evaluated answer, whether to:
  - clarify      : the answer was ambiguous/incomplete, ask them to clarify
  - deeper       : the answer was correct but shallow, push for more depth
  - challenge    : the answer contained a misconception, challenge it directly
  - example      : ask for a concrete example / real usage
  - tradeoffs    : ask about trade-offs, edge cases, or alternatives
  - move_on      : sufficient signal gathered, advance to the next topic

This mirrors how a real interviewer probes: never a fixed script, always a
reaction to what the candidate just said.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.config import get_settings
from backend.services.conversation_manager import InterviewState, QuestionRecord
from backend.services.llm_client import BaseLLMClient, get_llm_client
from backend.services.retrieval import get_retriever
from backend.utils.helpers import truncate, word_count

FOLLOWUP_ACTIONS = ["clarify", "deeper", "challenge", "example", "tradeoffs", "move_on"]

_SYSTEM_PERSONA = (
    "You are a senior technical interviewer conducting a live technical "
    "interview. You react naturally to what the candidate just said — you "
    "never ask generic questions unrelated to their actual answer."
)


@dataclass
class FollowupDecision:
    action: str
    reasoning: str = ""


def decide_followup(state: InterviewState, question: QuestionRecord, evaluation: dict, answer: str) -> FollowupDecision:
    settings = get_settings()

    # Hard stop: we've already followed up enough on this topic.
    if state.followups_on_current >= settings.MAX_FOLLOWUPS_PER_TOPIC:
        return FollowupDecision(action="move_on", reasoning="Follow-up budget for this topic reached.")

    score = evaluation.get("score", 50)
    misconceptions = evaluation.get("misconceptions") or []
    too_short = word_count(answer) < 12

    # Deterministic guardrails for clear-cut cases keep behavior predictable
    # and cheap; ambiguous cases are handed to the LLM for a judgment call.
    if misconceptions:
        return FollowupDecision(action="challenge", reasoning="Evaluation flagged a misconception to challenge.")
    if too_short:
        return FollowupDecision(action="clarify", reasoning="Answer was too brief to assess.")
    if score >= 85:
        return FollowupDecision(action="tradeoffs", reasoning="Strong answer — probe trade-off awareness.")
    if score < 45:
        return FollowupDecision(action="example", reasoning="Weak answer — ask for a concrete example to check understanding.")

    # Middle ground: let the LLM decide between deeper / example / move_on
    # based on the actual conversational content.
    chunk = get_retriever().get_day(question.day)
    context = chunk.to_context_string() if chunk else ""
    llm = get_llm_client()

    user_prompt = f"""
CURRICULUM CONTEXT
{context}

QUESTION
{question.question}

CANDIDATE ANSWER
{answer}

EVALUATION
score={score}, communication_quality={evaluation.get('communication_quality')}

Decide the single best next interviewer move. Respond as JSON:
{{"action": "<one of: clarify, deeper, example, tradeoffs, move_on>", "reasoning": "<one sentence>"}}
""".strip()

    result = llm.complete_json(_SYSTEM_PERSONA, user_prompt)
    action = result.get("action", "deeper")
    if action not in FOLLOWUP_ACTIONS:
        action = "deeper"
    return FollowupDecision(action=action, reasoning=result.get("reasoning", ""))


_ACTION_INSTRUCTIONS = {
    "clarify": "Ask the candidate to clarify or restate their answer more precisely — something in it was ambiguous or incomplete.",
    "deeper": "Push the candidate to go deeper on the mechanism or reasoning behind their answer — don't accept a surface-level explanation.",
    "challenge": "Politely but directly challenge the specific misconception in their answer, and ask them to reconsider. For example, if they overstate a guarantee, ask what could still go wrong.",
    "example": "Ask the candidate for a concrete, specific example or real scenario illustrating their answer.",
    "tradeoffs": "Ask the candidate about trade-offs, limitations, or alternative approaches related to their answer.",
}


def generate_followup_question(
    llm: BaseLLMClient,
    state: InterviewState,
    question: QuestionRecord,
    answer: str,
    decision: FollowupDecision,
) -> str:
    chunk = get_retriever().get_day(question.day)
    context = chunk.to_context_string() if chunk else ""
    instruction = _ACTION_INSTRUCTIONS.get(decision.action, _ACTION_INSTRUCTIONS["deeper"])

    user_prompt = f"""
CURRICULUM CONTEXT
{context}

ORIGINAL QUESTION
{question.question}

CANDIDATE'S ANSWER
{answer}

FOLLOW-UP GOAL
{instruction}

Write ONE natural, conversational follow-up question (1-2 sentences) that responds directly to what the candidate said. Do not restate the original question. Do not explain what you're doing — just ask the question as an interviewer would.
""".strip()

    return llm.complete(_SYSTEM_PERSONA, user_prompt).strip()
