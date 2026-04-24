"""
Generates input schedule files for all strategy/capacity combinations.

File format: 32 rows x 6 columns (Mon=0 ... Sat=5)
  0 = closed (Thu/Sat afternoon)
  1 = elective patient slot
  2 = urgent patient slot

Strategies:
  1: Urgent slots placed at the END of each morning/afternoon session
  2: Urgent slots evenly distributed throughout the day
  3: Urgent slot placed after every block of elective slots
     (block size adjusted per day so that exactly k urgent slots fit)

Output: ../input-S{strategy}-{n_urgent}.txt  (same folder as existing input files)
"""

import math
import os

FULL_DAYS = [0, 1, 2, 4]   # Mon, Tue, Wed, Fri  (32 slots each)
HALF_DAYS = [3, 5]          # Thu, Sat            (16 slots each, no afternoon)
N_DAYS = 6
N_SLOTS_FULL = 32
N_SLOTS_HALF = 16
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..")


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def create_base_schedule():
    """All slots elective (1), Thu/Sat afternoons closed (0)."""
    schedule = [[1] * N_DAYS for _ in range(N_SLOTS_FULL)]
    for row in range(N_SLOTS_HALF, N_SLOTS_FULL):
        schedule[row][3] = 0  # Thu afternoon closed
        schedule[row][5] = 0  # Sat afternoon closed
    return schedule


def distribute_per_day(n_urgent):
    """
    Distribute n_urgent slots across 6 days using the largest-remainder method,
    proportional to each day's number of available slots (32 for full, 16 for half).
    """
    weights = [N_SLOTS_FULL if d in FULL_DAYS else N_SLOTS_HALF for d in range(N_DAYS)]
    total_weight = sum(weights)
    exact = [n_urgent * w / total_weight for w in weights]
    floored = [int(x) for x in exact]
    remainder = n_urgent - sum(floored)
    # Give the remainder to days with the largest fractional part
    order = sorted(range(N_DAYS), key=lambda i: -(exact[i] - floored[i]))
    for i in range(remainder):
        floored[order[i]] += 1
    return floored


# ---------------------------------------------------------------------------
# Strategy implementations
# ---------------------------------------------------------------------------

def apply_strategy1(schedule, n_urgent):
    """
    Strategy 1: urgent slots at the END of morning and afternoon sessions.
    For full days: ceil(k/2) slots from end of morning, floor(k/2) from end of afternoon.
    For half days: k slots from end of morning.
    """
    per_day = distribute_per_day(n_urgent)
    for d in range(N_DAYS):
        k = per_day[d]
        if d in FULL_DAYS:
            morning_count = math.ceil(k / 2)
            afternoon_count = math.floor(k / 2)
        else:
            morning_count = k
            afternoon_count = 0
        # End of morning: rows 15, 14, 13, ...
        for i in range(morning_count):
            schedule[N_SLOTS_HALF - 1 - i][d] = 2
        # End of afternoon: rows 31, 30, 29, ...
        for i in range(afternoon_count):
            schedule[N_SLOTS_FULL - 1 - i][d] = 2


def apply_strategy2(schedule, n_urgent):
    """
    Strategy 2: urgent slots evenly distributed throughout the day.
    Uses midpoint-offset spacing: position = int(step/2 + i * step).
    """
    per_day = distribute_per_day(n_urgent)
    for d in range(N_DAYS):
        k = per_day[d]
        if k == 0:
            continue
        n_avail = N_SLOTS_FULL if d in FULL_DAYS else N_SLOTS_HALF
        step = n_avail / k
        positions = [int(step / 2 + i * step) for i in range(k)]
        for pos in positions:
            schedule[pos][d] = 2


def apply_strategy3(schedule, n_urgent, block_size=6):
    """
    Strategy 3: one urgent slot after every fixed block of 6 elective slots.
    As per the assignment specification:
        "Starting from the beginning of a session, a time slot for urgent
         patients is planned each time after a block of six time slots for
         elective patients."

    Implementation:
      - Scan through the day's slots, count elective slots, and place an
        urgent slot after every 6th elective slot.
      - On a 32-slot full day, this places urgent slots at indices 6, 13,
        20, 27 (at most 4).
      - On a 16-slot half day, indices 6 and 13 (at most 2).
      - If k (urgent slots to place for that day) is larger than the maximum
        achievable with block_size=6, the remaining urgent slots are placed
        at the END of the day (converting the latest electives to urgent).
    """
    per_day = distribute_per_day(n_urgent)
    for d in range(N_DAYS):
        k = per_day[d]
        if k == 0:
            continue
        n_avail = N_SLOTS_FULL if d in FULL_DAYS else N_SLOTS_HALF

        # 1) Place urgent slots at fixed positions: every (block_size+1)-th slot
        #    starting at index block_size (0-indexed).
        placed = 0
        pos = block_size  # index 6 for block_size=6
        while pos < n_avail and placed < k:
            schedule[pos][d] = 2
            placed += 1
            pos += block_size + 1

        # 2) If k is larger than the number of positions produced above, place
        #    the remaining urgent slots at the end of the day (working backwards),
        #    skipping any slots that are already urgent.
        row = n_avail - 1
        while placed < k and row >= 0:
            if schedule[row][d] != 2:
                schedule[row][d] = 2
                placed += 1
            row -= 1


# ---------------------------------------------------------------------------
# File I/O and verification
# ---------------------------------------------------------------------------

def generate_schedule(strategy, n_urgent):
    schedule = create_base_schedule()
    if strategy == 1:
        apply_strategy1(schedule, n_urgent)
    elif strategy == 2:
        apply_strategy2(schedule, n_urgent)
    elif strategy == 3:
        apply_strategy3(schedule, n_urgent)
    return schedule


def write_schedule(schedule, filepath):
    with open(filepath, 'w') as f:
        for row in schedule:
            f.write('\t'.join(map(str, row)) + '\n')


def count_urgent(schedule):
    return sum(1 for row in schedule for val in row if val == 2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"{'File':<25} {'Urgent slots':>12} {'Status':>10}")
    print("-" * 50)

    all_ok = True
    for strategy in [1, 2, 3]:
        for n in range(10, 21):
            schedule = generate_schedule(strategy, n)
            actual = count_urgent(schedule)
            ok = actual == n
            if not ok:
                all_ok = False
            filename = f"input-S{strategy}-{n}.txt"
            filepath = os.path.join(OUTPUT_DIR, filename)
            write_schedule(schedule, filepath)
            status = "OK" if ok else f"MISMATCH ({actual})"
            print(f"{filename:<25} {actual:>12}    {status}")

    print("-" * 50)
    if all_ok:
        print(f"All 33 files written to {os.path.abspath(OUTPUT_DIR)}/")
    else:
        print("WARNING: some files have incorrect urgent slot counts!")
