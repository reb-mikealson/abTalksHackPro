"""
Conversation / interview state management.

Owns the lifecycle of an interview session: which candidate it belongs to,
which curriculum topics will be probed, what's been asked/answered so far,
current adaptive difficulty, and running strengths/weaknesses signals.

Storage is an in-memory dict by default (fine for a single-process hackathon
deployment and for tests). Swap `SessionStore` for a Redis/SQLite-backed
implementation without touching any calling code if you need multi-worker
persistence.
"""
from __future__ import annotations

import random
import time
import uuid
from dataclasses import dataclass, field
from threading import Lock

from backend.config import get_settings
from backend.services.retrieval import CurriculumChunk, get_retriever

# Curriculum day "types" ranked by how much technical depth they typically
# demonstrate — used purely as a *tie-breaker* signal when selecting which
# topics to interview on, never as a hard-coded question list.
_TYPE_WEIGHT = {
    "CAPSTONE": 5,
    "SHIP_IT": 4,
    "AI_CORE": 4,
    "BUILD": 3,
    "OPTIMIZE": 2,
    "LEARN": 2,
    "SETUP": 0,
}

DIFFICULTIES = ["easy", "medium", "hard"]


@dataclass
class QuestionRecord:
    index: int
    day: int
    topic_title: str
    question: str
    is_followup: bool
    difficulty: str
    followup_type: str | None = None
    answer: str | None = None
    evaluation: dict | None = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class InterviewState:
    session_id: str
    candidate: dict
    status: str = "not_started"  # not_started | in_progress | completed

    topic_queue: list[int] = field(default_factory=list)     # curriculum day numbers still to introduce
    topics_covered: list[int] = field(default_factory=list)  # day numbers already introduced as a *main* question
    current_day: int | None = None
    followups_on_current: int = 0

    difficulty: str = "medium"
    consecutive_strong: int = 0
    consecutive_weak: int = 0

    questions: list[QuestionRecord] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    misconceptions: list[str] = field(default_factory=list)

    # Rolling chat history used to give the LLM conversational context.
    history: list[dict] = field(default_factory=list)

    def main_question_count(self) -> int:
        return sum(1 for q in self.questions if not q.is_followup)

    def last_question(self) -> QuestionRecord | None:
        return self.questions[-1] if self.questions else None

    def add_history(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})
        # keep the window bounded so prompts don't grow unbounded
        if len(self.history) > 24:
            self.history = self.history[-24:]


def _score_day_for_candidate(chunk: CurriculumChunk, mission: dict | None) -> float:
    """Higher score == more interesting / informative to interview on."""
    score = float(_TYPE_WEIGHT.get(chunk.type, 2))

    if mission is None:
        # Candidate never touched this topic at all — deprioritize heavily,
        # we only want to probe what they actually engaged with.
        return -100.0

    if mission.get("skipped"):
        score -= 3.0  # still eligible (worth *lightly* probing) but low priority
    elif mission.get("passed") is False:
        score += 6.0  # failed topics are prime interview territory
    elif mission.get("passed") is True:
        attempts = mission.get("attempts", 1)
        if attempts >= 4:
            score += 4.0   # passed, but clearly struggled -> worth probing depth
        elif attempts >= 2:
            score += 1.5
        else:
            score += 0.5   # breezed through -> still worth a sanity-check question

    return score


def select_topics(candidate: dict, min_topics: int, target_topics: int = 6, seed: str | None = None) -> list[int]:
    """Pick curriculum days to interview a candidate on, grounded in what
    they actually did during the cohort (from candidate['missions']), padded
    out with other curriculum days if the candidate's own history is too
    sparse to reach `target_topics`."""
    retriever = get_retriever()
    missions_by_day = {m["day"]: m for m in candidate.get("missions", [])}

    rng = random.Random(seed or candidate.get("member", {}).get("id"))

    # Primary pool: topics the candidate actually engaged with, scored by
    # how informative they'd be to probe (failed/struggled topics first).
    primary: list[tuple[float, int]] = []
    for chunk in retriever.all_days:
        mission = missions_by_day.get(chunk.day)
        s = _score_day_for_candidate(chunk, mission)
        if s > -100.0:
            primary.append((s + rng.uniform(-0.75, 0.75), chunk.day))
    primary.sort(key=lambda pair: pair[0], reverse=True)
    ordered_days = [day for _, day in primary]

    # Fallback pool: curriculum days the candidate has no record of, used
    # only to pad out the interview when their own history is too sparse to
    # fill `target_topics` (or even `min_topics`). Non-SETUP days preferred.
    if len(ordered_days) < target_topics:
        remaining = [c for c in retriever.all_days if c.day not in missions_by_day]
        remaining.sort(key=lambda c: (_TYPE_WEIGHT.get(c.type, 2), rng.random()), reverse=True)
        for c in remaining:
            if c.day not in ordered_days:
                ordered_days.append(c.day)
            if len(ordered_days) >= target_topics:
                break

    top = ordered_days[:target_topics]
    if len(top) < min_topics:
        # last resort: pull in anything left in the whole curriculum,
        # including SETUP days, to satisfy the hard minimum.
        for c in retriever.all_days:
            if c.day not in top:
                top.append(c.day)
            if len(top) >= min_topics:
                break
    return top


class SessionStore:
    """Thread-safe in-memory session store."""

    def __init__(self) -> None:
        self._sessions: dict[str, InterviewState] = {}
        self._lock = Lock()

    def get(self, session_id: str) -> InterviewState | None:
        with self._lock:
            return self._sessions.get(session_id)

    def save(self, state: InterviewState) -> None:
        with self._lock:
            self._sessions[state.session_id] = state

    def exists(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._sessions


class ConversationManager:
    def __init__(self, store: SessionStore | None = None) -> None:
        self._store = store or SessionStore()
        self._settings = get_settings()

    # -- lifecycle --------------------------------------------------------
    def start_session(self, session_id: str, candidate: dict) -> InterviewState:
        existing = self._store.get(session_id)
        if existing is not None:
            return existing

        # One main question per topic by design, so we need at least
        # MIN_QUESTIONS distinct topics to reach the required question count.
        target_topics = max(self._settings.MIN_QUESTIONS, self._settings.MIN_TOPICS + 2)
        topic_queue = select_topics(
            candidate,
            min_topics=self._settings.MIN_TOPICS,
            target_topics=target_topics,
            seed=session_id,
        )
        state = InterviewState(
            session_id=session_id,
            candidate=candidate,
            status="in_progress",
            topic_queue=topic_queue,
        )
        self._store.save(state)
        return state

    def get_or_create(self, session_id: str, candidate: dict | None) -> InterviewState:
        existing = self._store.get(session_id)
        if existing is not None:
            return existing
        if candidate is None:
            # A follow-up message came in for a session we've never seen.
            # Build a minimal anonymous candidate so the interview can still
            # proceed gracefully rather than hard-failing.
            candidate = {
                "member": {"id": session_id, "name": "Candidate", "jobRole": "Unknown", "yearsExperience": 0},
                "missions": [],
            }
        return self.start_session(session_id, candidate)

    def save(self, state: InterviewState) -> None:
        self._store.save(state)

    def new_session_id(self) -> str:
        return str(uuid.uuid4())

    # -- topic / difficulty progression -----------------------------------
    def next_topic_day(self, state: InterviewState) -> int | None:
        """Pop the next uncovered topic from the queue, if any."""
        while state.topic_queue:
            day = state.topic_queue.pop(0)
            if day not in state.topics_covered:
                return day
        return None

    def begin_topic(self, state: InterviewState, day: int) -> None:
        state.current_day = day
        state.followups_on_current = 0
        if day not in state.topics_covered:
            state.topics_covered.append(day)

    def adjust_difficulty(self, state: InterviewState, score: int) -> None:
        """Adapt difficulty based on the most recent evaluation score (0-100)."""
        if score >= 75:
            state.consecutive_strong += 1
            state.consecutive_weak = 0
        elif score < 45:
            state.consecutive_weak += 1
            state.consecutive_strong = 0
        else:
            state.consecutive_strong = 0
            state.consecutive_weak = 0

        idx = DIFFICULTIES.index(state.difficulty)
        if state.consecutive_strong >= 2 and idx < len(DIFFICULTIES) - 1:
            state.difficulty = DIFFICULTIES[idx + 1]
            state.consecutive_strong = 0
        elif state.consecutive_weak >= 2 and idx > 0:
            state.difficulty = DIFFICULTIES[idx - 1]
            state.consecutive_weak = 0

    def is_ready_to_conclude(self, state: InterviewState) -> bool:
        enough_questions = state.main_question_count() >= self._settings.MIN_QUESTIONS
        enough_topics = len(state.topics_covered) >= self._settings.MIN_TOPICS
        no_more_topics = not state.topic_queue and state.followups_on_current >= self._settings.MAX_FOLLOWUPS_PER_TOPIC
        hard_cap = len(state.questions) >= self._settings.MAX_TOTAL_TURNS
        return hard_cap or (enough_questions and enough_topics and no_more_topics)


_manager_singleton: ConversationManager | None = None


def get_conversation_manager() -> ConversationManager:
    global _manager_singleton
    if _manager_singleton is None:
        _manager_singleton = ConversationManager()
    return _manager_singleton
