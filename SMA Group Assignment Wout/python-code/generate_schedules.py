"""Generate all 33 appointment schedule input files.

Output format: 32 rows x 6 columns.
Columns are Mon..Sat. Values are:
  0 = closed/no slot
  1 = elective slot
  2 = urgent slot during normal working hours

The C++ simulation then adds 10 urgent overtime slots per day internally.
"""

import math
from pathlib import Path

FULL_DAYS = [0, 1, 2, 4]      # Mon, Tue, Wed, Fri
HALF_DAYS = [3, 5]            # Thu, Sat
N_DAYS = 6
N_SLOTS_FULL = 32
N_SLOTS_HALF = 16
OUTPUT_DIR = Path(__file__).resolve().parent.parent


def create_base_schedule():
    schedule = [[1 for _ in range(N_DAYS)] for _ in range(N_SLOTS_FULL)]
    for row in range(N_SLOTS_HALF, N_SLOTS_FULL):
        schedule[row][3] = 0
        schedule[row][5] = 0
    return schedule


def distribute_per_day(n_urgent):
    weights = [N_SLOTS_FULL if d in FULL_DAYS else N_SLOTS_HALF for d in range(N_DAYS)]
    total = sum(weights)
    exact = [n_urgent * w / total for w in weights]
    base = [math.floor(x) for x in exact]
    remainder = n_urgent - sum(base)
    order = sorted(range(N_DAYS), key=lambda d: (-(exact[d] - base[d]), d))
    for i in range(remainder):
        base[order[i]] += 1
    return base


def apply_strategy1(schedule, n_urgent):
    """Urgent slots at the end of each morning/afternoon session."""
    per_day = distribute_per_day(n_urgent)
    for d, k in enumerate(per_day):
        if d in FULL_DAYS:
            morning_count = math.ceil(k / 2)
            afternoon_count = math.floor(k / 2)
        else:
            morning_count = k
            afternoon_count = 0
        for i in range(morning_count):
            schedule[N_SLOTS_HALF - 1 - i][d] = 2
        for i in range(afternoon_count):
            schedule[N_SLOTS_FULL - 1 - i][d] = 2


def apply_strategy2(schedule, n_urgent):
    """Urgent slots distributed evenly over each available working day."""
    per_day = distribute_per_day(n_urgent)
    for d, k in enumerate(per_day):
        if k == 0:
            continue
        n_avail = N_SLOTS_FULL if d in FULL_DAYS else N_SLOTS_HALF
        step = n_avail / k
        positions = [int(step / 2 + i * step) for i in range(k)]
        for pos in positions:
            schedule[pos][d] = 2


def apply_strategy3(schedule, n_urgent, block_size=6):
    """Place urgent slots after blocks of elective slots within each session."""
    per_day = distribute_per_day(n_urgent)
    for d, k in enumerate(per_day):
        if k == 0:
            continue
        n_avail = N_SLOTS_FULL if d in FULL_DAYS else N_SLOTS_HALF
        sessions = [(0, N_SLOTS_HALF)]
        if d in FULL_DAYS:
            sessions.append((N_SLOTS_HALF, N_SLOTS_FULL))

        placed = 0
        for start, end in sessions:
            elective_count = 0
            for pos in range(start, end):
                if placed >= k:
                    break
                elective_count += 1
                if elective_count % (block_size + 1) == 0:
                    schedule[pos][d] = 2
                    placed += 1

        row = n_avail - 1
        while placed < k and row >= 0:
            if schedule[row][d] != 2:
                schedule[row][d] = 2
                placed += 1
            row -= 1


def generate_schedule(strategy, n_urgent):
    schedule = create_base_schedule()
    if strategy == 1:
        apply_strategy1(schedule, n_urgent)
    elif strategy == 2:
        apply_strategy2(schedule, n_urgent)
    elif strategy == 3:
        apply_strategy3(schedule, n_urgent)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
    return schedule


def count_urgent(schedule):
    return sum(1 for row in schedule for value in row if value == 2)


def write_schedule(schedule, path):
    with path.open("w", encoding="utf-8") as f:
        for row in schedule:
            f.write("\t".join(str(value) for value in row) + "\n")


if __name__ == "__main__":
    print(f"{'file':<18} {'urgent':>8} status")
    print("-" * 34)
    all_ok = True
    for strategy in (1, 2, 3):
        for n_urgent in range(10, 21):
            schedule = generate_schedule(strategy, n_urgent)
            actual = count_urgent(schedule)
            ok = actual == n_urgent
            all_ok = all_ok and ok
            filename = f"input-S{strategy}-{n_urgent}.txt"
            write_schedule(schedule, OUTPUT_DIR / filename)
            print(f"{filename:<18} {actual:>8} {'OK' if ok else 'MISMATCH'}")
    print("-" * 34)
    print(f"Files written to: {OUTPUT_DIR}")
    if not all_ok:
        raise SystemExit("At least one schedule has an incorrect urgent-slot count.")
