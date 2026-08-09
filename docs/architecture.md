# Architecture

## Overview

The AI Interview Agent is a stateful conversational service exposed through
a single HTTP endpoint. Each `sessionId` maps to an `InterviewState` that
tracks everything about that interview: which candidate it's for, which
curriculum topics have been covered, the full question/answer/evaluation
history, current adaptive difficulty, and accumulated strengths/weaknesses.

A single request handler (`InterviewOrchestrator.handle_turn`) drives the
whole flow described in the top-level README's diagram, delegating each
stage to a focused service module.

## Components

### `retrieval.py` — RAG over the curriculum

`CurriculumRetriever` loads `data/curriculum.json`, flattens each day into a
retrievable text chunk (title + type + tools + objectives), and builds a
vector index over the corpus using an `EmbeddingBackend` (see
`models/embeddings.py`). At query time, callers pass a free-text query
(a topic title, or content derived from the candidate's previous answer)
and get back the `top_k` most semantically similar curriculum days by
cosine similarity.

This is genuine retrieval, not a dictionary lookup: `question_generator.py`
asks the index for chunks *related to* the current topic (not just the
exact day) to give the LLM richer grounding, and nothing in the codebase
hard-codes which day maps to which question.

### `models/embeddings.py` — embedding backend

Two interchangeable backends behind one interface (`fit(corpus)`,
`embed(texts) -> np.ndarray`):

- **`TfidfEmbeddingBackend`** (default): scikit-learn TF-IDF vectorizer
  fit on the curriculum corpus. Fully offline, no model download, fast to
  start — ideal for a hackathon/demo environment.
- **`SentenceTransformerEmbeddingBackend`** (optional): wraps
  `sentence-transformers` for denser semantic embeddings, if you have
  network/model-cache access. Swap via `EMBEDDING_BACKEND=sentence-transformers`.

### `conversation_manager.py` — state + personalization

- `InterviewState` / `QuestionRecord`: the full state machine's data model.
- `select_topics(candidate, ...)`: scores every curriculum day the
  candidate has a mission record for for how *informative* it would be to
  interview on — failed topics and topics passed only after many attempts
  score highest, topics passed easily score lowest (but are still included
  for a sanity check), skipped topics are included at low priority. If the
  candidate's own history doesn't cover enough topics to reach
  `MIN_QUESTIONS`, the pool is padded with other curriculum days ranked by
  how central they are (`SHIP_IT`/`CAPSTONE`/`AI_CORE` days first).
- `ConversationManager`: session lifecycle (`start_session`,
  `get_or_create`), topic queue progression (`next_topic_day`,
  `begin_topic`), adaptive difficulty (`adjust_difficulty` — two strong
  answers bump difficulty up, two weak answers bump it down), and the
  termination condition (`is_ready_to_conclude`).
- `SessionStore`: a thread-safe in-memory dict. Swappable for a persistent
  backend without touching any calling code.

### `question_generator.py` — question generation + evaluation

- `opening_question` / `main_question`: build a prompt combining (a) the
  candidate's profile and per-topic mission history, (b) retrieved
  curriculum context for the target topic *and* semantically related
  topics, (c) current difficulty, and (d) the list of questions already
  asked (to avoid repeats) — then call the LLM to produce exactly one
  open-ended question. No question text is ever hard-coded.
- `evaluate_answer`: sends the question + answer + curriculum context to
  the LLM and parses a structured JSON evaluation
  (`score`, `correct`, `misconceptions`, `reasoning`, `communication_quality`).

### `followup_logic.py` — adaptive follow-ups

`decide_followup` combines cheap deterministic guardrails (a flagged
misconception → `challenge`; a too-short answer → `clarify`; a very
high/low score → `tradeoffs`/`example`) with an LLM judgment call for
ambiguous middle-ground answers, to decide the single next interviewer
move: `clarify`, `deeper`, `challenge`, `example`, `tradeoffs`, or
`move_on`. `generate_followup_question` then asks the LLM for one
natural follow-up question that reacts to what the candidate actually said
— e.g. "RAG prevents hallucinations" → "Does RAG *guarantee* hallucinations
can't occur? What else affects reliability?"

### `feedback_generator.py` — final structured feedback

Aggregates every evaluated question into topic-wise scores, an overall
score, an inferred technical level, and dominant communication quality,
then asks the LLM to synthesize a specific, evidence-based summary,
strengths, gaps, and next steps — grounded in the actual interview
transcript, not generic templates. The output always includes the four
fields required by the spec (`summary`, `strengths`, `gaps`, `next`); a
`_detail` field with the richer breakdown is attached for debugging/tests
but is stripped before being returned over the API.

### `llm_client.py` — pluggable LLM provider

One `BaseLLMClient.complete(system, user, json_mode)` interface, with three
implementations: `AnthropicLLMClient`, `OpenAICompatibleLLMClient` (works
with OpenAI or any OpenAI-compatible endpoint via `OPENAI_BASE_URL`, e.g.
Groq or a local Ollama server), and `MockLLMClient` (deterministic,
offline — used automatically if no provider/key is configured, and forced
in tests).

### `interview_orchestrator.py` — ties it together

`InterviewOrchestrator.handle_turn(session_id, candidate, message)` is the
single function the route calls. It:

1. On the first call (candidate provided, no message): starts a session,
   selects topics, generates the opening question.
2. On every later call (message provided): records + evaluates the answer,
   adjusts difficulty, decides follow-up vs. move-on, and either asks a
   follow-up, asks the next topic's main question, or concludes the
   interview and returns feedback.

### `routes/interview.py` + `app.py`

The route is intentionally thin: Pydantic request/response models matching
`data/technical_spec.md` exactly, basic validation, and a single call into
the orchestrator. `app.py` wires up FastAPI, CORS, and a `/health` check;
Swagger docs are automatically available at `/docs`.

## Data Flow (single turn)

```
HTTP request
    │
    ▼
routes/interview.py  (validate request shape)
    │
    ▼
InterviewOrchestrator.handle_turn
    │
    ├─ ConversationManager        (load/create session state)
    ├─ QuestionGenerator.evaluate_answer   ──┐
    │                                        ├─ retrieval.py (RAG context)
    ├─ followup_logic.decide_followup        ├─ llm_client.py (LLM call)
    ├─ QuestionGenerator.main_question       │
    ├─ followup_logic.generate_followup_question
    └─ FeedbackGenerator.generate  (only on final turn)
    │
    ▼
{ reply, done, feedback? }
```
