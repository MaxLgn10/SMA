"""
Appointment scheduling rules for elective patients.

Each rule maps a slot to an appointment time, given context about the slot's
position within its session (for Bailey-Welch) or within a block (for Blocking).

All times are in minutes from t=0.

Rule definitions (from assignment):
  1 FCFS       : appointment_time = slot_start
  2 Bailey-Welch (K=2): first 2 patients of each session get session_start;
                        remaining get slot_start - SLOT_DURATION (15 min)
  3 Blocking (B=2): patients in pairs of consecutive slots share the start
                    of the first slot in the pair
  4 Benchmark (alpha=0.5): appointment_time = slot_start - alpha * sigma_elective
                            = slot_start - 1.5 min
"""
from __future__ import annotations

from enum import IntEnum


SLOT_DURATION = 15.0       # minutes per slot
K_BAILEY_WELCH = 2         # first K patients per session share session start
B_BLOCKING = 2             # block size (consecutive slots sharing start)
ALPHA_BENCHMARK = 0.5      # fraction of sigma
SIGMA_ELECTIVE = 3.0       # minutes, from distributions.ELECTIVE_SCAN_SIGMA


class AppointmentRule(IntEnum):
    FCFS = 1
    BAILEY_WELCH = 2
    BLOCKING = 3
    BENCHMARK = 4


def compute_appointment_time(
    rule: AppointmentRule,
    slot_abs_start: float,
    session_abs_start: float,
    slot_in_session: int,   # 0-indexed position within morning/afternoon session
) -> float:
    """
    Compute the appointment time for an elective patient given their assigned slot.

    Args:
        rule:              Which scheduling rule to apply.
        slot_abs_start:    Absolute start time of the slot (minutes).
        session_abs_start: Absolute start time of the session this slot belongs to.
        slot_in_session:   0-indexed position within the session (0–15).

    Returns:
        Appointment time in minutes from t=0.
    """
    if rule == AppointmentRule.FCFS:
        return slot_abs_start

    elif rule == AppointmentRule.BAILEY_WELCH:
        # First K patients of the session share session start; others get slot_start - 15
        if slot_in_session < K_BAILEY_WELCH:
            return session_abs_start
        return slot_abs_start - SLOT_DURATION

    elif rule == AppointmentRule.BLOCKING:
        # Pairs (0,1), (2,3), ... share the start of the first slot in the pair.
        # First slot of the pair is at position floor(slot_in_session / B) * B.
        pair_start_in_session = (slot_in_session // B_BLOCKING) * B_BLOCKING
        # Each slot within the session is SLOT_DURATION apart,
        # but sessions skip the lunch break implicitly (that's handled by slot_start_offset).
        # The offset of the pair's first slot from session start:
        pair_offset = pair_start_in_session * SLOT_DURATION
        return session_abs_start + pair_offset

    elif rule == AppointmentRule.BENCHMARK:
        return slot_abs_start - ALPHA_BENCHMARK * SIGMA_ELECTIVE

    else:
        raise ValueError(f"Unknown appointment rule: {rule}")
