from backend.services.conversation_manager import ConversationManager, SessionStore
from backend.services.interview_orchestrator import InterviewOrchestrator


def _make_orchestrator() -> InterviewOrchestrator:
    # Fresh, isolated state store per test so tests don't leak sessions.
    manager = ConversationManager(store=SessionStore())
    return InterviewOrchestrator(manager=manager)


def test_start_interview_returns_first_question(sample_candidate):
    orch = _make_orchestrator()
    result = orch.handle_turn("session-1", sample_candidate, None)
    assert result["done"] is False
    assert isinstance(result["reply"], str) and result["reply"]


def test_starting_twice_is_idempotent(sample_candidate):
    orch = _make_orchestrator()
    first = orch.handle_turn("session-idem", sample_candidate, None)
    second = orch.handle_turn("session-idem", sample_candidate, None)
    # Second "start" call for an existing session should not reset progress —
    # it should return the same in-flight question rather than a new one.
    assert first["reply"] == second["reply"]


def test_full_interview_reaches_completion_with_min_questions_and_topics(sample_candidate):
    orch = _make_orchestrator()
    session_id = "session-full"

    result = orch.handle_turn(session_id, sample_candidate, None)
    assert result["done"] is False

    main_question_days = set()
    turns = 0
    while not result["done"] and turns < 40:
        state = orch._manager.get_or_create(session_id, None)
        last_q = state.last_question()
        if last_q and not last_q.is_followup:
            main_question_days.add(last_q.day)

        # Simulate a reasonably detailed candidate answer.
        answer = (
            "I would approach this by first understanding the retrieval step, "
            "then grounding the generation in retrieved context, and I'd "
            "consider trade-offs like latency versus accuracy."
        )
        result = orch.handle_turn(session_id, None, answer)
        turns += 1

    assert result["done"] is True
    assert "feedback" in result
    feedback = result["feedback"]
    assert set(feedback.keys()) == {"summary", "strengths", "gaps", "next"}
    assert isinstance(feedback["strengths"], list)
    assert isinstance(feedback["gaps"], list)
    assert isinstance(feedback["next"], list)

    state = orch._manager.get_or_create(session_id, None)
    assert state.main_question_count() >= 8
    assert len(state.topics_covered) >= 4


def test_response_shape_matches_spec_contract(sample_candidate):
    orch = _make_orchestrator()
    result = orch.handle_turn("session-shape", sample_candidate, None)
    assert set(result.keys()) <= {"reply", "done", "feedback"}
    assert "reply" in result and "done" in result


def test_followup_generated_for_low_quality_answer(sample_candidate):
    orch = _make_orchestrator()
    session_id = "session-followup"
    orch.handle_turn(session_id, sample_candidate, None)

    state = orch._manager.get_or_create(session_id, None)
    questions_before = len(state.questions)

    # A very short/low-effort answer should trigger a clarify/example follow-up
    # rather than immediately advancing to a brand-new topic.
    orch.handle_turn(session_id, None, "not sure")

    state = orch._manager.get_or_create(session_id, None)
    assert len(state.questions) == questions_before + 1
    assert state.questions[-1].is_followup is True
