THE PROMPTS I USED ARE AS FOLLOWS
1. 
### The Interview Agent

Build the interviewer, not the interview.

### The Situation

The **AI Cohort** is a **31-day enterprise AI engineering program** covering modern AI topics including:

- Retrieval-Augmented Generation (RAG)
- Vector Databases
- Prompt Engineering
- Agentic AI
- Model Context Protocol (MCP)
- AI Deployment
- Production AI Systems

After completing the cohort, learners should be able to confidently explain the systems they built and the engineering decisions behind them.

However, preparing for technical interviews and effectively communicating this knowledge remains one of the biggest challenges.

Your task is to build an **AI Interview Agent** that conducts personalized technical interviews based on a candidate's learning journey throughout the cohort.

---

### Your Challenge

Design and build an AI agent capable of conducting a realistic, multi-turn technical interview.

The interview should:

- Assess the candidate's understanding of the concepts they have completed.
- Adapt naturally throughout the conversation.
- Ask intelligent follow-up questions.
- Maintain context across the interview.
- Provide actionable feedback at the end.

The overall experience should resemble a real technical interview rather than a scripted questionnaire.

---

### What You're Given

Every team will receive the following resources:

### 1. Curriculum

A structured JSON containing the complete **31-day AI Cohort curriculum**, including:

- Modules
- Daily topics
- Learning objectives
- Tools used throughout the program

### 2. Candidate Profiles

A collection of candidate profiles describing each participant's progress through the cohort, including:

- Completed missions
- Attempts
- Skipped topics
- Learning signals

### 3. Technical Specification

A separate document defining:

- Required API contract
- Submission requirements
- Request/response formats

---

### Minimum Requirements

Your solution **must**:

- Conduct a conversational technical interview.
- Ask a minimum of 8 questions covering at least 4 different curriculum days.
- Generate follow-up questions based on previous responses.
- Maintain conversation context throughout the interview.
- Produce structured feedback at the end of the interview.
- Expose the required HTTP endpoint defined in the Technical Specification.

You are free to choose any:

- AI models
- Frameworks
- Agent orchestration strategy
- Retrieval pipeline
- System architecture

---

### Out of Scope

The following are **not required**:

- Voice interaction
- User authentication
- Persistent user accounts
- Long-term conversation history
- Mobile applications

---

### Notes

- All curriculum and candidate data provided for this challenge are **synthetic** and intended solely for the hackathon.
- Teams may use any AI models, agent frameworks, vector databases, or supporting technologies.
- Creativity in interview flow, reasoning, interaction design, and overall user experience is highly encouraged.

---

### Attached Resources

- Curriculum JSON
- Candidate Profiles
- Technical Specification

this is the problem statement ,can you generate me a prompt which i can give to claude for making me this project with a neat and clean file structure of-

ai-interview-agent/

│

├── backend/

│   ├── app.py                # Main entry point (FastAPI/Flask server)

│   ├── routes/

│   │   └── interview\.py       # API endpoint for starting interviews

│   ├── services/

│   │   ├── conversation\_manager.py   # Handles interview flow & context

│   │   ├── question\_generator.py     # Generates questions from curriculum

│   │   ├── followup\_logic.py         # Creates follow-up questions

│   │   ├── feedback\_generator.py     # Produces final structured feedback

│   │   └── retrieval.py              # Connects to vector DB for curriculum

│   ├── models/

│   │   └── embeddings.py             # Embedding functions for curriculum data

│   ├── utils/

│   │   └── helpers.py                # Utility functions (logging, formatting)

│   └── config.py             # Configuration (DB paths, API keys, settings)

│

├── data/

│   ├── curriculum.json       # 31-day cohort syllabus

│   ├── candidate\_profiles/   # Profiles for each participant

│   └── technical\_spec.json   # API contract & requirements

│

├── tests/

│   ├── test\_interview\_flow\.py        # Unit tests for conversation manager

│   ├── test\_question\_generator.py    # Tests for question generation

│   └── test\_feedback\_generator.py    # Tests for feedback logic

│

├── docs/

│   ├── architecture.md       # Explanation of system design

│   └── api\_spec.md           # API contract documentation

│

├── requirements.txt          # Python dependencies

└── README.md                 # Project overview & setup instructions








2.
make it a bit brief but still effective






3.
# Build: AI Interview Agent

You are a **Senior AI Engineer and Python Backend Developer**. Build a complete, hackathon-ready **AI Interview Agent** for a 31-day Enterprise AI Engineering cohort.

The goal is to **build the interviewer, not a static interview questionnaire**.

## 1. First inspect the provided files

Before coding, carefully inspect:

* `curriculum.json`
* `candidate_profiles/`
* `technical_spec.json`

Treat `technical_spec.json` as the **source of truth for the API contract**. Do not invent or modify the required request/response format.

---

## 2. Core Requirements

The agent must:

* Conduct a realistic multi-turn technical interview.
* Personalize questions using the candidate profile and curriculum.
* Ask **at least 8 questions across at least 4 curriculum days/topics**.
* Generate intelligent follow-up questions based on previous answers.
* Maintain conversation context/state.
* Adapt question difficulty based on performance.
* Evaluate candidate answers.
* Generate structured, actionable feedback at the end.

The interview must feel like a real technical interview, **not a predefined list of questions**.

The flow should roughly be:

```text
Candidate Profile + Curriculum
              ↓
        Retrieval / RAG
              ↓
      Question Generation
              ↓
     Candidate's Answer
              ↓
       Answer Evaluation
              ↓
 Follow-up OR Next Question
              ↓
        Final Feedback
```

---

## 3. Required File Structure

Use this structure:

```text
ai-interview-agent/
│
├── backend/
│   ├── app.py
│   ├── routes/
│   │   └── interview.py
│   ├── services/
│   │   ├── conversation_manager.py
│   │   ├── question_generator.py
│   │   ├── followup_logic.py
│   │   ├── feedback_generator.py
│   │   └── retrieval.py
│   ├── models/
│   │   └── embeddings.py
│   ├── utils/
│   │   └── helpers.py
│   └── config.py
│
├── data/
│   ├── curriculum.json
│   ├── candidate_profiles/
│   └── technical_spec.json
│
├── tests/
│   ├── test_interview_flow.py
│   ├── test_question_generator.py
│   └── test_feedback_generator.py
│
├── docs/
│   ├── architecture.md
│   └── api_spec.md
│
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

You may add small supporting files such as `__init__.py` if required.

---

## 4. Technology

Prefer:

* Python 3.11+
* FastAPI
* Pydantic
* Uvicorn
* ChromaDB or another lightweight vector DB
* Configurable LLM provider
* Environment variables for API keys

Do not hard-code secrets.

Keep the architecture simple and understandable.

---

## 5. Important Components

### `conversation_manager.py`

Maintain interview state:

* candidate ID
* questions asked
* answers
* topics covered
* evaluations
* current difficulty
* strengths/weaknesses
* interview status

### `question_generator.py`

Generate questions using:

* curriculum
* candidate progress
* completed/skipped topics
* previous questions
* previous answers
* current performance

Do **not** hard-code questions or curriculum days.

### `followup_logic.py`

Decide whether to:

* ask for clarification
* go deeper
* challenge an incorrect answer
* ask for an example
* ask about trade-offs
* move to another topic

Example:

Candidate:

> "RAG prevents hallucinations."

Good follow-up:

> "Does RAG guarantee that hallucinations cannot occur? What other factors affect RAG reliability?"

### `feedback_generator.py`

Generate structured feedback including:

* overall score
* technical level
* topic-wise scores
* strengths
* weaknesses
* misconceptions
* communication quality
* recommended topics to revise
* actionable next steps

### `retrieval.py`

Create a lightweight RAG pipeline over the curriculum using embeddings + vector DB.

---

## 6. API

Implement the exact endpoint(s) required by `technical_spec.json`.

Keep routes thin. Business logic should remain inside services.

If FastAPI is used, provide Swagger documentation.

---

## 7. Testing

Create tests for:

* interview state/context
* question generation
* adaptive follow-ups
* candidate personalization
* feedback generation

Mock external LLM/API calls.

Tests must run with:

```bash
pytest
```

---

## 8. Documentation

### `README.md`

Include:

* project overview
* features
* architecture
* setup
* environment variables
* how to run
* API usage
* testing
* example interview flow

### `docs/architecture.md`

Explain:

* system architecture
* RAG/retrieval
* conversation management
* question generation
* follow-up logic
* feedback generation

### `docs/api_spec.md`

Document the actual API based on `technical_spec.json`.

---

## 9. Development Rules

Build the project in this order:

1. Inspect provided data.
2. Understand API specification.
3. Create structure.
4. Implement data loading + retrieval.
5. Implement question generation.
6. Implement answer evaluation + follow-ups.
7. Implement conversation manager.
8. Implement feedback.
9. Implement API.
10. Add tests and documentation.
11. Run tests and fix errors.

Do not stop at pseudocode or architecture suggestions. **Build the actual working project.**

Avoid:

* static question lists
* hard-coded curriculum days
* hard-coded candidate information
* unnecessary complexity
* API keys in code
* putting everything in `app.py`

The final project should clearly demonstrate:

**Candidate Profile + Curriculum + RAG + LLM + Conversation Memory + Adaptive Follow-ups + Answer Evaluation + Structured Feedback = AI Technical Interviewer**

If you have filesystem access, create the files directly. Otherwise, provide complete code for each file with its path.





