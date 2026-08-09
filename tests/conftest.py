import os
import sys
from pathlib import Path

# Make `backend` importable when running `pytest` from the project root.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Force a deterministic, offline LLM + embedding backend for the whole test suite.
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("EMBEDDING_BACKEND", "tfidf")

import pytest


@pytest.fixture
def sample_candidate() -> dict:
    return {
        "member": {
            "id": "CAND-TEST",
            "name": "Test Candidate",
            "jobRole": "AI Engineer",
            "yearsExperience": 5,
            "education": "BS Computer Science",
            "status": "COMPLETED",
        },
        "missions": [
            {"day": 7, "title": "Embeddings Explained", "passed": True, "attempts": 1},
            {"day": 8, "title": "Vector Databases Overview", "passed": True, "attempts": 1},
            {"day": 10, "title": "Retrieval & Matching Engine", "passed": False, "attempts": 3},
            {"day": 12, "title": "Prompt Engineering Fundamentals", "passed": True, "attempts": 4},
            {"day": 16, "title": "Chatbot Backend & API Integration", "passed": True, "attempts": 1},
            {"day": 22, "title": "Multi-Agent Orchestration", "passed": True, "attempts": 2},
            {"day": 23, "title": "Model Context Protocol (MCP)", "passed": True, "attempts": 2},
            {"day": 31, "title": "Capstone Project & Final Demo", "passed": True, "attempts": 1},
        ],
        "signals": {"commitDays": 28, "missionsCompleted": 8, "missionsFirstTry": 5},
    }
