
"""
Orchestrates a single interview turn.

This is the "brain" that implements the flow diagram from the spec:

    Candidate Profile + Curriculum
                  |
            Retrieval / RAG
                  |
          Question Generation
                  |
         Candidate's Answer
                  |
           Answer Evaluation
                  |
     Follow-up OR Next Question
                  |
            Final Feedback

Routes stay thin and simply call `handle_turn`.
"""
from __future__ import annotations

from backend.config import get_settings
from backend.services.conversation_manager import (
    ConversationManager,
    InterviewState,
    QuestionRecord,
    get_conversation_manager,
)
from backend.services.feedback_generator import FeedbackGenerator, get_feedback_generator
from backend.services.followup_logic import decide_followup, generate_followup_question
from backend.services.llm_client import BaseLLMClient, get_llm_client
from backend.services.question_generator import QuestionGenerator, get_question_generator
from backend.services.retrieval import get_retriever


class InterviewOrchestrator:
    def __init__(
        self,
        manager: ConversationManager | None = None,
        question_generator: QuestionGenerator | None = None,
        feedback_generator: FeedbackGenerator | None = None,
        llm: BaseLLMClient | None = None,
    ) -> None:
        self._manager = manager or get_conversation_manager()
        self._qgen = question_generator or get_question_generator()
        self._fgen = feedback_generator or get_feedback_generator()
        self._llm = llm or get_llm_client()
        self._settings = get_settings()

    # -- entrypoint ----------------------------------------------------------
    def handle_turn(self, session_id: str, candidate: dict | None, message: str | None) -> dict:
        is_start = candidate is not None and message is None

        if is_start:
            return self._start_interview(session_id, candidate)

        state = self._manager.get_or_create(session_id, candidate=None)
        if state.status == "completed":
            return {
                "reply": "This interview has already concluded. Thank you for your time!",
                "done": True,
            }
        return self._continue_interview(state, message or "")

    # -- start -----------------------------------------------------------------
    def _start_interview(self, session_id: str, candidate: dict) -> dict:
        state = self._manager.start_session(session_id, candidate)
        first_day = self._manager.next_topic_day(state)

        if first_day is None:
            # Extremely defensive fallback — should not happen given curriculum size.
            self._manager.save(state)
            return {"reply": "Welcome! Unfortunately no interview topics could be prepared for this profile.", "done": True}

        self._manager.begin_topic(state, first_day)
        chunk = get_retriever().get_day(first_day)
        question_text = self._qgen.opening_question(state, first_day)

        record = QuestionRecord(
            index=len(state.questions),
            day=first_day,
            topic_title=chunk.title if chunk else f"Day {first_day}",
            question=question_text,
            is_followup=False,
            difficulty=state.difficulty,
        )
        state.questions.append(record)
        state.add_history("assistant", question_text)
        self._manager.save(state)

        return {"reply": question_text, "done": False}

    # -- continue ------------------------------------------------------------
    def _continue_interview(self, state: InterviewState, message: str) -> dict:
        last_question = state.last_question()
        if last_question is None:
            # No question was ever asked (shouldn't normally happen) — recover
            # by starting fresh with the already-known candidate profile.
            return self._start_interview(state.session_id, state.candidate)

        # 1. Record + evaluate the candidate's answer to the last question.
        last_question.answer = message
        state.add_history("user", message)

        evaluation = self._qgen.evaluate_answer(state, last_question, message)
        last_question.evaluation = evaluation
        self._manager.adjust_difficulty(state, evaluation["score"])

        if evaluation["score"] >= 70:
            note = f"Strong understanding of {last_question.topic_title}."
            if note not in state.strengths:
                state.strengths.append(note)
        elif evaluation["score"] < 45:
            note = f"Gap identified in {last_question.topic_title}."
            if note not in state.weaknesses:
                state.weaknesses.append(note)
        for m in evaluation.get("misconceptions", []) or []:
            if m not in state.misconceptions:
                state.misconceptions.append(m)

        # 2. Decide: follow up on this topic, or move to the next one.
        decision = decide_followup(state, last_question, evaluation, message)

        if decision.action != "move_on":
            state.followups_on_current += 1
            followup_text = generate_followup_question(self._llm, state, last_question, message, decision)
            record = QuestionRecord(
                index=len(state.questions),
                day=last_question.day,
                topic_title=last_question.topic_title,
                question=followup_text,
                is_followup=True,
                difficulty=state.difficulty,
                followup_type=decision.action,
            )
            state.questions.append(record)
            state.add_history("assistant", followup_text)
            self._manager.save(state)
            return {"reply": followup_text, "done": False}

        # 3. Moving on — either to the next topic, or to final feedback.
        if self._manager.is_ready_to_conclude(state):
            return self._conclude(state)

        next_day = self._manager.next_topic_day(state)
        if next_day is None:
            return self._conclude(state)

        self._manager.begin_topic(state, next_day)
        chunk = get_retriever().get_day(next_day)
        question_text = self._qgen.main_question(state, next_day, chunk)
        record = QuestionRecord(
            index=len(state.questions),
            day=next_day,
            topic_title=chunk.title if chunk else f"Day {next_day}",
            question=question_text,
            is_followup=False,
            difficulty=state.difficulty,
        )
        state.questions.append(record)
        state.add_history("assistant", question_text)
        self._manager.save(state)
        return {"reply": question_text, "done": False}

    # -- conclude ------------------------------------------------------------
    def _conclude(self, state: InterviewState) -> dict:
        feedback = self._fgen.generate(state)
        state.status = "completed"
        self._manager.save(state)
        return {
            "reply": "Interview completed. Thank you for your time — here is your feedback.",
            "done": True,
            "feedback": {
                "summary": feedback["summary"],
                "strengths": feedback["strengths"],
                "gaps": feedback["gaps"],
                "next": feedback["next"],
            },
        }


_orchestrator_singleton: InterviewOrchestrator | None = None


def get_orchestrator() -> InterviewOrchestrator:
    global _orchestrator_singleton
    if _orchestrator_singleton is None:
        _orchestrator_singleton = InterviewOrchestrator()
    return _orchestrator_singleton
