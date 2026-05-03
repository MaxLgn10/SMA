"""Tests for probability distributions: ranges, moments, reproducibility."""
import numpy as np
import pytest
from src.distributions import (
    elective_scan_duration,
    urgent_scan_duration,
    elective_call_interarrival,
    urgent_interarrival,
    tardiness,
    is_no_show,
    ELECTIVE_SCAN_MU,
    ELECTIVE_SCAN_SIGMA,
    NO_SHOW_PROB,
    URGENT_SCAN_TYPES,
)

N_SAMPLES = 10_000
RNG = np.random.default_rng(42)


def _fresh_rng():
    return np.random.default_rng(123)


# ---- Elective scan duration ----

def test_elective_scan_nonnegative():
    rng = _fresh_rng()
    samples = [elective_scan_duration(rng) for _ in range(N_SAMPLES)]
    assert all(s >= 0 for s in samples)


def test_elective_scan_mean_approx():
    rng = _fresh_rng()
    samples = [elective_scan_duration(rng) for _ in range(N_SAMPLES)]
    mean = np.mean(samples)
    # Truncated normal from 0; with mu=15, sigma=3 and left-tail cut at 0,
    # the truncated mean is slightly above 15 but very close.
    assert abs(mean - ELECTIVE_SCAN_MU) < 0.5, f"Mean too far from {ELECTIVE_SCAN_MU}: {mean:.3f}"


# ---- Urgent scan duration ----

def test_urgent_scan_nonnegative():
    rng = _fresh_rng()
    samples = [urgent_scan_duration(rng) for _ in range(N_SAMPLES)]
    assert all(s >= 0 for s in samples)


def test_urgent_scan_mean_range():
    rng = _fresh_rng()
    samples = [urgent_scan_duration(rng) for _ in range(N_SAMPLES)]
    mean = np.mean(samples)
    # Weighted mean: 0.7*15 + 0.1*17.5 + 0.1*22.5 + 0.05*30 + 0.05*30 = 17.5
    expected_mean = sum(freq * mu for _, freq, mu, _ in URGENT_SCAN_TYPES)
    assert abs(mean - expected_mean) < 0.5, f"Mean {mean:.3f} far from expected {expected_mean}"


# ---- Interarrival times ----

def test_elective_call_iat_positive():
    rng = _fresh_rng()
    samples = [elective_call_interarrival(rng) for _ in range(N_SAMPLES)]
    assert all(s > 0 for s in samples)


def test_elective_call_iat_mean():
    rng = _fresh_rng()
    samples = [elective_call_interarrival(rng) for _ in range(N_SAMPLES)]
    # mean IAT = window / lambda = 540 / 28.345 ≈ 19.05 min
    expected = 540.0 / 28.345
    assert abs(np.mean(samples) - expected) < 0.5


def test_urgent_iat_full_day_mean():
    rng = _fresh_rng()
    samples = [urgent_interarrival(rng, is_half_day=False) for _ in range(N_SAMPLES)]
    expected = 480.0 / 2.5  # 192 min mean IAT for full day
    # Exponential has high variance: SE ≈ 192/sqrt(10000) ≈ 1.92; allow 4× SE
    assert abs(np.mean(samples) - expected) < 8.0


def test_urgent_iat_half_day_mean():
    rng = _fresh_rng()
    samples = [urgent_interarrival(rng, is_half_day=True) for _ in range(N_SAMPLES)]
    expected = 240.0 / 1.25  # 192 min mean IAT for half day (same rate)
    assert abs(np.mean(samples) - expected) < 8.0


def test_urgent_iat_same_rate_full_and_half():
    """Rate per open minute should be equal for full and half days."""
    rng1 = np.random.default_rng(99)
    rng2 = np.random.default_rng(99)
    mean_full = np.mean([urgent_interarrival(rng1, False) for _ in range(N_SAMPLES)])
    mean_half = np.mean([urgent_interarrival(rng2, True) for _ in range(N_SAMPLES)])
    assert abs(mean_full - mean_half) < 2.0


# ---- Tardiness ----

def test_tardiness_can_be_negative():
    rng = _fresh_rng()
    samples = [tardiness(rng) for _ in range(N_SAMPLES)]
    assert any(s < 0 for s in samples), "Tardiness should be able to be negative (early arrivals)"


def test_tardiness_mean_near_zero():
    rng = _fresh_rng()
    samples = [tardiness(rng) for _ in range(N_SAMPLES)]
    assert abs(np.mean(samples)) < 0.2, f"Tardiness mean too far from 0: {np.mean(samples):.3f}"


def test_tardiness_std_approx():
    rng = _fresh_rng()
    samples = [tardiness(rng) for _ in range(N_SAMPLES)]
    assert abs(np.std(samples) - 2.5) < 0.1


# ---- No-show ----

def test_no_show_rate():
    rng = _fresh_rng()
    outcomes = [is_no_show(rng) for _ in range(N_SAMPLES)]
    rate = sum(outcomes) / N_SAMPLES
    assert abs(rate - NO_SHOW_PROB) < 0.005, f"No-show rate {rate:.4f} far from {NO_SHOW_PROB}"


# ---- Reproducibility (same seed → same output) ----

def test_elective_scan_reproducible():
    rng1 = np.random.default_rng(777)
    rng2 = np.random.default_rng(777)
    s1 = [elective_scan_duration(rng1) for _ in range(100)]
    s2 = [elective_scan_duration(rng2) for _ in range(100)]
    assert s1 == s2
