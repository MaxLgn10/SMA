"""
SimulationEngine: discrete-event simulation of the outpatient radiology department.

Uses SimPy (process-based DES).  One replication = warmup_weeks + sim_weeks
simulated weeks.  Data is collected only after warmup_cutoff.

Architecture:
  - Two generator processes run in parallel:
      1. generate_elective_calls  – Mon–Fri 08:00–17:00, Poisson(λ_e)
      2. generate_urgent_arrivals – Mon–Sat opening hours, Poisson(λ_u)
  - Each patient is a separate SimPy process that:
      a. Waits until its appointment/slot time
      b. Requests the single scanner (simpy.Resource)
      c. Holds the resource for the scan duration
  - Overtime is computed after env.run() by comparing per-day last scan_end
    to the official day closing time.

Common Random Numbers (CRN):
  All randomness flows through RandomStreamManager, which is seeded from a
  base seed that is the same for every configuration in a given replication.
"""
from __future__ import annotations

import itertools
from collections import defaultdict
from typing import Dict, List, Tuple

import simpy

from src.appointment_rules import AppointmentRule, compute_appointment_time
from src.distributions import (
    elective_call_interarrival,
    elective_scan_duration,
    is_no_show,
    tardiness,
    urgent_interarrival,
    urgent_scan_duration,
)
from src.patient import ElectivePatient, UrgentPatient
from src.performance import PerformanceCollector, ReplicationResult
from src.random_streams import RandomStreamManager
from src.schedule_builder import (
    DAY_SLOTS,
    HALF_DAYS,
    WEEK_MINUTES,
    ScheduleBuilder,
    SlotType,
    slot_start_offset,
)

# Minutes from day-open (08:00) to start and end of lunch on full days
_LUNCH_START = 240.0   # 12:00
_LUNCH_END   = 300.0   # 13:00


class _RadiologyDept:
    """
    Internal SimPy model of the outpatient radiology department.
    Not intended to be used directly – use run_replication() instead.
    """

    def __init__(
        self,
        env: simpy.Environment,
        schedule_pattern: Dict[int, List[SlotType]],
        rule: AppointmentRule,
        rng: RandomStreamManager,
        collector: PerformanceCollector,
        total_weeks: int,
    ):
        self.env = env
        self.scanner = simpy.Resource(env, capacity=1)
        self.schedule_pattern = schedule_pattern
        self.rule = rule
        self.rng = rng
        self.collector = collector
        self.total_weeks = total_weeks

        # Pre-build per-week elective slot list: [(week, day, slot_idx), ...]
        # consumed FIFO as patients call in
        self._elective_slot_queue: List[Tuple[int, int, int]] = []
        for w in range(total_weeks):
            for day in range(6):
                for idx, stype in enumerate(schedule_pattern[day]):
                    if stype == SlotType.ELECTIVE:
                        self._elective_slot_queue.append((w, day, idx))
        self._slot_ptr = 0  # next elective slot to assign

        self._patient_id = itertools.count(1)

        # Day tracking for overtime: (week, day) -> max scan_end seen so far
        self._day_max_end: Dict[Tuple[int, int], float] = defaultdict(float)

    # ------------------------------------------------------------------
    # Lunch-break guard
    # ------------------------------------------------------------------

    def _next_scan_start(self, t: float) -> float:
        """Earliest time a scan can start on or after t.

        On full days, the window [12:00, 13:00) is blocked: a patient who
        acquires the scanner during lunch must wait until 13:00.
        Half-day lunch is not an issue (department closes at 12:00).
        """
        t_in_week = t % WEEK_MINUTES
        day = int(t_in_week // 1440)
        t_in_day = t_in_week - day * 1440   # minutes since this day's 08:00
        if day not in HALF_DAYS and _LUNCH_START <= t_in_day < _LUNCH_END:
            week = int(t // WEEK_MINUTES)
            return week * WEEK_MINUTES + day * 1440 + _LUNCH_END
        return t

    # ------------------------------------------------------------------
    # Elective call generator
    # ------------------------------------------------------------------

    def generate_elective_calls(self):
        """Poisson arrival process for elective patient calls, weekdays 08:00–17:00."""
        rng = self.rng.get("elective_arrival")

        for week in range(self.total_weeks):
            for day in range(5):  # Mon=0 … Fri=4 (no calls on Sat/Sun)
                window_start = week * WEEK_MINUTES + day * 1440
                window_end = window_start + 540.0  # 9 hours = 540 min

                # advance to the start of the calling window
                if window_start > self.env.now:
                    yield self.env.timeout(window_start - self.env.now)

                # generate calls within window as Poisson process
                while True:
                    iat = elective_call_interarrival(rng)
                    if self.env.now + iat >= window_end:
                        break
                    yield self.env.timeout(iat)
                    self._book_elective_patient()

    def _book_elective_patient(self):
        """Assign the next available FUTURE elective slot to a patient calling right now."""
        # Advance past slots that have already started (abs_start < call_time)
        while self._slot_ptr < len(self._elective_slot_queue):
            w, d, ix = self._elective_slot_queue[self._slot_ptr]
            if w * WEEK_MINUTES + d * 1440 + slot_start_offset(ix) >= self.env.now:
                break
            self._slot_ptr += 1

        if self._slot_ptr >= len(self._elective_slot_queue):
            return

        week, day, idx = self._elective_slot_queue[self._slot_ptr]
        self._slot_ptr += 1

        abs_start = week * WEEK_MINUTES + day * 1440 + slot_start_offset(idx)
        session = 0 if idx < 16 else 1
        session_offset = 0.0 if session == 0 else 300.0
        session_abs_start = week * WEEK_MINUTES + day * 1440 + session_offset
        slot_in_session = idx if idx < 16 else idx - 16

        appt_time = compute_appointment_time(
            self.rule, abs_start, session_abs_start, slot_in_session
        )

        rng_scan = self.rng.get("elective_scan")
        rng_tard = self.rng.get("tardiness")
        rng_ns = self.rng.get("no_show")

        patient = ElectivePatient(
            patient_id=next(self._patient_id),
            call_time=self.env.now,
            appointment_time=appt_time,
            slot_abs_start=abs_start,
            slot_day=day,
            slot_idx=idx,
            slot_week=week,
            tardiness_min=tardiness(rng_tard),
            no_show=is_no_show(rng_ns),
            scan_duration=elective_scan_duration(rng_scan),
        )
        patient.actual_arrival = patient.appointment_time + patient.tardiness_min

        self.env.process(self._elective_process(patient))

    def _elective_process(self, patient: ElectivePatient):
        """SimPy process for a single elective patient."""
        delay = patient.actual_arrival - self.env.now
        if delay > 0:
            yield self.env.timeout(delay)

        if patient.no_show:
            # Slot is idle; still record for AWT (no_show patients excluded in collector)
            self.collector.record_elective(patient)
            return

        with self.scanner.request() as req:
            yield req
            lunch_wait = self._next_scan_start(self.env.now) - self.env.now
            if lunch_wait > 0:
                yield self.env.timeout(lunch_wait)
            patient.scan_start = self.env.now
            yield self.env.timeout(patient.scan_duration)
            patient.scan_end = self.env.now

        self.collector.record_elective(patient)
        # Update day-level max scan end for overtime
        key = (patient.slot_week, patient.slot_day)
        if patient.scan_end > self._day_max_end[key]:
            self._day_max_end[key] = patient.scan_end

    # ------------------------------------------------------------------
    # Urgent arrival generator
    # ------------------------------------------------------------------

    def generate_urgent_arrivals(self):
        """
        Poisson arrival process for urgent patients during opening hours.
        Full days: two blocks (08:00–12:00 and 13:00–17:00), no arrivals during lunch.
        Half days: one block (08:00–12:00).
        """
        rng = self.rng.get("urgent_arrival")

        for week in range(self.total_weeks):
            # Build the urgent slot availability list per day for this week
            day_urgent_slots: Dict[int, List[float]] = {}
            for day in range(6):
                slots: List[float] = []
                for idx, stype in enumerate(self.schedule_pattern[day]):
                    if stype == SlotType.URGENT:
                        abs_s = week * WEEK_MINUTES + day * 1440 + slot_start_offset(idx)
                        slots.append(abs_s)
                day_urgent_slots[day] = sorted(slots)

            for day in range(6):
                is_half = day in HALF_DAYS
                day_base = week * WEEK_MINUTES + day * 1440
                day_close = day_base + (240.0 if is_half else 540.0)

                # Time blocks during which urgent patients can arrive
                # Morning: [day_base, day_base+240], Afternoon (full only): [day_base+300, day_base+540]
                blocks = [(day_base, day_base + 240.0)]
                if not is_half:
                    blocks.append((day_base + 300.0, day_base + 540.0))

                slot_pool = day_urgent_slots[day]

                for block_start, block_end in blocks:
                    if block_start > self.env.now:
                        yield self.env.timeout(block_start - self.env.now)

                    while True:
                        iat = urgent_interarrival(rng, is_half)
                        if self.env.now + iat >= block_end:
                            break
                        yield self.env.timeout(iat)
                        self._handle_urgent_arrival(week, day, day_close, slot_pool)

    def _handle_urgent_arrival(
        self,
        week: int,
        day: int,
        day_close: float,
        slot_pool: List[float],
    ):
        """Assign next urgent slot (or overtime) and start patient process."""
        rng_scan = self.rng.get("urgent_scan")

        # Find next available urgent slot >= current time
        assigned_start: float = day_close  # default: overtime
        is_overtime = True
        for i, abs_s in enumerate(slot_pool):
            if abs_s >= self.env.now:
                assigned_start = abs_s
                slot_pool.pop(i)
                is_overtime = False
                break

        patient = UrgentPatient(
            patient_id=next(self._patient_id),
            arrival_time=self.env.now,
            arrival_day=day,
            arrival_week=week,
            scan_duration=urgent_scan_duration(rng_scan),
            is_overtime=is_overtime,
        )

        self.env.process(self._urgent_process(patient, assigned_start))

    def _urgent_process(self, patient: UrgentPatient, assigned_start: float):
        """SimPy process for a single urgent patient."""
        delay = assigned_start - self.env.now
        if delay > 0:
            yield self.env.timeout(delay)

        with self.scanner.request() as req:
            yield req
            lunch_wait = self._next_scan_start(self.env.now) - self.env.now
            if lunch_wait > 0:
                yield self.env.timeout(lunch_wait)
            patient.scan_start = self.env.now
            yield self.env.timeout(patient.scan_duration)
            patient.scan_end = self.env.now

        self.collector.record_urgent(patient)
        key = (patient.arrival_week, patient.arrival_day)
        if patient.scan_end > self._day_max_end[key]:
            self._day_max_end[key] = patient.scan_end

    # ------------------------------------------------------------------
    # Post-run overtime finalisation
    # ------------------------------------------------------------------

    def finalise_overtime(self):
        """
        After env.run() completes, compute and record per-day overtime.
        Must be called before collector.build_result().
        """
        for week in range(self.total_weeks):
            for day in range(6):
                is_half = day in HALF_DAYS
                day_base = week * WEEK_MINUTES + day * 1440
                day_close = day_base + (240.0 if is_half else 540.0)
                last_end = self._day_max_end.get((week, day), day_close)
                overtime = max(0.0, last_end - day_close)
                self.collector.record_overtime(week, day, overtime)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def run_replication(
    n_urgent: int,
    strategy: int,
    rule: int,
    seed: int,
    warmup_weeks: int = 8,
    sim_weeks: int = 52,
) -> ReplicationResult:
    """
    Run one replication of the radiology simulation.

    Args:
        n_urgent:     Number of urgent slots per week (10-20).
        strategy:     Urgent slot timing strategy (1, 2, or 3).
        rule:         Appointment scheduling rule (1-4).
        seed:         Base random seed (same across all configs for CRN).
        warmup_weeks: Number of weeks to discard as warm-up.
        sim_weeks:    Number of weeks to collect data for.

    Returns:
        ReplicationResult with per-patient and per-week KPIs.
    """
    # ── input assertions ──────────────────────────────────────────────────────
    assert n_urgent in range(10, 21), f"n_urgent must be in [10, 20], got {n_urgent}"
    assert strategy in (1, 2, 3), f"strategy must be 1, 2, or 3, got {strategy}"
    assert rule in (1, 2, 3, 4), f"rule must be in [1, 4], got {rule}"

    total_weeks = warmup_weeks + sim_weeks
    schedule_pattern = ScheduleBuilder().build(n_urgent, strategy)

    # ── schedule assertions ───────────────────────────────────────────────────
    for day, slots in schedule_pattern.items():
        n_urgent_day = sum(1 for s in slots if s == SlotType.URGENT)
        n_elective_day = sum(1 for s in slots if s == SlotType.ELECTIVE)
        assert len(slots) == DAY_SLOTS[day], (
            f"Day {day}: expected {DAY_SLOTS[day]} slots, got {len(slots)}"
        )
        assert n_urgent_day + n_elective_day == DAY_SLOTS[day], (
            f"Day {day}: urgent + elective slots must equal {DAY_SLOTS[day]}"
        )
    total_urgent_per_week = sum(
        sum(1 for s in slots if s == SlotType.URGENT)
        for slots in schedule_pattern.values()
    )
    assert total_urgent_per_week == n_urgent, (
        f"Weekly urgent slots mismatch: requested {n_urgent}, built {total_urgent_per_week}"
    )
    total_per_week = sum(len(slots) for slots in schedule_pattern.values())
    assert total_per_week == 160, (
        f"Total weekly slots must be 160, got {total_per_week}"
    )

    appt_rule = AppointmentRule(rule)
    rng = RandomStreamManager(seed)
    warmup_cutoff = warmup_weeks * WEEK_MINUTES
    collector = PerformanceCollector(warmup_cutoff)

    env = simpy.Environment()
    dept = _RadiologyDept(env, schedule_pattern, appt_rule, rng, collector, total_weeks)

    env.process(dept.generate_elective_calls())
    env.process(dept.generate_urgent_arrivals())

    env.run(until=total_weeks * WEEK_MINUTES)

    dept.finalise_overtime()
    result = collector.build_result()

    # ── output assertion: W uses hours for both components ────────────────────
    # W = (1/168)*awt_e_hours + (1/9)*(swt_u_min/60)
    # Both terms are dimensionless and bounded [0, 1] under normal operation.
    # Flag if either component exceeds 2.0 (clearly unstable / data error).
    if result.mean_awt_e > 0 or result.mean_swt_u > 0:
        w_awt = result.mean_awt_e / 168.0
        w_swt = (result.mean_swt_u / 60.0) / 9.0
        assert abs(result.objective - (w_awt + w_swt)) < 1e-6, (
            f"W computation mismatch: objective={result.objective:.6f}, "
            f"(awt/168 + swt_u/60/9)={w_awt + w_swt:.6f}"
        )

    return result
