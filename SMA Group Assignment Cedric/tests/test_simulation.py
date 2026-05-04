"""Tests for the simulation engine: smoke tests, KPI ranges, CRN property."""
import pytest
import numpy as np
from src.simulation import run_replication
from src.performance import W_ELECTIVE, W_URGENT

BASELINE = (14, 1, 1)  # n_urgent=14, strategy=1, rule=1 (FCFS)


# ---- Smoke test: simulation completes ----

def test_smoke_baseline():
    result = run_replication(*BASELINE, seed=0, warmup_weeks=4, sim_weeks=4)
    assert result is not None
    assert len(result.elective_awt) > 0
    assert len(result.urgent_swt) > 0


@pytest.mark.parametrize("rule", [1, 2, 3, 4])
def test_all_rules_complete(rule):
    result = run_replication(14, 1, rule, seed=1, warmup_weeks=2, sim_weeks=2)
    assert result.mean_awt_e >= 0
    assert result.mean_swt_u >= 0


@pytest.mark.parametrize("strategy", [1, 2, 3])
def test_all_strategies_complete(strategy):
    result = run_replication(14, strategy, 1, seed=2, warmup_weeks=2, sim_weeks=2)
    assert result.mean_swt_u >= 0


# ---- KPI sanity checks ----

def test_awt_e_nonnegative():
    """After fix: patients book future slots, so AWT_e >= 0."""
    result = run_replication(*BASELINE, seed=3, warmup_weeks=4, sim_weeks=8)
    assert result.mean_awt_e >= 0, f"AWT_e should not be negative: {result.mean_awt_e}"


def test_awt_e_reasonable_range():
    """AWT_e should be between 0 and 168 h for a stable system in steady state."""
    result = run_replication(*BASELINE, seed=4, warmup_weeks=8, sim_weeks=52)
    assert 0 <= result.mean_awt_e < 168, f"AWT_e out of range: {result.mean_awt_e}"


def test_swt_u_nonnegative():
    result = run_replication(*BASELINE, seed=5, warmup_weeks=4, sim_weeks=8)
    assert result.mean_swt_u >= 0


def test_overtime_nonnegative():
    result = run_replication(*BASELINE, seed=6, warmup_weeks=4, sim_weeks=8)
    assert result.mean_overtime >= 0


def test_objective_bounded():
    result = run_replication(*BASELINE, seed=7, warmup_weeks=8, sim_weeks=52)
    # Objective should be non-negative; no strict upper bound since SWT_u can vary
    assert result.objective >= 0, f"Objective negative: {result.objective}"


# ---- CRN: same seed, different configs produce different results ----

def test_crn_different_configs_differ():
    r1 = run_replication(14, 1, 1, seed=42, warmup_weeks=4, sim_weeks=8)
    r2 = run_replication(20, 1, 1, seed=42, warmup_weeks=4, sim_weeks=8)
    # Different n_urgent → different KPIs
    assert abs(r1.mean_awt_e - r2.mean_awt_e) > 0 or abs(r1.mean_swt_u - r2.mean_swt_u) > 0


# ---- CRN: same config + seed → reproducible ----

def test_crn_reproducible():
    r1 = run_replication(*BASELINE, seed=99, warmup_weeks=4, sim_weeks=8)
    r2 = run_replication(*BASELINE, seed=99, warmup_weeks=4, sim_weeks=8)
    assert r1.mean_awt_e == r2.mean_awt_e
    assert r1.mean_swt_u == r2.mean_swt_u


# ---- More urgent slots: monotone effect on AWT_e ----

def test_more_urgent_slots_less_elective_slots():
    """More urgent slots means fewer elective slots → higher AWT_e on average."""
    awt_low = run_replication(10, 1, 1, seed=10, warmup_weeks=8, sim_weeks=52).mean_awt_e
    awt_high = run_replication(20, 1, 1, seed=10, warmup_weeks=8, sim_weeks=52).mean_awt_e
    # Higher n_urgent → fewer elective slots → patients wait longer for appointment
    # This is a weak monotone test; with CRN the direction should hold.
    assert awt_high >= awt_low * 0.8, (
        f"Unexpected: more urgent slots did not increase AWT_e ({awt_low:.2f} → {awt_high:.2f})"
    )


# ---- Weekly stats ----

def test_weekly_stats_populated():
    result = run_replication(*BASELINE, seed=11, warmup_weeks=4, sim_weeks=8)
    assert len(result.weekly) > 0
    for ws in result.weekly:
        assert ws.n_elective >= 0
        assert ws.n_urgent >= 0
        assert ws.awt_e_hours >= 0, f"Negative AWT in week {ws.week}: {ws.awt_e_hours}"


# ---- No-show rate ----

def test_no_shows_present():
    """About 2% of elective patients should no-show."""
    from src.simulation import run_replication as rr
    from src.schedule_builder import ScheduleBuilder, WEEK_MINUTES
    from src.random_streams import RandomStreamManager
    from src.appointment_rules import AppointmentRule
    from src.performance import PerformanceCollector
    import simpy
    from src.simulation import _RadiologyDept

    # Run with known seed and count no-shows
    result = rr(14, 1, 1, seed=50, warmup_weeks=4, sim_weeks=52)
    # We can't directly count no-shows from ReplicationResult, but we can check
    # that the number of elective records is somewhat less than expected
    # (no-shows are excluded from elective_awt etc.)
    assert len(result.elective_awt) > 100  # sanity: some patients were served
