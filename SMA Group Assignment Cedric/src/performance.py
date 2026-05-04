"""
PerformanceCollector: accumulates per-patient records and computes KPIs.

KPIs tracked per simulation run:
  AWT_e : average appointment waiting time for elective patients (hours)
  SWT_e : average scan waiting time for elective patients (minutes)
  SWT_u : average scan waiting time for urgent patients (minutes)
  OT    : average daily overtime (minutes per open day)

Objective function (from assignment):
  W = w_e * AWT_e_hours + w_u * SWT_u_hours
  where w_e = 1/168, w_u = 1/9
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict

import numpy as np

from src.patient import ElectivePatient, UrgentPatient

W_ELECTIVE = 1.0 / 168.0   # weight; AWT_e in hours, max ≈ 168 h = 1 week
W_URGENT = 1.0 / 9.0       # weight; SWT_u in hours, max = 9 h = 1 day


@dataclass
class WeeklyStats:
    """Aggregate KPIs for a single simulated week (post warm-up)."""
    week: int
    awt_e_hours: float    # mean appointment wait (hours)
    swt_e_min: float      # mean scan wait elective (minutes)
    swt_u_min: float      # mean scan wait urgent (minutes)
    overtime_min: float   # mean overtime per open day (minutes)
    n_elective: int
    n_urgent: int

    @property
    def objective(self) -> float:
        return W_ELECTIVE * self.awt_e_hours + W_URGENT * (self.swt_u_min / 60.0)


@dataclass
class ReplicationResult:
    """All KPI data from one complete replication."""
    weekly: List[WeeklyStats] = field(default_factory=list)
    # Raw records for post-hoc analysis
    elective_awt: List[float] = field(default_factory=list)    # hours
    elective_swt: List[float] = field(default_factory=list)    # minutes
    urgent_swt: List[float] = field(default_factory=list)      # minutes
    overtime_per_day: List[float] = field(default_factory=list)  # minutes

    @property
    def mean_awt_e(self) -> float:
        return float(np.mean(self.elective_awt)) if self.elective_awt else 0.0

    @property
    def mean_swt_e(self) -> float:
        return float(np.mean(self.elective_swt)) if self.elective_swt else 0.0

    @property
    def mean_swt_u(self) -> float:
        return float(np.mean(self.urgent_swt)) if self.urgent_swt else 0.0

    @property
    def mean_overtime(self) -> float:
        return float(np.mean(self.overtime_per_day)) if self.overtime_per_day else 0.0

    @property
    def objective(self) -> float:
        return W_ELECTIVE * self.mean_awt_e + W_URGENT * (self.mean_swt_u / 60.0)


class PerformanceCollector:
    """
    Collects patient-level outcomes and daily overtime during a simulation run.
    Warm-up data is ignored: only records after warm-up_cutoff_time are kept.
    """

    def __init__(self, warmup_cutoff: float):
        """
        Args:
            warmup_cutoff: Simulation time (minutes) after which data collection starts.
        """
        self.warmup_cutoff = warmup_cutoff
        self._elective: List[ElectivePatient] = []
        self._urgent: List[UrgentPatient] = []
        self._overtime: List[float] = []       # one entry per open day post-warmup
        self._weekly_elective: Dict[int, List[ElectivePatient]] = {}
        self._weekly_urgent: Dict[int, List[UrgentPatient]] = {}
        self._weekly_overtime: Dict[int, List[float]] = {}

    def record_elective(self, patient: ElectivePatient) -> None:
        if patient.scan_end >= self.warmup_cutoff and not patient.no_show:
            self._elective.append(patient)
            week = patient.slot_week
            self._weekly_elective.setdefault(week, []).append(patient)

    def record_urgent(self, patient: UrgentPatient) -> None:
        if patient.scan_end >= self.warmup_cutoff:
            self._urgent.append(patient)
            week = patient.arrival_week
            self._weekly_urgent.setdefault(week, []).append(patient)

    def record_overtime(self, week: int, day: int, overtime_min: float) -> None:
        """Record overtime for one open day. week/day used for warm-up check."""
        from src.schedule_builder import WEEK_MINUTES
        day_base = week * WEEK_MINUTES + day * 1440
        if day_base >= self.warmup_cutoff:
            self._overtime.append(overtime_min)
            self._weekly_overtime.setdefault(week, []).append(overtime_min)

    def build_result(self) -> ReplicationResult:
        result = ReplicationResult()
        result.elective_awt = [p.appointment_wait_hours for p in self._elective]
        result.elective_swt = [p.scan_wait_minutes for p in self._elective]
        result.urgent_swt = [p.scan_wait_minutes for p in self._urgent]
        result.overtime_per_day = list(self._overtime)

        all_weeks = sorted(set(list(self._weekly_elective.keys()) +
                               list(self._weekly_urgent.keys()) +
                               list(self._weekly_overtime.keys())))
        for w in all_weeks:
            ep = self._weekly_elective.get(w, [])
            up = self._weekly_urgent.get(w, [])
            ot = self._weekly_overtime.get(w, [])
            awt_e = float(np.mean([p.appointment_wait_hours for p in ep])) if ep else 0.0
            swt_e = float(np.mean([p.scan_wait_minutes for p in ep])) if ep else 0.0
            swt_u = float(np.mean([p.scan_wait_minutes for p in up])) if up else 0.0
            ot_mean = float(np.mean(ot)) if ot else 0.0
            ws = WeeklyStats(
                week=w,
                awt_e_hours=awt_e,
                swt_e_min=swt_e,
                swt_u_min=swt_u,
                overtime_min=ot_mean,
                n_elective=len(ep),
                n_urgent=len(up),
            )
            result.weekly.append(ws)
        return result


def aggregate_replications(results: List[ReplicationResult]) -> Dict[str, Dict]:
    """
    Aggregate KPIs across replications, computing mean, std, and 95% CI.

    Returns dict with keys: awt_e, swt_e, swt_u, overtime, objective.
    Each value is a dict with keys: mean, std, ci_low, ci_high.
    """
    from scipy import stats

    awt_vals = [r.mean_awt_e for r in results]
    swt_e_vals = [r.mean_swt_e for r in results]
    swt_u_vals = [r.mean_swt_u for r in results]
    ot_vals = [r.mean_overtime for r in results]
    obj_vals = [r.objective for r in results]

    def _summarise(vals: List[float]) -> Dict:
        arr = np.array(vals)
        n = len(arr)
        mean = float(np.mean(arr))
        std = float(np.std(arr, ddof=1)) if n > 1 else 0.0
        if n > 1:
            t_crit = float(stats.t.ppf(0.975, df=n - 1))
            margin = t_crit * std / np.sqrt(n)
        else:
            margin = 0.0
        return {"mean": mean, "std": std, "ci_low": mean - margin, "ci_high": mean + margin, "n": n}

    return {
        "awt_e_hours": _summarise(awt_vals),
        "swt_e_min":   _summarise(swt_e_vals),
        "swt_u_min":   _summarise(swt_u_vals),
        "overtime_min": _summarise(ot_vals),
        "objective":   _summarise(obj_vals),
    }
