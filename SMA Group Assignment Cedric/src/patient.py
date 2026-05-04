"""
Patient dataclasses for elective and urgent patients.

All times are in minutes from simulation t=0 (Monday 08:00 of week 0).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ElectivePatient:
    patient_id: int

    # Set at call time
    call_time: float = 0.0           # when the patient called
    appointment_time: float = 0.0    # scheduled appointment time (from rule)
    slot_abs_start: float = 0.0      # absolute start of the assigned slot
    slot_day: int = 0
    slot_idx: int = 0                # slot index within day (0-indexed)
    slot_week: int = 0
    tardiness_min: float = 0.0       # N(0, 2.5) deviation added to appointment_time
    no_show: bool = False
    scan_duration: float = 0.0       # pre-drawn truncated normal

    # Set during simulation
    actual_arrival: float = 0.0      # appointment_time + tardiness_min (capped at day end)
    scan_start: float = 0.0
    scan_end: float = 0.0

    @property
    def appointment_wait_hours(self) -> float:
        """Time from call to scheduled appointment (hours). AWT_e metric."""
        return (self.appointment_time - self.call_time) / 60.0

    @property
    def scan_wait_minutes(self) -> float:
        """Time from actual arrival to scan start (minutes). SWT_e metric."""
        return max(0.0, self.scan_start - self.actual_arrival)

    @property
    def slot_week_day(self) -> int:
        """Day of week for the slot (0=Mon ... 5=Sat)."""
        return self.slot_day


@dataclass
class UrgentPatient:
    patient_id: int

    # Set at arrival time
    arrival_time: float = 0.0        # when the patient physically arrived
    arrival_day: int = 0
    arrival_week: int = 0
    scan_duration: float = 0.0       # pre-drawn from discrete-mixture truncnorm

    # Set during simulation
    scan_start: float = 0.0
    scan_end: float = 0.0
    is_overtime: bool = False        # True when served after official closing time

    @property
    def scan_wait_minutes(self) -> float:
        """Time from arrival to scan start (minutes). SWT_u metric."""
        return max(0.0, self.scan_start - self.arrival_time)

    @property
    def scan_wait_hours(self) -> float:
        return self.scan_wait_minutes / 60.0
