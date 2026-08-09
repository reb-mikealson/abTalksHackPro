from backend.services.conversation_manager import ConversationManager, SessionStore, QuestionRecord
from backend.services.feedback_generator import FeedbackGenerator


def _state_with_answers(sample_candidate):
    manager = ConversationManager(store=SessionStore())
    state = manager.start_session("feedback-session", sample_candidate)

    state.questions = [
        QuestionRecord(
            index=0, day=7, topic_title="Embeddings Explained",
            question="How do embeddings capture semantic meaning?",
            is_followup=False, difficulty="medium",
            answer="Embeddings map text into vectors so similar meanings are close together.",
            evaluation={"score": 80, "correct": True, "misconceptions": [], "reasoning": "Solid.", "communication_quality": "clear"},
        ),
        QuestionRecord(
            index=1, day=10, topic_title="Retrieval & Matching Engine",
            question="How would you merge SQL and vector search results?",
            is_followup=False, difficulty="medium",
            answer="I'd just pick whichever source returns first.",
            evaluation={"score": 30, "correct": False, "misconceptions": ["Ignores relevance ranking"], "reasoning": "Weak.", "communication_quality": "unclear"},
        ),
    ]
    return state


def test_feedback_has_required_spec_fields(sample_candidate):
    state = _state_with_answers(sample_candidate)
    fgen = FeedbackGenerator()
    feedback = fgen.generate(state)

    for field in ("summary", "strengths", "gaps", "next"):
        assert field in feedback
    assert isinstance(feedback["summary"], str) and feedback["summary"]
    assert isinstance(feedback["strengths"], list)
    assert isinstance(feedback["gaps"], list)
    assert isinstance(feedback["next"], list)


def test_feedback_detail_includes_topic_scores(sample_candidate):
    state = _state_with_answers(sample_candidate)
    fgen = FeedbackGenerator()
    feedback = fgen.generate(state)

    detail = feedback["_detail"]
    assert detail["overall_score"] == 55.0  # average of 80 and 30
    topic_titles = {t["title"] for t in detail["topic_scores"]}
    assert "Embeddings Explained" in topic_titles
    assert any("Retrieval" in t and "Matching Engine" in t for t in topic_titles)
