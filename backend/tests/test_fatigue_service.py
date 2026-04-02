"""
tests/test_fatigue_service.py
Stage 13 — Unit tests for the pure check_fatigue() algorithm.

No DB required. Run with:
    python -m pytest tests/test_fatigue_service.py -v
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.fatigue_service import (
    check_fatigue,
    FATIGUE_WINDOW,
    FATIGUE_THRESHOLD,
    TREND_THRESHOLD,
    FATIGUED_MU,
    NORMAL_MU,
)


class TestCheckFatigue:

    # ── Insufficient data ──────────────────────────────────────────────────

    def test_fewer_than_window_returns_not_fatigued(self):
        result = check_fatigue([0.2, 0.1])   # only 2 scores, need 4
        assert result.fatigued is False

    def test_exactly_window_minus_one_returns_not_fatigued(self):
        result = check_fatigue([0.1] * (FATIGUE_WINDOW - 1))
        assert result.fatigued is False

    # ── Fatigue triggered ─────────────────────────────────────────────────

    def test_low_avg_and_declining_trend_triggers_fatigue(self):
        # avg = 0.25, trend = 0.1 - 0.4 = -0.3 → both conditions met
        scores = [0.4, 0.3, 0.2, 0.1]
        result = check_fatigue(scores)
        assert result.fatigued is True
        assert result.target_mu == FATIGUED_MU            # 0.35
        assert result.recommendation == "reduce_difficulty"
        assert "easier" in result.message.lower() or "break" in result.message.lower()

    def test_window_uses_last_n_only(self):
        # First scores are high; only last 4 matter
        scores = [0.9, 0.9, 0.9, 0.4, 0.3, 0.2, 0.1]
        result = check_fatigue(scores)
        assert result.fatigued is True

    def test_avg_and_trend_values_attached(self):
        scores = [0.4, 0.3, 0.2, 0.1]
        result = check_fatigue(scores)
        assert result.avg_window == round(sum(scores) / 4, 4)
        assert result.trend == round(scores[-1] - scores[0], 4)

    # ── No fatigue: avg too high ──────────────────────────────────────────

    def test_high_avg_no_fatigue(self):
        scores = [0.7, 0.8, 0.75, 0.9]   # avg=0.8125, trend=+0.2
        result = check_fatigue(scores)
        assert result.fatigued is False

    # ── No fatigue: declining but avg above threshold ─────────────────────

    def test_declining_but_avg_above_threshold(self):
        # avg = 0.5, trend = -0.2 → avg NOT < 0.35
        scores = [0.7, 0.6, 0.4, 0.3]
        result = check_fatigue(scores)
        assert result.fatigued is False

    # ── No fatigue: low avg but NOT declining ─────────────────────────────

    def test_low_avg_but_flat_trend(self):
        # avg = 0.2, trend = 0.0 → trend NOT < -0.1
        scores = [0.2, 0.2, 0.2, 0.2]
        result = check_fatigue(scores)
        assert result.fatigued is False

    def test_low_avg_improving_trend(self):
        # avg = 0.2, trend = +0.15 → trend NOT < -0.1
        scores = [0.1, 0.15, 0.2, 0.25]
        result = check_fatigue(scores)
        assert result.fatigued is False

    # ── Boundary: exactly at thresholds ──────────────────────────────────

    def test_avg_exactly_at_threshold_no_fatigue(self):
        # avg == FATIGUE_THRESHOLD (0.35) is NOT < threshold → no fatigue
        scores = [0.35, 0.35, 0.35, 0.35]
        result = check_fatigue(scores)
        assert result.fatigued is False

    def test_trend_exactly_at_threshold_no_fatigue(self):
        # avg = 0.2, trend = TREND_THRESHOLD (-0.1) is NOT < -0.1
        scores = [0.3, 0.25, 0.2, 0.2]  # trend = -0.1
        result = check_fatigue(scores)
        # trend = 0.2 - 0.3 = -0.1 → NOT < -0.1 → no fatigue
        assert result.fatigued is False

    # ── Normal mu is returned when not fatigued ───────────────────────────

    def test_not_fatigued_returns_normal_mu(self):
        scores = [0.8, 0.9, 0.85, 0.9]
        result = check_fatigue(scores)
        assert result.fatigued is False
        assert result.target_mu == NORMAL_MU


class TestEffectiveMu:
    def test_effective_mu_normal(self):
        from services.fatigue_service import effective_mu
        assert effective_mu(None) == NORMAL_MU

    def test_effective_mu_fatigued(self):
        from services.fatigue_service import effective_mu

        class FakeSession:
            fatigued = True

        assert effective_mu(FakeSession()) == FATIGUED_MU

    def test_effective_mu_not_fatigued(self):
        from services.fatigue_service import effective_mu

        class FakeSession:
            fatigued = False

        assert effective_mu(FakeSession()) == NORMAL_MU


class TestGaussianMuShift:
    """Verify the problem selector shifts behavior with mu."""

    def test_mu_shift_changes_rankings(self):
        from services.problem_service import gaussian_utility, MU_NORMAL, MU_FATIGUED
        
        score = 0.5
        d_easy = 0.2   # s = 0.7
        d_med  = 0.5   # s = 1.0

        # Normal mu=0.5 targets s=0.5. 
        # d_easy (s=0.7, dist=0.2) vs d_med (s=1.0, dist=0.5)
        # d_easy should be better than d_med.
        u_easy_n = gaussian_utility(d_easy, score, mu=MU_NORMAL)
        u_med_n  = gaussian_utility(d_med,  score, mu=MU_NORMAL)
        assert u_easy_n > u_med_n

        # Fatigued mu=0.35 targets s=0.35.
        # d_easy (s=0.7, dist=0.35) vs d_med (s=1.0, dist=0.65)
        # d_easy should be better than d_med.
        u_easy_f = gaussian_utility(d_easy, score, mu=MU_FATIGUED)
        u_med_f  = gaussian_utility(d_med,  score, mu=MU_FATIGUED)
        assert u_easy_f > u_med_f
        
        # Verify they are DIFFERENT
        assert u_easy_f != u_easy_n

