"""
Configurable LLM client.

Supports:
  - "anthropic"  : Anthropic Messages API (default)
  - "openai"     : OpenAI or any OpenAI-compatible endpoint (Groq, Ollama, etc.
                    via OPENAI_BASE_URL)
  - "mock"       : deterministic offline stub, used by tests / when no API
                    key is configured, so the whole flow can run without a
                    real LLM.

Callers only ever see `LLMClient.complete(system, user, json_mode=False)`.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod

from backend.config import get_settings
from backend.utils.helpers import safe_json_parse

logger = logging.getLogger(__name__)


class BaseLLMClient(ABC):
    @abstractmethod
    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        """Return raw text completion from the model."""

    def complete_json(self, system: str, user: str) -> dict:
        """Complete and parse a JSON object, falling back to an empty dict."""
        raw = self.complete(system, user, json_mode=True)
        parsed = safe_json_parse(raw)
        return parsed or {}


class AnthropicLLMClient(BaseLLMClient):
    def __init__(self) -> None:
        settings = get_settings()
        import anthropic  # lazy import so the package is optional until used

        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")
        self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self._model = settings.ANTHROPIC_MODEL
        self._settings = settings

    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        if json_mode:
            system = system + "\n\nRespond with ONLY a valid JSON object. No markdown fences, no prose."
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._settings.LLM_MAX_TOKENS,
            temperature=self._settings.LLM_TEMPERATURE,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        return "".join(parts).strip()


class OpenAICompatibleLLMClient(BaseLLMClient):
    def __init__(self) -> None:
        settings = get_settings()
        from openai import OpenAI  # lazy import

        if not settings.OPENAI_API_KEY and not settings.OPENAI_BASE_URL:
            raise RuntimeError("OPENAI_API_KEY (or OPENAI_BASE_URL for local providers) is not set.")
        self._client = OpenAI(
            api_key=settings.OPENAI_API_KEY or "not-needed",
            base_url=settings.OPENAI_BASE_URL,
        )
        self._model = settings.OPENAI_MODEL
        self._settings = settings

    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        if json_mode:
            system = system + "\n\nRespond with ONLY a valid JSON object. No markdown fences, no prose."
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._settings.LLM_MAX_TOKENS,
            temperature=self._settings.LLM_TEMPERATURE,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (response.choices[0].message.content or "").strip()


class MockLLMClient(BaseLLMClient):
    """Deterministic offline stub used for tests and local dry-runs.

    It produces plausible, varied output using simple templating so the
    rest of the pipeline (state machine, follow-up logic, feedback shape)
    can be exercised without network access or an API key.
    """

    def complete(self, system: str, user: str, json_mode: bool = False) -> str:
        lowered = (system + user).lower()

        if json_mode and "evaluate" in lowered:
            return json.dumps({
                "score": 65,
                "correct": True,
                "misconceptions": [],
                "reasoning": "Mock evaluation: answer demonstrates baseline understanding.",
                "communication_quality": "clear",
            })

        if json_mode and "follow" in lowered:
            return json.dumps({
                "action": "go_deeper",
                "reasoning": "Mock follow-up decision.",
            })

        if json_mode and "feedback" in lowered:
            return json.dumps({
                "summary": "Mock summary: solid overall performance with a few gaps to revisit.",
                "strengths": ["Clear communication", "Good grasp of fundamentals"],
                "gaps": ["Could go deeper on trade-offs"],
                "next": ["Review the flagged topics", "Practice explaining trade-offs out loud"],
            })

        if "question" in lowered:
            return "Can you walk me through how you would approach this problem, including any trade-offs?"

        return "Thanks for sharing that — could you elaborate a bit further?"


def build_llm_client() -> BaseLLMClient:
    settings = get_settings()
    provider = settings.LLM_PROVIDER.lower()

    try:
        if provider == "anthropic":
            return AnthropicLLMClient()
        if provider == "openai":
            return OpenAICompatibleLLMClient()
        if provider == "mock":
            return MockLLMClient()
    except Exception as exc:  # missing key / package not installed
        logger.warning("Falling back to MockLLMClient: %s", exc)
        return MockLLMClient()

    logger.warning("Unknown LLM_PROVIDER=%s, falling back to MockLLMClient", provider)
    return MockLLMClient()


_llm_singleton: BaseLLMClient | None = None


def get_llm_client() -> BaseLLMClient:
    global _llm_singleton
    if _llm_singleton is None:
        _llm_singleton = build_llm_client()
    return _llm_singleton
