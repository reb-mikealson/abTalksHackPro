from backend.services.conversation_manager import get_conversation_manager, select_topics, ConversationManager, SessionStore
from backend.services.question_generator import QuestionGenerator
from backend.services.retrieval import get_retriever


def test_retriever_loads_all_curriculum_days():
    retriever = get_retriever()
    assert len(retriever.all_days) == 31
    day7 = retriever.get_day(7)
    assert day7 is not None
    assert "Embeddings" in day7.title


def test_retriever_search_returns_relevant_chunks():
    retriever = get_retriever()
    results = retriever.search("vector database retrieval", top_k=3)
    assert len(results) == 3
    titles = [r.title for r in results]
    # at least one of the top results should be topically related
    assert any("Vector" in t or "Retrieval" in t or "Database" in t for t in titles)


def test_select_topics_prioritizes_failed_and_struggled_topics(sample_candidate):
    topics = select_topics(sample_candidate, min_topics=4, target_topics=6, seed="test-seed")
    assert len(topics) >= 4
    # Day 10 was failed (passed=False) and day 12 took 4 attempts — both should
    # be prioritized into the selection given they scored highest.
    assert 10 in topics
    assert 12 in topics


def test_select_topics_meets_minimum_even_with_sparse_profile():
    sparse_candidate = {
        "member": {"id": "X", "name": "Sparse", "jobRole": "Tester", "yearsExperience": 1},
        "missions": [{"day": 7, "title": "Embeddings Explained", "passed": True, "attempts": 1}],
    }
    topics = select_topics(sparse_candidate, min_topics=4, target_topics=6, seed="sparse-seed")
    assert len(topics) >= 4


def test_question_generator_produces_nonempty_question(sample_candidate):
    manager = ConversationManager(store=SessionStore())
    state = manager.start_session("sess-qgen", sample_candidate)
    day = manager.next_topic_day(state)
    manager.begin_topic(state, day)

    qgen = QuestionGenerator()
    question = qgen.opening_question(state, day)
    assert isinstance(question, str)
    assert len(question.strip()) > 0


def test_question_generator_no_hardcoded_question_bank():
    # The generator module should contain no static list of question strings —
    # every question must be produced by the LLM at run time.
    import inspect
    from backend.services import question_generator as qg_module

    source = inspect.getsource(qg_module)
    assert "QUESTION_BANK" not in source
    assert '"What is' not in source  # no literal hard-coded question text
