"""
Centralised probability distributions for the radiology simulation.

All distributions accept a numpy.random.Generator (rng) to support CRN.
Scan durations use truncated normal to prevent negative values.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import truncnorm

# ---- Elective scan parameters ----
ELECTIVE_SCAN_MU = 15.0   # minutes
ELECTIVE_SCAN_SIGMA = 3.0  # minutes

# ---- Urgent scan type mixture ----
# (name, frequency, mu_min, sigma_min)
URGENT_SCAN_TYPES = [
    ("Brain",           0.70, 15.0,  2.5),
    ("Spine_Lumbar",    0.10, 17.5,  1.0),
    ("Spine_Cervical",  0.10, 22.5,  2.5),
    ("Abdomen_MRCP",    0.05, 30.0,  1.0),
    ("Others",          0.05, 30.0,  4.5),
]
_URGENT_PROBS = np.array([t[1] for t in URGENT_SCAN_TYPES])
assert abs(_URGENT_PROBS.sum() - 1.0) < 1e-9

# ---- Arrival parameters ----
ELECTIVE_DAILY_LAMBDA = 28.345          # Poisson arrivals per weekday
ELECTIVE_CALL_WINDOW = (0.0, 540.0)    # minutes after 08:00 (08:00–17:00)

URGENT_LAMBDA_FULL = 2.5   # arrivals per full day (8h)
URGENT_LAMBDA_HALF = 1.25  # arrivals per half day (4h)
FULL_DAY_MINUTES = 480.0   # open minutes on a full day
HALF_DAY_MINUTES = 240.0   # open minutes on a half day

# ---- Tardiness parameters ----
TARDINESS_MU = 0.0
TARDINESS_SIGMA = 2.5  # minutes

# ---- No-show probability ----
NO_SHOW_PROB = 0.02


def elective_scan_duration(rng: np.random.Generator) -> float:
    """Truncated normal scan duration for elective patient (minutes, ≥ 0)."""
    a, b = (0 - ELECTIVE_SCAN_MU) / ELECTIVE_SCAN_SIGMA, np.inf
    return float(truncnorm.rvs(a, b, loc=ELECTIVE_SCAN_MU, scale=ELECTIVE_SCAN_SIGMA, random_state=rng))


def urgent_scan_duration(rng: np.random.Generator) -> float:
    """Discrete-mixture truncated normal for urgent patient scan (minutes, ≥ 0)."""
    type_idx = rng.choice(len(URGENT_SCAN_TYPES), p=_URGENT_PROBS)
    _, _, mu, sigma = URGENT_SCAN_TYPES[type_idx]
    a = (0 - mu) / sigma
    return float(truncnorm.rvs(a, np.inf, loc=mu, scale=sigma, random_state=rng))


def elective_call_interarrival(rng: np.random.Generator) -> float:
    """
    Exponential interarrival time (minutes) for elective patient calls within one day.
    Rate = ELECTIVE_DAILY_LAMBDA / ELECTIVE_CALL_WINDOW (arrivals per minute).
    """
    window = ELECTIVE_CALL_WINDOW[1] - ELECTIVE_CALL_WINDOW[0]
    rate = ELECTIVE_DAILY_LAMBDA / window  # arrivals per minute
    return float(rng.exponential(1.0 / rate))


def urgent_interarrival(rng: np.random.Generator, is_half_day: bool) -> float:
    """
    Exponential interarrival time (minutes) for urgent patients on a given day.
    Rate is the same per open minute for both full and half days.
    """
    lam = URGENT_LAMBDA_HALF if is_half_day else URGENT_LAMBDA_FULL
    mins = HALF_DAY_MINUTES if is_half_day else FULL_DAY_MINUTES
    rate = lam / mins  # per minute
    return float(rng.exponential(1.0 / rate))


def tardiness(rng: np.random.Generator) -> float:
    """
    Punctuality deviation from appointment time (minutes).
    N(0, 2.5) – can be negative (early) or positive (late).
    """
    return float(rng.normal(TARDINESS_MU, TARDINESS_SIGMA))


def is_no_show(rng: np.random.Generator) -> bool:
    """Return True with probability NO_SHOW_PROB."""
    return bool(rng.random() < NO_SHOW_PROB)
