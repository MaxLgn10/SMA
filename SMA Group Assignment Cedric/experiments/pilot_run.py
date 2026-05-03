"""
Pilot run experiment:
  1. Run 10 replications of the baseline config (14 urgent, strategy 1, rule 1).
  2. Compute weekly moving averages of the weighted objective (Welch method).
  3. Plot the Welch plot → determine warm-up period visually.
  4. Compute required sample size n via the pilot-run formula.
  5. Save welch_plot.png to results/.

Usage:
    cd "SMA Group Assignment Cedric"
    python -m experiments.pilot_run
"""
from __future__ import annotations

import os
import sys

# Make src importable when run from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

from src.simulation import run_replication
from src.performance import W_ELECTIVE, W_URGENT

# ---- Configuration ----
BASELINE = dict(n_urgent=14, strategy=1, rule=1)
N_PILOT = 10
WARMUP_WEEKS = 8      # conservative initial estimate; refined by Welch plot
SIM_WEEKS = 52
TOTAL_WEEKS = WARMUP_WEEKS + SIM_WEEKS
WELCH_WINDOW = 4      # moving average half-window for Welch plot
EPSILON = 0.05        # desired relative precision (5%)
ALPHA = 0.05          # significance level for CI
RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")


def run_pilot(n_pilot: int = N_PILOT):
    """Run n_pilot replications with WARMUP_WEEKS=0 to see the full transient."""
    print(f"Running {n_pilot} pilot replications (warmup=0, sim={TOTAL_WEEKS} weeks)...")
    weekly_objectives: list[list[float]] = []

    for rep in range(n_pilot):
        # Use warmup_weeks=0 to collect full transient for Welch analysis
        result = run_replication(
            **BASELINE,
            seed=rep,
            warmup_weeks=0,
            sim_weeks=TOTAL_WEEKS,
        )
        obj_per_week = [ws.objective for ws in result.weekly]
        weekly_objectives.append(obj_per_week)
        print(f"  Rep {rep+1}/{n_pilot}: mean_obj = {np.mean(obj_per_week):.4f}")

    return weekly_objectives


def welch_moving_average(weekly_objectives: list[list[float]], window: int = WELCH_WINDOW) -> np.ndarray:
    """
    Compute the Welch moving average across replications.
    For each week w, average Y_w over replications then smooth with a moving average.
    """
    # Pad shorter replications to the same length
    n_weeks = max(len(w) for w in weekly_objectives)
    matrix = np.full((len(weekly_objectives), n_weeks), np.nan)
    for i, row in enumerate(weekly_objectives):
        matrix[i, :len(row)] = row

    # Mean across replications for each week
    mean_per_week = np.nanmean(matrix, axis=0)

    # Moving average with window size = 2*window+1
    smoothed = np.convolve(mean_per_week, np.ones(2 * window + 1) / (2 * window + 1), mode="valid")
    # Offset: smoothed[0] corresponds to week `window`
    return mean_per_week, smoothed


def determine_warmup(smoothed: np.ndarray, window: int = WELCH_WINDOW) -> int:
    """
    Heuristic: warm-up ends when the smoothed curve stays within ±5% of the
    overall mean for at least 3 consecutive periods.
    Returns the recommended warm-up in weeks (relative to the start).
    """
    tail_mean = np.mean(smoothed[-int(len(smoothed) * 0.5):])
    tol = 0.05 * abs(tail_mean) + 1e-9
    stable_since = None
    for i, v in enumerate(smoothed):
        if abs(v - tail_mean) <= tol:
            if stable_since is None:
                stable_since = i
            if i - stable_since >= 2:
                return stable_since + window  # map back to week index
        else:
            stable_since = None
    return window  # fallback


def compute_required_n(weekly_objectives: list[list[float]], warmup_weeks: int) -> dict:
    """
    Compute required number of replications using the pilot-run formula:
        n >= (t_{1-alpha/2,n0-1} * s0 / (epsilon * mu0))^2
    Applied to the per-replication mean objective (post warmup).
    """
    per_rep_means = []
    for rep_obj in weekly_objectives:
        post_warmup = rep_obj[warmup_weeks:]
        per_rep_means.append(float(np.mean(post_warmup)))

    arr = np.array(per_rep_means)
    n0 = len(arr)
    mu_pilot = float(np.mean(arr))
    s_pilot = float(np.std(arr, ddof=1)) if n0 > 1 else 0.0
    tcrit = float(stats.t.ppf(1 - ALPHA / 2, df=n0 - 1)) if n0 > 1 else 0.0

    if mu_pilot == 0 or n0 <= 1:
        n_required = 30
    else:
        n_required = int(np.ceil((tcrit * s_pilot / (EPSILON * abs(mu_pilot))) ** 2))

    return {
        "n_required": n_required,
        "n_pilot": n0,
        "pilot_mean_W": mu_pilot,
        "pilot_std_W": s_pilot,
        "tcrit": tcrit,
        "epsilon": EPSILON,
        "alpha": ALPHA,
        "per_rep_means": per_rep_means,
    }


def save_welch_plot(mean_per_week: np.ndarray, smoothed: np.ndarray,
                    warmup_weeks: int, window: int = WELCH_WINDOW):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    weeks = np.arange(len(mean_per_week))
    smooth_weeks = np.arange(window, window + len(smoothed))

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(weeks, mean_per_week, alpha=0.4, color="steelblue", label="Weekly mean (across reps)")
    ax.plot(smooth_weeks, smoothed, color="navy", linewidth=2, label=f"Moving avg (±{window}w)")
    ax.axvline(warmup_weeks, color="red", linestyle="--", linewidth=1.5,
               label=f"Warm-up cutoff ({warmup_weeks} weeks)")
    ax.set_xlabel("Week")
    ax.set_ylabel("Weighted objective W")
    ax.set_title("Welch Plot – Warm-up Period Analysis (Baseline config: 14 urgent, S1, R1)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "welch_plot.png")
    plt.savefig(path, dpi=150)
    warmup_path = os.path.join(RESULTS_DIR, "warmup_plot.png")
    plt.savefig(warmup_path, dpi=150)
    plt.close()
    print(f"Welch plot saved to {path}")
    print(f"Warm-up plot saved to {warmup_path}")


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    weekly_objectives = run_pilot(N_PILOT)

    mean_per_week, smoothed = welch_moving_average(weekly_objectives, WELCH_WINDOW)
    warmup_est = determine_warmup(smoothed, WELCH_WINDOW)
    warmup_est = max(warmup_est, 4)  # enforce minimum 4-week warmup

    print(f"\nEstimated warm-up period: {warmup_est} weeks")

    sample_size = compute_required_n(weekly_objectives, warmup_est)
    n_req = sample_size["n_required"]
    print(f"Pilot mean W: {sample_size['pilot_mean_W']:.6f}")
    print(f"Pilot std W: {sample_size['pilot_std_W']:.6f}")
    print(f"t critical value: {sample_size['tcrit']:.6f}")
    print(f"Required replications (epsilon={EPSILON}, alpha={ALPHA}): {n_req}")

    save_welch_plot(mean_per_week, smoothed, warmup_est, WELCH_WINDOW)

    # Save summary
    summary = {
        "warmup_weeks": warmup_est,
        "total_weeks": TOTAL_WEEKS,
        **sample_size,
    }
    import json
    path = os.path.join(RESULTS_DIR, "pilot_summary.json")
    with open(path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Pilot summary saved to {path}")
    return summary


if __name__ == "__main__":
    main()
