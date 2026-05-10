"""
Full factorial experiment: 6 × 3 × 4 = 72 configurations × n_reps replications each.

Uses Common Random Numbers (CRN): same seeds per replication across all configs.
Uses concurrent.futures.ProcessPoolExecutor to run configs in parallel across all CPU cores,
cutting wall-clock time from ~6 h to ~50 min on an 8-core machine.

Usage:
    cd "SMA Group Assignment Cedric"
    python -m experiments.full_factorial [--n-reps N] [--warmup-weeks W] [--sim-weeks S] [--workers N]

Results are saved to results/raw_results.csv and results/summary_table.csv.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from src.performance import aggregate_replications, ReplicationResult
from src.simulation import run_replication

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")

N_URGENT_LEVELS = list(range(10, 21))
STRATEGY_LEVELS = [1, 2, 3]
RULE_LEVELS = [1, 2, 3, 4]

DEFAULT_N_REPS = 90
DEFAULT_WARMUP = 20
DEFAULT_SIM = 52


def load_pilot_params() -> Dict:
    path = os.path.join(RESULTS_DIR, "pilot_summary.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


# ---- Worker function (must be module-level for pickling) ----

def _run_one(args: Tuple) -> Dict:
    """Run a single (config, rep) combination.  Returns a raw-result row dict."""
    n_urgent, strategy, rule, rep, warmup_weeks, sim_weeks = args
    result = run_replication(
        n_urgent=n_urgent,
        strategy=strategy,
        rule=rule,
        seed=rep,
        warmup_weeks=warmup_weeks,
        sim_weeks=sim_weeks,
    )
    return {
        "replication_id": rep,
        "n_urgent": n_urgent, "strategy": strategy, "rule": rule, "rep": rep,
        "AWT_e": result.mean_awt_e,
        "SWT_e": result.mean_swt_e,
        "SWT_u": result.mean_swt_u,
        "OT": result.mean_overtime,
        "W": result.objective,
        # Backwards-compatible column names used by existing analysis scripts.
        "awt_e_hours": result.mean_awt_e,
        "swt_e_min": result.mean_swt_e,
        "swt_u_min": result.mean_swt_u,
        "overtime_min": result.mean_overtime,
        "objective": result.objective,
    }


def _run_tasks_parallel(tasks: List[Tuple], total_runs: int, workers: int) -> List[Dict]:
    """Execute a list of (config, rep) tasks in parallel, printing progress."""
    raw_rows: List[Dict] = []
    start = time.time()
    done = 0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_run_one, t): t for t in tasks}
        for fut in as_completed(futures):
            raw_rows.append(fut.result())
            done += 1
            if done % 50 == 0 or done == total_runs:
                elapsed = time.time() - start
                eta = elapsed / done * (total_runs - done)
                print(f"  {done}/{total_runs}  elapsed {elapsed/60:.1f}m  ETA {eta/60:.1f}m")
    return raw_rows


def _aggregate_and_save(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate raw replication rows to per-config summary and save both CSVs."""
    raw_path = os.path.join(RESULTS_DIR, "raw_results.csv")
    raw_df.to_csv(raw_path, index=False)
    print(f"Raw data saved: {raw_path}  ({len(raw_df)} rows)")

    configs = list(product(N_URGENT_LEVELS, STRATEGY_LEVELS, RULE_LEVELS))
    all_rows: List[Dict] = []
    for (n_u, s, r) in configs:
        sub = raw_df[(raw_df.n_urgent == n_u) & (raw_df.strategy == s) & (raw_df.rule == r)]
        from scipy import stats as sp_stats
        row = {"n_urgent": n_u, "strategy": s, "rule": r}
        for col in ["awt_e_hours", "swt_e_min", "swt_u_min", "overtime_min", "objective"]:
            vals = sub[col].values
            n = len(vals)
            mean = float(np.mean(vals))
            std = float(np.std(vals, ddof=1)) if n > 1 else 0.0
            t_crit = float(sp_stats.t.ppf(0.975, df=max(n - 1, 1)))
            margin = t_crit * std / np.sqrt(n)
            row[f"{col}_mean"] = mean
            row[f"{col}_std"] = std
            row[f"{col}_ci_low"] = mean - margin
            row[f"{col}_ci_high"] = mean + margin
        all_rows.append(row)

    summary_df = pd.DataFrame(all_rows)
    summary_path = os.path.join(RESULTS_DIR, "summary_table.csv")
    summary_df.to_csv(summary_path, index=False)
    print(f"Summary saved: {summary_path}")
    return summary_df


def run_full_factorial(
    n_reps: int = DEFAULT_N_REPS,
    warmup_weeks: int = DEFAULT_WARMUP,
    sim_weeks: int = DEFAULT_SIM,
    workers: int | None = None,
) -> pd.DataFrame:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    configs = list(product(N_URGENT_LEVELS, STRATEGY_LEVELS, RULE_LEVELS))
    total_runs = len(configs) * n_reps
    n_workers = workers or multiprocessing.cpu_count()

    print(f"Full factorial: {len(configs)} configs × {n_reps} reps = {total_runs} runs")
    print(f"Warm-up: {warmup_weeks}w, Simulation: {sim_weeks}w  |  Workers: {n_workers}")

    tasks = [
        (n_u, s, r, rep, warmup_weeks, sim_weeks)
        for (n_u, s, r), rep in product(configs, range(n_reps))
    ]

    t0 = time.time()
    raw_rows = _run_tasks_parallel(tasks, total_runs, n_workers)
    raw_df = pd.DataFrame(raw_rows)
    # Keep canonical columns only (drop redundant AWT_e/SWT_e/etc aliases)
    canonical = ["replication_id", "n_urgent", "strategy", "rule", "rep",
                 "awt_e_hours", "swt_e_min", "swt_u_min", "overtime_min", "objective"]
    raw_df = raw_df[[c for c in canonical if c in raw_df.columns]]

    summary_df = _aggregate_and_save(raw_df)
    print(f"\nTotal time: {(time.time() - t0)/60:.1f} min")
    return summary_df


def run_append(
    target_reps: int = 90,
    warmup_weeks: int = DEFAULT_WARMUP,
    sim_weeks: int = DEFAULT_SIM,
    workers: int | None = None,
) -> pd.DataFrame:
    """
    Append replications [existing_max+1, target_reps) to raw_results.csv.

    Safe because each replication's seed is SHA-256(rep_id, stream_name) only —
    independent of N_REPS, run order, or any other global state.
    CRN is preserved: every config receives the same new rep_ids in the same order.
    """
    os.makedirs(RESULTS_DIR, exist_ok=True)
    raw_path = os.path.join(RESULTS_DIR, "raw_results.csv")
    if not os.path.exists(raw_path):
        raise FileNotFoundError(f"raw_results.csv not found at {raw_path}. Run full factorial first.")

    existing_df = pd.read_csv(raw_path)
    start_rep = int(existing_df["rep"].max()) + 1

    if start_rep >= target_reps:
        print(f"Already have {start_rep} reps (>= {target_reps}). Nothing to append.")
        return existing_df

    configs = list(product(N_URGENT_LEVELS, STRATEGY_LEVELS, RULE_LEVELS))
    new_reps = list(range(start_rep, target_reps))
    total_runs = len(configs) * len(new_reps)
    n_workers = workers or multiprocessing.cpu_count()

    print(f"Append mode: reps {start_rep}–{target_reps-1} "
          f"({len(new_reps)} new reps × {len(configs)} configs = {total_runs} tasks)")
    print(f"Warm-up: {warmup_weeks}w, Simulation: {sim_weeks}w  |  Workers: {n_workers}")

    tasks = [
        (n_u, s, r, rep, warmup_weeks, sim_weeks)
        for (n_u, s, r), rep in product(configs, new_reps)
    ]

    t0 = time.time()
    new_rows = _run_tasks_parallel(tasks, total_runs, n_workers)
    new_df = pd.DataFrame(new_rows)

    # Normalise columns: add replication_id to existing if absent, then align
    if "replication_id" not in existing_df.columns:
        existing_df.insert(0, "replication_id", existing_df["rep"])
    keep_cols = list(existing_df.columns)
    new_aligned = new_df[[c for c in keep_cols if c in new_df.columns]].copy()

    combined = (pd.concat([existing_df, new_aligned], ignore_index=True)
                  .sort_values(["n_urgent", "strategy", "rule", "rep"])
                  .reset_index(drop=True))

    # Verify: every config must have exactly target_reps unique rep_ids, no duplicates
    bad = []
    for n_u, s, r in configs:
        sub = combined[(combined.n_urgent == n_u) & (combined.strategy == s) & (combined.rule == r)]
        n_uniq = sub["rep"].nunique()
        if n_uniq != target_reps:
            bad.append(f"  ({n_u},{s},{r}): got {n_uniq}, expected {target_reps}")
    if bad:
        raise ValueError("Verification failed — wrong rep counts:\n" + "\n".join(bad))

    print(f"Verified: all {len(configs)} configs have exactly {target_reps} unique rep_ids.")
    summary_df = _aggregate_and_save(combined)
    print(f"\nAppend total time: {(time.time() - t0)/60:.1f} min")
    return summary_df


def save_top10(summary_df: pd.DataFrame):
    top10 = summary_df.nsmallest(10, "objective_mean")[
        ["n_urgent", "strategy", "rule",
         "objective_mean", "objective_ci_low", "objective_ci_high",
         "awt_e_hours_mean", "swt_u_min_mean", "overtime_min_mean"]
    ]
    path = os.path.join(RESULTS_DIR, "top10_configs.csv")
    top10.to_csv(path, index=False)
    print(f"Top-10 saved: {path}")
    print(top10.to_string(index=False))
    return top10


def save_pairwise_vs_baseline(raw_df: pd.DataFrame):
    from scipy import stats as sp_stats

    baseline = raw_df[(raw_df.n_urgent == 14) & (raw_df.strategy == 1) & (raw_df.rule == 1)]
    baseline_obj = baseline.set_index("rep")["objective"]

    rows = []
    for (n_u, s, r), group in raw_df.groupby(["n_urgent", "strategy", "rule"]):
        if n_u == 14 and s == 1 and r == 1:
            continue
        cfg_obj = group.set_index("rep")["objective"]
        common = sorted(set(cfg_obj.index) & set(baseline_obj.index))
        diff = [cfg_obj[rep] - baseline_obj[rep] for rep in common]
        t_stat, p_val = sp_stats.ttest_1samp(diff, 0)
        mean_diff = float(np.mean(diff))
        n = len(diff)
        margin = float(sp_stats.t.ppf(0.975, df=n - 1)) * float(np.std(diff, ddof=1)) / np.sqrt(n)
        rows.append({
            "n_urgent": n_u, "strategy": s, "rule": r,
            "mean_diff_objective": mean_diff,
            "ci_low": mean_diff - margin, "ci_high": mean_diff + margin,
            "t_stat": t_stat, "p_value": p_val,
            "significant": p_val < 0.05,
            "better_than_baseline": mean_diff < 0 and p_val < 0.05,
        })

    df = pd.DataFrame(rows)
    df["p_bonferroni"] = np.minimum(df["p_value"] * 71, 1.0)
    df["significant_bonferroni"] = df["p_bonferroni"] < 0.05
    path = os.path.join(RESULTS_DIR, "pairwise_comparison_vs_baseline.csv")
    df.to_csv(path, index=False)
    print(f"Pairwise comparison saved: {path}")
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-reps", type=int, default=None)
    parser.add_argument("--warmup-weeks", type=int, default=None)
    parser.add_argument("--sim-weeks", type=int, default=None)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument(
        "--append-to", type=int, default=None, metavar="N",
        help="Append missing replications to reach N reps per config (safe with CRN; "
             "seeds depend only on rep_id, not run order or total N).",
    )
    args = parser.parse_args()

    pilot = load_pilot_params()
    warmup_weeks = args.warmup_weeks or pilot.get("warmup_weeks", DEFAULT_WARMUP)
    sim_weeks = args.sim_weeks or DEFAULT_SIM
    workers = args.workers

    if args.append_to is not None:
        summary_df = run_append(args.append_to, warmup_weeks, sim_weeks, workers)
    else:
        n_reps = args.n_reps or pilot.get("n_required", DEFAULT_N_REPS)
        summary_df = run_full_factorial(n_reps, warmup_weeks, sim_weeks, workers)

    save_top10(summary_df)
    raw_df = pd.read_csv(os.path.join(RESULTS_DIR, "raw_results.csv"))
    save_pairwise_vs_baseline(raw_df)


if __name__ == "__main__":
    main()
