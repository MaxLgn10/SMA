# SMA Group Assignment – Radiology Department Appointment Scheduling

Simulation Modelling and Analysis (F000941) — Year 2025-2026

## Project Overview

Discrete-event simulation of an outpatient radiology department with a single scanner.
The goal is to find the optimal appointment scheduling policy by evaluating combinations of:

- **Strategic level**: Number of reserved urgent slots per week (N = 10–20)
- **Tactical level**: Positioning strategy for urgent slots (Strategy 1, 2, or 3)
- **Operational level**: Scheduling rule for elective patients (Rules 1–4)

**Objective function** (minimise):
```
w_e × WT_elective + w_u × WT_urgent     (w_e = 1/168, w_u = 1/9)
```

---

## Repository Structure

```
project assignment/
├── cpp code/           # C++ simulation (main source)
│   ├── main.cpp
│   ├── Simulation.cpp / Simulation.hpp
│   ├── Helper.cpp / Helper.hpp
│   └── readme.txt
├── python code/        # Python utilities
│   ├── simulation.py       # Original Python simulation
│   ├── generate_schedules.py  # Generates all 33 input files
│   └── plot_results.py     # Generates plots from results
├── input-S{1,2,3}-{10..20}.txt   # 33 schedule input files
└── results/
    ├── warmup_analysis.csv
    ├── experiment_results.csv
    └── plots/
```

---

## How to Compile the C++ Simulation

```bash
cd "project assignment/cpp code"
clang++ -O2 -std=c++17 -o simulation main.cpp Simulation.cpp Helper.cpp
```

---

## How to Run

### 1. Warmup Analysis (Welch method)
Determines how many weeks to discard at the start of each replication.

```bash
./simulation warmup ../input-S1-14.txt 100 50
```
Arguments: `warmup [inputFile] [W=weeks] [R=replications]`

Output: CSV to stdout → redirect to file:
```bash
./simulation warmup ../input-S1-14.txt 100 50 > ../results/warmup_analysis.csv
```
**Result**: 10 weeks warm-up period determined.

### 2. Full Experiment (all 132 configurations)
Runs all combinations of Strategy × N × Rule with warmup correction and 95% CI.

```bash
mkdir -p ../results
./simulation experiment 100 100 10
```
Arguments: `experiment [W=weeks] [R=replications] [warmupWeeks=10]`

Output: `../results/experiment_results.csv`

Runtime: ~50 seconds for all 132 configurations.

### 3. Generate Plots (Python)

```bash
cd "../python code"
python3 plot_results.py
```

Generates 9 plots in `results/plots/`:
- `warmup_plot.png` — Welch warmup analysis
- `heatmap_S{1,2,3}.png` — objective value by N and Rule per strategy
- `lineplot_S{1,2,3}.png` — objective value trends
- `top10_barplot.png` — top 10 configurations with 95% CI
- `strategy_comparison.png` — strategy comparison across N values

---

## Input File Format

Each `input-S{strategy}-{N}.txt` defines the weekly slot schedule (6 days × 32 slots):

```
<strategy>  <N>
<day> <slot> <type> <appTime>
...
```

Slot types: `e` = elective, `u` = urgent normal, `o` = urgent overtime

To regenerate all 33 input files:
```bash
cd "python code"
python3 generate_schedules.py
```

---

## Scheduling Rules

| Rule | Name | Description |
|------|------|-------------|
| 1 | FCFS | Plain first-come-first-served; appointment = scheduled slot time |
| 2 | Bailey-Welch | First 2 patients of each session get same start time; rest shifted back |
| 3 | Blocking | Patients scheduled in pairs at the same time (block of 2) |
| 4 | Benchmarking | Appointment shifted back by `k_a × σ_e / 60` minutes (k_a = 0.5) |

---

## Current Results Summary

Warm-up: **10 weeks** | Run length: **100 weeks** | Replications: **R = 100**

Best configurations (lowest weighted objective):
- See `results/plots/top10_barplot.png` for top 10 with confidence intervals
- See `results/experiment_results.csv` for full results table
