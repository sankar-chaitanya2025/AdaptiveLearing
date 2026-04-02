"""
backend/plato/tests/test_utils.py
Stage 9 — Unit tests for Plato utility helpers.

Tests cover:
  - Gaussian utility scoring (paper Eq. 6)
  - WSFT input formatting
  - JSON extraction from Ollama output variants
  - Candidate problem validation
  - Content hash fingerprinting
  - TrainingExample validation (malformed JSON rejection)
  - Filtering logic simulation

Run with:
    cd backend
    python -m pytest plato/tests/test_utils.py -v
"""

import json
import math
import sys
import types
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Path setup — allows running from backend/ without install
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Stub the ai.zpd dependency so this test file can run without the full
# project on sys.path during CI (falls back to inline formula if import fails).
try:
    from ai.zpd import compute_zpd_utility as _real_gaussian
except ImportError:
    # Inline reference implementation matching zpd.py exactly
    def _real_gaussian(sq, mu=0.5, sigma=0.2):  # type: ignore[override]
        return math.exp(-((sq - mu) ** 2) / (2 * sigma ** 2))

    # Inject stub module so plato.utils can import it
    _zpd_mod = types.ModuleType("ai.zpd")
    _zpd_mod.compute_zpd_utility = _real_gaussian
    _ai_mod = types.ModuleType("ai")
    sys.modules.setdefault("ai", _ai_mod)
    sys.modules.setdefault("ai.zpd", _zpd_mod)

from plato.utils import (
    content_hash,
    extract_json,
    format_training_input,
    gaussian_utility,
    validate_candidate,
)
from plato.schemas import TrainingExample


# ===========================================================================
# Gaussian utility scoring
# ===========================================================================

class TestGaussianUtility:
    """Paper Eq. 6: U(q') = exp(-((sq - μ)² / (2σ²)))"""

    def test_peak_at_mu(self):
        """Maximum utility (1.0) is achieved exactly at sq == mu."""
        u = gaussian_utility(0.5, mu=0.5, sigma=0.2)
        assert abs(u - 1.0) < 1e-9

    def test_symmetric_around_mu(self):
        """Utility is symmetric: U(mu + d) == U(mu - d)."""
        for d in (0.1, 0.2, 0.3):
            u_above = gaussian_utility(0.5 + d)
            u_below = gaussian_utility(0.5 - d)
            assert abs(u_above - u_below) < 1e-9, f"Asymmetry at d={d}"

    def test_utility_decays_with_distance(self):
        """Utility decreases as sq moves away from mu."""
        u_close = gaussian_utility(0.5)
        u_far   = gaussian_utility(0.9)
        assert u_close > u_far

    def test_extremes_have_low_utility(self):
        """sq == 0.0 and sq == 1.0 both produce low utility."""
        u_zero = gaussian_utility(0.0)
        u_one  = gaussian_utility(1.0)
        assert u_zero < 0.5
        assert u_one  < 0.5

    def test_matches_zpd_formula(self):
        """Must delegate to zpd.compute_zpd_utility, not duplicate."""
        for sq in (0.0, 0.25, 0.5, 0.75, 1.0):
            assert abs(gaussian_utility(sq) - _real_gaussian(sq)) < 1e-12, (
                f"Mismatch at sq={sq}"
            )

    def test_custom_mu_sigma(self):
        """Custom μ and σ shift the peak correctly."""
        u = gaussian_utility(0.8, mu=0.8, sigma=0.15)
        assert abs(u - 1.0) < 1e-9

    def test_range_always_zero_to_one(self):
        """Utility is always in (0, 1]."""
        for sq in [i / 20 for i in range(21)]:
            u = gaussian_utility(sq)
            assert 0.0 < u <= 1.0, f"Out of range at sq={sq}: {u}"


# ===========================================================================
# WSFT input formatting
# ===========================================================================

class TestFormatTrainingInput:
    def test_contains_all_fields(self):
        text = format_training_input(
            original_statement="Write a function to reverse a list.",
            failure_mode="off_by_one",
            root_cause="Student does not account for empty list edge case.",
        )
        assert "Write a function to reverse a list." in text
        assert "off_by_one" in text
        assert "Student does not account for empty list edge case." in text

    def test_section_headers_present(self):
        text = format_training_input("prob", "fail", "cause")
        assert "### Input" in text
        assert "### Output" in text

    def test_strips_surrounding_whitespace(self):
        """Leading/trailing whitespace in arguments should be stripped."""
        text = format_training_input(
            "  problem stmt  ",
            "  fail mode  ",
            "  root cause  ",
        )
        assert "  problem stmt  " not in text
        assert "problem stmt" in text


# ===========================================================================
# JSON extraction from Ollama output
# ===========================================================================

class TestExtractJson:
    def test_clean_json_object(self):
        raw = '{"title": "Test", "difficulty": 0.5}'
        result = extract_json(raw)
        assert result == {"title": "Test", "difficulty": 0.5}

    def test_think_tag_stripped(self):
        raw = "<think>Some reasoning here</think>\n{\"key\": 42}"
        result = extract_json(raw)
        assert result == {"key": 42}

    def test_code_fence_stripped(self):
        raw = '```json\n{"a": 1}\n```'
        result = extract_json(raw)
        assert result == {"a": 1}

    def test_prose_before_json(self):
        raw = 'Here is the JSON:\n{"x": "y"}'
        result = extract_json(raw)
        assert result == {"x": "y"}

    def test_empty_string_returns_none(self):
        assert extract_json("") is None

    def test_no_json_object_returns_none(self):
        assert extract_json("This is just plain text.") is None

    def test_malformed_json_returns_none(self):
        assert extract_json('{"broken": }') is None

    def test_nested_object_extracted(self):
        raw = '{"outer": {"inner": 1}}'
        result = extract_json(raw)
        assert result["outer"]["inner"] == 1


# ===========================================================================
# Candidate problem validation
# ===========================================================================

class TestValidateCandidate:
    def _valid(self) -> dict:
        return {
            "title": "Reverse a List",
            "statement": "Write a function that reverses the elements of a given list in Python.",
            "difficulty": 0.4,
            "visible_tests": [{"input": "[1,2,3]", "expected": "[3,2,1]"}],
            "hidden_tests": [],
        }

    def test_valid_candidate_passes(self):
        ok, reason = validate_candidate(self._valid())
        assert ok
        assert reason == ""

    def test_missing_title_fails(self):
        d = self._valid()
        del d["title"]
        ok, reason = validate_candidate(d)
        assert not ok
        assert "title" in reason

    def test_missing_statement_fails(self):
        d = self._valid()
        del d["statement"]
        ok, reason = validate_candidate(d)
        assert not ok

    def test_short_statement_fails(self):
        d = self._valid()
        d["statement"] = "Short."   # < 20 chars
        ok, reason = validate_candidate(d)
        assert not ok
        assert "statement" in reason

    def test_difficulty_out_of_range_fails(self):
        d = self._valid()
        d["difficulty"] = 1.5
        ok, reason = validate_candidate(d)
        assert not ok
        assert "difficulty" in reason

    def test_visible_tests_not_list_fails(self):
        d = self._valid()
        d["visible_tests"] = "not a list"
        ok, reason = validate_candidate(d)
        assert not ok
        assert "visible_tests" in reason

    def test_empty_title_fails(self):
        d = self._valid()
        d["title"] = "   "
        ok, reason = validate_candidate(d)
        assert not ok

    def test_difficulty_at_boundaries_passes(self):
        d = self._valid()
        d["difficulty"] = 0.0
        ok, _ = validate_candidate(d)
        assert ok
        d["difficulty"] = 1.0
        ok, _ = validate_candidate(d)
        assert ok


# ===========================================================================
# Content hash fingerprinting
# ===========================================================================

class TestContentHash:
    def test_same_statement_same_hash(self):
        h1 = content_hash("Write a function to reverse a list.")
        h2 = content_hash("Write a function to reverse a list.")
        assert h1 == h2

    def test_case_insensitive(self):
        h1 = content_hash("REVERSE A LIST")
        h2 = content_hash("reverse a list")
        assert h1 == h2

    def test_whitespace_normalised(self):
        h1 = content_hash("reverse  a   list")
        h2 = content_hash("reverse a list")
        assert h1 == h2

    def test_different_statements_different_hash(self):
        h1 = content_hash("Problem A")
        h2 = content_hash("Problem B")
        assert h1 != h2

    def test_returns_64_char_hex(self):
        h = content_hash("any statement")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ===========================================================================
# TrainingExample schema validation (malformed JSON rejection)
# ===========================================================================

class TestTrainingExampleSchema:
    def _valid_example(self) -> dict:
        return {
            "source_id": str(uuid.uuid4()),
            "input_text": "### Input\nOriginal problem: foo\nStudent failure mode: bar\nRoot cause: baz\n\n### Output\n",
            "output_text": json.dumps({"title": "T", "statement": "S", "difficulty": 0.5}),
            "weight": 0.75,
        }

    def test_valid_example_passes(self):
        ex = TrainingExample(**self._valid_example())
        assert ex.weight == 0.75

    def test_malformed_output_json_raises(self):
        data = self._valid_example()
        data["output_text"] = "this is not JSON"
        with pytest.raises(Exception):  # pydantic.ValidationError
            TrainingExample(**data)

    def test_weight_below_zero_raises(self):
        data = self._valid_example()
        data["weight"] = -0.1
        with pytest.raises(Exception):
            TrainingExample(**data)

    def test_weight_above_one_raises(self):
        data = self._valid_example()
        data["weight"] = 1.1
        with pytest.raises(Exception):
            TrainingExample(**data)

    def test_weight_at_boundary_passes(self):
        for w in (0.0, 1.0):
            data = self._valid_example()
            data["weight"] = w
            ex = TrainingExample(**data)
            assert ex.weight == w


# ===========================================================================
# Utility threshold filtering simulation
# ===========================================================================

class TestUtilityFiltering:
    """Simulate the training/insertion filtering logic."""

    def _make_log(self, utility: float) -> MagicMock:
        log = MagicMock()
        log.utility_score = utility
        return log

    def test_training_filter_threshold(self):
        """Only logs with utility >= 0.3 pass the training dataset filter."""
        MIN = 0.3
        logs = [self._make_log(u) for u in (0.1, 0.3, 0.5, 0.8, 0.29, 0.31)]
        passing = [l for l in logs if l.utility_score >= MIN]
        utilities = [l.utility_score for l in passing]
        assert all(u >= MIN for u in utilities)
        assert len(passing) == 4  # 0.3, 0.5, 0.8, 0.31

    def test_insertion_filter_threshold(self):
        """Only candidates with utility >= 0.6 are inserted into the problem bank."""
        MIN_INSERT = 0.6
        candidates = [0.55, 0.6, 0.7, 0.4, 0.61, 0.59]
        accepted = [u for u in candidates if u >= MIN_INSERT]
        assert accepted == [0.6, 0.7, 0.61]

    def test_gaussian_above_threshold_for_near_mu(self):
        """Candidates near μ=0.5 should naturally exceed the insertion threshold."""
        for sq in (0.4, 0.45, 0.5, 0.55, 0.6):
            u = gaussian_utility(sq)
            assert u >= 0.6, (
                f"Expected utility >= 0.6 for sq={sq} near mu=0.5, got {u:.4f}"
            )
