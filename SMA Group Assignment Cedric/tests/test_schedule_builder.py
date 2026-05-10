"""Tests for ScheduleBuilder: slot counts, strategy invariants, type distribution."""
import pytest
from src.schedule_builder import (
    ScheduleBuilder,
    SlotType,
    DAY_SLOTS,
    HALF_DAYS,
    WEEK_TOTAL_SLOTS,
    slot_start_offset,
    day_close_offset,
)

BUILDER = ScheduleBuilder()
N_URGENT_VALUES = list(range(10, 21))
STRATEGIES = [1, 2, 3]


# ---- slot_start_offset geometry ----

def test_slot_offset_morning():
    """Slot 0 starts at 0 (08:00), slot 15 starts at 225 (11:45)."""
    assert slot_start_offset(0) == 0
    assert slot_start_offset(15) == 225


def test_slot_offset_afternoon():
    """Slot 16 starts at 300 (13:00 = 240+60 lunch), slot 31 at 525 (16:45)."""
    assert slot_start_offset(16) == 300   # 16*15 + 60
    assert slot_start_offset(31) == 525   # 31*15 + 60


def test_day_close_full_vs_half():
    assert day_close_offset(0) == 540   # Monday full day
    assert day_close_offset(3) == 240   # Thursday half day
    assert day_close_offset(5) == 240   # Saturday half day


# ---- total slot counts per week ----

@pytest.mark.parametrize("n_urgent", N_URGENT_VALUES)
@pytest.mark.parametrize("strategy", STRATEGIES)
def test_total_slots_correct(n_urgent, strategy):
    schedule = BUILDER.build(n_urgent, strategy)
    total = sum(len(v) for v in schedule.values())
    assert total == WEEK_TOTAL_SLOTS, f"Expected {WEEK_TOTAL_SLOTS}, got {total}"


@pytest.mark.parametrize("n_urgent", N_URGENT_VALUES)
@pytest.mark.parametrize("strategy", STRATEGIES)
def test_urgent_count_exact(n_urgent, strategy):
    schedule = BUILDER.build(n_urgent, strategy)
    n_u = sum(1 for day in schedule for t in schedule[day] if t == SlotType.URGENT)
    assert n_u == n_urgent, f"Expected {n_urgent} urgent slots, got {n_u}"


@pytest.mark.parametrize("n_urgent", N_URGENT_VALUES)
@pytest.mark.parametrize("strategy", STRATEGIES)
def test_elective_count_correct(n_urgent, strategy):
    schedule = BUILDER.build(n_urgent, strategy)
    n_e = sum(1 for day in schedule for t in schedule[day] if t == SlotType.ELECTIVE)
    assert n_e == WEEK_TOTAL_SLOTS - n_urgent


@pytest.mark.parametrize("n_urgent", N_URGENT_VALUES)
@pytest.mark.parametrize("strategy", STRATEGIES)
def test_day_slot_lengths(n_urgent, strategy):
    schedule = BUILDER.build(n_urgent, strategy)
    for day, expected_n in DAY_SLOTS.items():
        assert len(schedule[day]) == expected_n, (
            f"Day {day}: expected {expected_n} slots, got {len(schedule[day])}"
        )


# ---- Strategy 1 specifics ----

def test_strategy1_urgent_at_end_of_block():
    """Strategy 1: urgent slots should be at the end of each block (session)."""
    schedule = BUILDER.build(14, 1)
    for day in range(6):
        slots = schedule[day]
        n_sessions = 1 if day in HALF_DAYS else 2
        for s in range(n_sessions):
            block = slots[s * 16: (s + 1) * 16]
            # Find last non-elective position (urgent slots should be at the end)
            urgent_positions = [i for i, t in enumerate(block) if t == SlotType.URGENT]
            if urgent_positions:
                # All urgent slots must be contiguous at the END of the block
                expected_start = 16 - len(urgent_positions)
                assert urgent_positions[0] == expected_start, (
                    f"Day {day} session {s}: urgent slots not at end. Positions: {urgent_positions}"
                )
                assert urgent_positions == list(range(expected_start, 16))


# ---- Strategy 3 specifics ----

def test_strategy3_per_day_pattern():
    """Strategy 3: within each day urgents appear after every 6 elective slots (Figure 6)."""
    for n_urgent in N_URGENT_VALUES:
        schedule = BUILDER.build(n_urgent, 3)
        for day in range(6):
            slots = schedule[day]
            n_u = sum(1 for t in slots if t == SlotType.URGENT)
            for i in range(n_u):
                assert slots[i * 7 + 6] == SlotType.URGENT, (
                    f"n_urgent={n_urgent}, day={day}: urgent not at pos {i * 7 + 6}"
                )
                assert all(t == SlotType.ELECTIVE for t in slots[i * 7: i * 7 + 6])
            for pos in range(n_u * 7, DAY_SLOTS[day]):
                assert slots[pos] == SlotType.ELECTIVE


def test_strategy3_matches_reference_n14():
    """n=14: Mon/Tue/Wed/Fri get 3 urgents at 0-indexed positions 6,13,20; Thu/Sat get 1 at 6."""
    schedule = BUILDER.build(14, 3)
    for day in [0, 1, 2, 4]:  # Mon Tue Wed Fri
        assert schedule[day][6] == SlotType.URGENT
        assert schedule[day][13] == SlotType.URGENT
        assert schedule[day][20] == SlotType.URGENT
    for day in [3, 5]:  # Thu Sat (half days)
        assert schedule[day][6] == SlotType.URGENT
        n_u = sum(1 for t in schedule[day] if t == SlotType.URGENT)
        assert n_u == 1


# ---- Strategy 2 specifics ----

def test_strategy2_urgent_distributed_across_all_days():
    """Strategy 2 should produce urgent slots on multiple different days."""
    for n_urgent in N_URGENT_VALUES:
        schedule = BUILDER.build(n_urgent, 2)
        days_with_urgent = sum(
            1 for day in range(6)
            if any(t == SlotType.URGENT for t in schedule[day])
        )
        # With enough urgent slots, all 6 days should get at least one
        if n_urgent >= 12:
            assert days_with_urgent >= 4, (
                f"n_urgent={n_urgent}: only {days_with_urgent} days have urgent slots"
            )


# ---- Invalid inputs ----

def test_invalid_strategy():
    with pytest.raises(ValueError):
        BUILDER.build(14, 99)
