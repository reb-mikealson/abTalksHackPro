"""Small, dependency-free helper functions shared across services."""
from __future__ import annotations

import json
import re
from typing import Any


def safe_json_parse(text: str) -> dict[str, Any] | None:
    """Best-effort parse of a JSON object out of an LLM response.

    LLMs sometimes wrap JSON in markdown fences or add stray prose. This
    strips common wrappers and tries a couple of fallback strategies before
    giving up.
    """
    if not text:
        return None

    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned.strip())
    cleaned = re.sub(r"```$", "", cleaned.strip())
    cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fallback: find the first {...} block greedily
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def truncate(text: str, max_len: int = 400) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def average(values: list[float]) -> float:
    values = [v for v in values if v is not None]
    if not values:
        return 0.0
    return sum(values) / len(values)
