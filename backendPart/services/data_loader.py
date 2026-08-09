"""
data_loader.py — reads candidate profiles and curriculum from the data/ folder.

Keeps all file I/O and data-shape knowledge out of app.py.
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CANDIDATES_FILE = DATA_DIR / "candidates.json"
CURRICULUM_FILE = DATA_DIR / "curriculum.json"


def load_candidate_profile(candidate_id: str) -> dict:
    """
    Returns the profile dict for a given candidate_id.
    Raises FileNotFoundError if the candidates file or the candidate is missing.
    """
    if not CANDIDATES_FILE.exists():
        raise FileNotFoundError(f"Candidates data file not found at {CANDIDATES_FILE}")

    with open(CANDIDATES_FILE, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    profile = candidates.get(candidate_id)
    if profile is None:
        raise FileNotFoundError(f"Candidate '{candidate_id}' not found")

    return profile


def load_curriculum() -> dict:
    """
    Returns the full curriculum dict, keyed by day.
    Raises FileNotFoundError if the curriculum file is missing.
    """
    if not CURRICULUM_FILE.exists():
        raise FileNotFoundError(f"Curriculum file not found at {CURRICULUM_FILE}")

    with open(CURRICULUM_FILE, "r", encoding="utf-8") as f:
        return json.load(f)