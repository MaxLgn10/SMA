"""
run_pipeline.py
===============
Runs the full simulation pipeline from scratch.
Make sure results_v2/ is empty before running.

Run from the python code folder:
    python run_pipeline.py
"""

import os
import subprocess
import sys

SCRIPTS = [
    "generate_schedules.py",
    "simulation.py",
    "analyze_pareto.py",
    "summary.py",
]

RESULTS_DIR  = os.path.join(os.path.dirname(__file__), "..", "results_v2")
MASTER_CSV   = os.path.join(RESULTS_DIR, "experiment_results_v2.csv")

# delete master CSV if it exists to avoid duplicate rows
if os.path.exists(MASTER_CSV):
    os.remove(MASTER_CSV)
    print(f"Deleted existing {MASTER_CSV}")

for script in SCRIPTS:
    print(f"\n{'=' * 60}")
    print(f"Running {script}...")
    print(f"{'=' * 60}")
    result = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), script)],
        check=True
    )

print(f"\n{'=' * 60}")
print("Pipeline complete.")
print(f"{'=' * 60}")