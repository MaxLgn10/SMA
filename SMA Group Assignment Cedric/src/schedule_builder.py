"""
ScheduleBuilder: generates the cyclic weekly slot schedule for all (n_urgent, strategy) combinations.

Week layout (time 0 = Monday 08:00):
  Day 0 Mon: 32 slots (morning 0-15, afternoon 16-31), full day closes 17:00
  Day 1 Tue: 32 slots, full day
  Day 2 Wed: 32 slots, full day
  Day 3 Thu: 16 slots (morning only 0-15), half day closes 12:00
  Day 4 Fri: 32 slots, full day
  Day 5 Sat: 16 slots (morning only), half day

Slot start offset from day base (= day * 1440, where 1440 = 24*60):
  slot i (0-indexed): i*15 min + (60 if i>=16 else 0)   [60 min = lunch break]
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Tuple


class SlotType(Enum):
    ELECTIVE = "E"
    URGENT = "U"


# Day index → total slots on that day
DAY_SLOTS: Dict[int, int] = {0: 32, 1: 32, 2: 32, 3: 16, 4: 32, 5: 16}
# Days that are half-days (morning only)
HALF_DAYS = frozenset({3, 5})
# Total slots per week
WEEK_TOTAL_SLOTS = sum(DAY_SLOTS.values())  # 160
# Week duration in minutes
WEEK_MINUTES = 7 * 24 * 60  # 10080


@dataclass(frozen=True)
class Slot:
    week: int
    day: int
    idx: int          # 0-indexed slot position within the day
    slot_type: SlotType

    @property
    def session(self) -> int:
        """0 = morning (slots 0-15), 1 = afternoon (slots 16-31)."""
        return 0 if self.idx < 16 else 1

    @property
    def slot_in_session(self) -> int:
        """Position within the morning or afternoon session (0-indexed)."""
        return self.idx if self.idx < 16 else self.idx - 16

    @property
    def abs_start(self) -> float:
        """Absolute start time in minutes from simulation t=0 (Monday 08:00 of week 0)."""
        return self.week * WEEK_MINUTES + self.day * 1440 + slot_start_offset(self.idx)

    @property
    def session_start(self) -> float:
        """Absolute start of the session this slot belongs to."""
        session_offset = 0 if self.session == 0 else 300  # afternoon starts 300 min after 08:00
        return self.week * WEEK_MINUTES + self.day * 1440 + session_offset


def slot_start_offset(idx: int) -> float:
    """Minutes from 08:00 (day base) to start of slot idx (0-indexed)."""
    return idx * 15 + (60 if idx >= 16 else 0)


def day_close_offset(day: int) -> float:
    """Minutes from 08:00 to closing time of the given day."""
    return 240.0 if day in HALF_DAYS else 540.0


def day_close_abs(week: int, day: int) -> float:
    return week * WEEK_MINUTES + day * 1440 + day_close_offset(day)


class ScheduleBuilder:
    """
    Generates the weekly slot assignment pattern for a given (n_urgent, strategy).

    The returned structure is a dict {day: List[SlotType]} valid for one week.
    The same pattern repeats cyclically each week.
    """

    def build(self, n_urgent: int, strategy: int) -> Dict[int, List[SlotType]]:
        """
        Build the weekly schedule.

        Args:
            n_urgent: number of urgent slots per week (10, 12, 14, 16, 18, 20)
            strategy: 1, 2, or 3

        Returns:
            {day: [SlotType, ...]} for days 0-5, length equals DAY_SLOTS[day]
        """
        if strategy == 1:
            return self._strategy_end_of_block(n_urgent)
        elif strategy == 2:
            return self._strategy_uniform(n_urgent)
        elif strategy == 3:
            return self._strategy_after_six(n_urgent)
        else:
            raise ValueError(f"Unknown strategy {strategy}. Must be 1, 2, or 3.")

    # ------------------------------------------------------------------
    # Strategy 1: urgent slots at END of each morning/afternoon block
    # ------------------------------------------------------------------
    def _strategy_end_of_block(self, n_urgent: int) -> Dict[int, List[SlotType]]:
        """
        Distribute n_urgent slots as evenly as possible across the 10 session blocks,
        placing them at the end of each block.

        Blocks in order: Mon-am, Mon-pm, Tue-am, Tue-pm, Wed-am, Wed-pm,
                         Thu-am, Fri-am, Fri-pm, Sat-am  (10 blocks total)
        """
        blocks: List[Tuple[int, int, int]] = []  # (day, session, block_size)
        for day in range(6):
            n_sessions = 1 if day in HALF_DAYS else 2
            for s in range(n_sessions):
                blocks.append((day, s, 16))

        n_blocks = len(blocks)  # always 10
        base, extra = divmod(n_urgent, n_blocks)
        # first 'extra' blocks receive one extra urgent slot
        urgent_per_block = [base + (1 if i < extra else 0) for i in range(n_blocks)]

        day_slots: Dict[int, List[SlotType]] = {d: [SlotType.ELECTIVE] * n for d, n in DAY_SLOTS.items()}

        block_idx = 0
        for day in range(6):
            n_sessions = 1 if day in HALF_DAYS else 2
            for s in range(n_sessions):
                n_u = urgent_per_block[block_idx]
                block_idx += 1
                if n_u == 0:
                    continue
                # slot indices for this session within the day
                start_slot = s * 16
                end_slot = start_slot + 16  # exclusive
                # place n_u urgent slots at the END of the block
                for offset in range(n_u):
                    day_slots[day][end_slot - 1 - offset] = SlotType.URGENT

        assert sum(t == SlotType.URGENT for d in day_slots for t in day_slots[d]) == n_urgent
        return day_slots

    # ------------------------------------------------------------------
    # Strategy 2: urgent slots uniformly spread over each day
    # ------------------------------------------------------------------
    def _strategy_uniform(self, n_urgent: int) -> Dict[int, List[SlotType]]:
        """
        Distribute n_urgent slots proportionally per day, then space them
        evenly within each day using round-based allocation.
        """
        day_slots: Dict[int, List[SlotType]] = {d: [SlotType.ELECTIVE] * n for d, n in DAY_SLOTS.items()}

        # Distribute n_urgent proportionally to each day's slot count
        day_urgent = _proportional_distribute(
            {d: DAY_SLOTS[d] for d in range(6)}, n_urgent
        )

        for day in range(6):
            n_u = day_urgent[day]
            total = DAY_SLOTS[day]
            if n_u == 0:
                continue
            # Evenly space n_u positions among 'total' slots using Bresenham-style spacing
            positions = _evenly_spaced(total, n_u)
            for pos in positions:
                day_slots[day][pos] = SlotType.URGENT

        assert sum(t == SlotType.URGENT for d in day_slots for t in day_slots[d]) == n_urgent
        return day_slots

    # ------------------------------------------------------------------
    # Strategy 3: one urgent slot after every 6 elective slots (per day)
    # ------------------------------------------------------------------
    def _strategy_after_six(self, n_urgent: int) -> Dict[int, List[SlotType]]:
        """
        Distribute n_urgent proportionally per day (same method as Strategy 1),
        then within each day place one urgent slot after every 6 consecutive
        elective slots. The count runs continuously within the day — through
        the lunch break — and resets at each day boundary, matching Figure 6:
        urgent slots land at positions 7, 14, 21, 28 (1-indexed) for a full
        day with 4 urgents.
        """
        day_urgent = _proportional_distribute(
            {d: DAY_SLOTS[d] for d in range(6)}, n_urgent
        )

        day_slots: Dict[int, List[SlotType]] = {}
        for day in range(6):
            n_u = day_urgent[day]
            n_total = DAY_SLOTS[day]
            slots: List[SlotType] = []
            for _ in range(n_u):
                slots.extend([SlotType.ELECTIVE] * 6)
                slots.append(SlotType.URGENT)
            while len(slots) < n_total:
                slots.append(SlotType.ELECTIVE)
            day_slots[day] = slots[:n_total]

        assert sum(t == SlotType.URGENT for d in day_slots for t in day_slots[d]) == n_urgent
        return day_slots


# ------------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------------

def _proportional_distribute(weights: Dict[int, int], total: int) -> Dict[int, int]:
    """
    Distribute 'total' integer items proportionally to the given weights.
    Uses largest-remainder method (Hamilton/Hare method) to avoid rounding errors.
    """
    weight_sum = sum(weights.values())
    exact = {k: total * v / weight_sum for k, v in weights.items()}
    floored = {k: int(v) for k, v in exact.items()}
    remainders = sorted(weights.keys(), key=lambda k: -(exact[k] - floored[k]))
    deficit = total - sum(floored.values())
    result = dict(floored)
    for k in remainders[:deficit]:
        result[k] += 1
    return result


def _evenly_spaced(total: int, n: int) -> List[int]:
    """
    Return n evenly spaced 0-indexed positions out of 'total' slots.
    Uses Bresenham-style integer spacing: positions at round((total/n) * (i + 0.5)) - 1.
    """
    if n == 0:
        return []
    positions = []
    for i in range(n):
        pos = int((total / n) * (i + 0.5))
        pos = min(pos, total - 1)
        positions.append(pos)
    return sorted(set(positions))
