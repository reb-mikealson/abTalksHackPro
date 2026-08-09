"""
Centralized configuration for the AI Interview Agent.

All secrets/config come from environment variables (see .env.example).
Never hard-code API keys here.
"""
from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv is optional at runtime (e.g. in CI); real deployments
    # should set env vars directly or install python-dotenv.
    pass

BASE_DIR = Path(__file__).resolve().parent.parent  # project root
DATA_DIR = BASE_DIR / "data"


class Settings:
    """Simple settings object populated from environment variables."""

    # --- LLM provider config -------------------------------------------------
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "anthropic")  # anthropic | openai | mock
    ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_BASE_URL: str | None = os.getenv("OPENAI_BASE_URL")  # for Groq/Ollama/OpenAI-compatible

    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "1024"))
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.4"))

    # --- Interview shape -------------------------------------------------------
    MIN_QUESTIONS: int = int(os.getenv("MIN_QUESTIONS", "8"))
    MIN_TOPICS: int = int(os.getenv("MIN_TOPICS", "4"))
    MAX_FOLLOWUPS_PER_TOPIC: int = int(os.getenv("MAX_FOLLOWUPS_PER_TOPIC", "2"))
    MAX_TOTAL_TURNS: int = int(os.getenv("MAX_TOTAL_TURNS", "22"))  # hard safety cap

    # --- Data paths --------------------------------------------------------
    CURRICULUM_PATH: Path = DATA_DIR / "curriculum.json"
    CANDIDATES_PATH: Path = DATA_DIR / "candidate_profiles" / "candidates.json"

    # --- Server ------------------------------------------------------------
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")

    # --- Session persistence -------------------------------------------------
    SESSION_STORE: str = os.getenv("SESSION_STORE", "memory")  # memory | sqlite
    SQLITE_PATH: str = os.getenv("SQLITE_PATH", str(BASE_DIR / "interview_sessions.db"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
