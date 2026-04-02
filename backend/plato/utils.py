"""
backend/plato/utils.py
Stage 9 — Shared utility helpers for the Plato pipeline.

All pure-function helpers.  No DB or Ollama dependencies so every function
is directly unit-testable.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

from ai.zpd import compute_zpd_utility  # Single source of Gaussian truth

logger = logging.getLogger("plato.utils")


# ---------------------------------------------------------------------------
# Gaussian utility (thin wrapper — do NOT duplicate the formula here)
# ---------------------------------------------------------------------------

def gaussian_utility(sq: float, mu: float = 0.5, sigma: float = 0.2) -> float:
    """
    Thin delegation to ai.zpd.compute_zpd_utility.
    sq   : student success rate / capability score (0.0 – 1.0)
    mu   : centre of optimal frontier (default 0.5)
    sigma: width of the bell (default 0.2)
    Returns a score in (0, 1].
    """
    return compute_zpd_utility(sq, mu=mu, sigma=sigma)


# ---------------------------------------------------------------------------
# JSON parsing / cleanup for Ollama raw output
# ---------------------------------------------------------------------------

_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json(raw: str) -> Optional[Dict[str, Any]]:
    """
    Defensively extract a JSON object from an Ollama model response.

    Handles:
      - <think>…</think> prefixes produced by Qwen3 reasoning models
      - ```json … ``` code fences
      - Stray prose before/after the JSON object
      - Nested objects — grabs the outermost `{…}` block

    Returns parsed dict or None if extraction fails.
    """
    if not raw:
        return None

    # 1. Strip thinking tokens
    text = _THINK_TAG_RE.sub("", raw).strip()

    # 2. Unwrap code fences if present
    fence_match = _CODE_FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    # 3. Locate the outermost JSON object {…}
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        logger.warning("No JSON object delimiters found in Ollama output.")
        return None

    candidate = text[start:end]

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        logger.warning("JSON decode failed after extraction: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Candidate problem validation
# ---------------------------------------------------------------------------

REQUIRED_PROBLEM_FIELDS: Tuple[str, ...] = (
    "title",
    "statement",
    "difficulty",
    "visible_tests",
    "hidden_tests",
)


def validate_candidate(data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Check that a generated problem dict has the required fields and
    sane values.

    Returns (True, "") on success.
    Returns (False, reason) on failure — caller logs the reason and drops
    the candidate without crashing.
    """
    for field in REQUIRED_PROBLEM_FIELDS:
        if field not in data:
            return False, f"Missing required field: {field!r}"

    title = data.get("title", "")
    if not isinstance(title, str) or not title.strip():
        return False, "Field 'title' is empty or not a string"

    statement = data.get("statement", "")
    if not isinstance(statement, str) or len(statement.strip()) < 20:
        return False, "Field 'statement' is too short (< 20 chars)"

    difficulty = data.get("difficulty")
    if not isinstance(difficulty, (int, float)) or not (0.0 <= float(difficulty) <= 1.0):
        return False, f"Field 'difficulty' out of range [0,1]: {difficulty!r}"

    for list_field in ("visible_tests", "hidden_tests"):
        val = data.get(list_field)
        if not isinstance(val, list):
            return False, f"Field {list_field!r} must be a list, got {type(val).__name__}"

    return True, ""


# ---------------------------------------------------------------------------
# Content fingerprinting — lightweight duplicate detection
# ---------------------------------------------------------------------------

def content_hash(statement: str) -> str:
    """
    SHA-256 hash of the lowercased, whitespace-normalised problem statement.
    Used to skip near-identical problems before DB insert.
    """
    normalised = " ".join(statement.lower().split())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# WSFT input formatter
# ---------------------------------------------------------------------------

_INPUT_TEMPLATE = """\
### Input
Original problem: {original_statement}
Student failure mode: {failure_mode}
Root cause: {root_cause}

### Output
"""


def format_training_input(
    original_statement: str,
    failure_mode: str,
    root_cause: str,
) -> str:
    """
    Build the WSFT prompt string fed as `input_text` in TrainingExample.
    Keeping the template in one place means downstream LoRA code uses the
    same format automatically.
    """
    return _INPUT_TEMPLATE.format(
        original_statement=original_statement.strip(),
        failure_mode=failure_mode.strip(),
        root_cause=root_cause.strip(),
    )


# ---------------------------------------------------------------------------
# Serialise refined_problem dict to canonical JSON string
# ---------------------------------------------------------------------------

def refined_problem_to_json(data: Dict[str, Any]) -> str:
    """
    Serialise a refined problem dict to a deterministic JSON string.
    Sorts keys for stability; callers treat this string as the training label.
    """
    return json.dumps(data, sort_keys=True, ensure_ascii=False)
