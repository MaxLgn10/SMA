# SMA radiology project - C++ translation

This version keeps the teacher's C++ template structure and ports the Python simulation logic into C++17.

## What is included

- `cpp-code/include/Simulation.hpp`
- `cpp-code/src/Simulation.cpp`
- `cpp-code/src/Helper.cpp`
- `cpp-code/main.cpp`
- `python-code/generate_schedules.py`
- `python-code/plot_results.py`
- `input-S{1,2,3}-{10..20}.txt` schedule files

The C++ program does the simulation and writes CSV files. Graph generation is kept in Python because it is much simpler and cleaner than plotting directly in C++.

## Scheduling rules implemented

1. `Rule 1`: FCFS. Appointment time equals slot start time.
2. `Rule 2`: Bailey-Welch. First two elective patients in each session receive the session start time; later elective patients are shifted one slot earlier.
3. `Rule 3`: Blocking. Elective appointments are scheduled in pairs with the same appointment time.
4. `Rule 4`: Benchmarking. Elective appointment time is shifted back by `k_a * sigma_e`, with `k_a = 0.5` and `sigma_e = 3` minutes.

## Compile

From the project root:

```bash
cd cpp-code
cmake -S . -B build
cmake --build build
```

The executable is written to `cpp-code/simulation`.

Alternative direct compile command:

```bash
cd cpp-code
clang++ -O2 -std=c++17 -Iinclude main.cpp src/Simulation.cpp src/Helper.cpp -o simulation
```

## Run one configuration

```bash
cd cpp-code
./simulation single ../input-S1-14.txt 1 100 100 0 ../results/single_run_results.csv
```

Arguments:

```text
single [inputFile] [rule] [W] [R] [warmupWeeks] [urgentTwoBlocks=0|1] [outFile]
```

## Warmup analysis

```bash
cd cpp-code
./simulation warmup ../input-S1-14.txt 1 100 50 0 ../results/warmup_analysis.csv
```

Arguments:

```text
warmup [inputFile] [rule] [W] [R] [urgentTwoBlocks=0|1] [outFile]
```

## Full experiment

This runs all 132 combinations: 3 strategies x 11 urgent slot levels x 4 appointment rules.

```bash
cd cpp-code
./simulation experiment 100 100 10 0 .. ../results/experiment_results.csv
```

Arguments:

```text
experiment [W] [R] [warmupWeeks] [urgentTwoBlocks=0|1] [inputDir] [outFile]
```

## Generate graphs

Install Python dependencies if needed:

```bash
python3 -m pip install pandas matplotlib numpy
```

Then run:

```bash
cd python-code
python3 plot_results.py
```

This reads:

- `../results/warmup_analysis.csv`
- `../results/experiment_results.csv`

and writes plots to:

- `../results/plots/`

## Regenerate all schedule input files

```bash
cd python-code
python3 generate_schedules.py
```

This recreates all 33 files named `input-S{strategy}-{n_urgent}.txt` in the project root.
