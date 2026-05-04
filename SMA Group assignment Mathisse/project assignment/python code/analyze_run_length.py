"""
analyze_run_length.py
---------------------
Justifies the run length W = 100 weeks used in the experiment.

Reads  ../results/warmup_analysis.csv  (50 replications x 100 weeks,
Welch's per-week averages for S1, N=14, Rule 1).

Produces three plots:
  1. run_length_weekly.png     – weekly objective with Welch's moving average
     and the chosen warm-up boundary (week 10).
  2. run_length_cumulative.png – cumulative mean of weekly objective from
     week 10 onwards with a 95 % CI band (across weeks); demonstrates that
     the cumulative mean has stabilised well before W=100.
  3. run_length_halfwidth.png  – CI half-width of the cumulative mean vs.
     number of active weeks used.  Shows that 90 active weeks (W=100,
     warm-up 10) already yields a very narrow CI.

Usage
-----
    python analyze_run_length.py
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
PLOT_DIR    = os.path.join(RESULTS_DIR, "plots")
os.makedirs(PLOT_DIR, exist_ok=True)

WARMUP      = 10     # weeks to discard
ALPHA       = 0.05   # 95% CI


def save(fig, name):
    path = os.path.join(PLOT_DIR, name)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


def main():
    df = pd.read_csv(os.path.join(RESULTS_DIR, "warmup_analysis.csv"))
    weeks = df["week"].values
    obj   = df["avg_objective"].values

    # ── 1) Per-week objective + Welch's moving average ───────────────────────
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(weeks, obj, color="#4C72B0", lw=1.2, label="Weekly avg (across R=50)")
    window = 10
    smooth = pd.Series(obj).rolling(window, center=True).mean()
    ax.plot(weeks, smooth, color="#C44E52", lw=2,
            label=f"Welch moving avg (window={window})")
    ax.axvline(WARMUP, color="grey", ls="--", lw=1.2,
               label=f"Warm-up boundary = {WARMUP}")
    ax.set_xlabel("Week")
    ax.set_ylabel("Objective value")
    ax.set_title("Run-length justification – weekly objective\n"
                 "(S1, N=14, Rule 1, 50 replications)")
    ax.grid(axis="y", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    save(fig, "run_length_weekly.png")

    # ── 2) Cumulative mean of weekly objective (weeks 10..W) ────────────────
    active = obj[WARMUP:]
    cum_mean = np.cumsum(active) / np.arange(1, len(active) + 1)
    # running CI halfwidth (across weeks treated as iid draws in-steady-state)
    hw = np.full_like(cum_mean, np.nan)
    for k in range(2, len(active) + 1):
        x = active[:k]
        s = x.std(ddof=1)
        t = stats.t.ppf(1 - ALPHA / 2, df=k - 1)
        hw[k - 1] = t * s / np.sqrt(k)
    active_weeks = np.arange(1, len(active) + 1)  # 1..90

    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(active_weeks, cum_mean, color="#4C72B0", lw=1.8,
            label="Cumulative mean of weekly objective")
    ax.fill_between(active_weeks, cum_mean - hw, cum_mean + hw,
                    color="#4C72B0", alpha=0.20,
                    label="95 % CI band")
    ax.set_xlabel("Number of active weeks used  (= W – warm-up)")
    ax.set_ylabel("Cumulative mean objective")
    ax.set_title("Run-length justification – cumulative mean\n"
                 "converges well before the full W=100 is used")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    save(fig, "run_length_cumulative.png")

    # ── 3) Absolute & relative CI halfwidth vs active weeks ─────────────────
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(active_weeks, hw, color="#4C72B0", lw=2,
            label="Absolute halfwidth")
    ax.set_xlabel("Active weeks used")
    ax.set_ylabel("Absolute CI halfwidth (hours)", color="#4C72B0")
    ax.tick_params(axis="y", labelcolor="#4C72B0")
    ax.grid(alpha=0.3)

    ax2 = ax.twinx()
    with np.errstate(invalid="ignore"):
        rel = 100.0 * hw / cum_mean
    ax2.plot(active_weeks, rel, color="#C44E52", lw=2,
             label="Relative halfwidth (%)")
    ax2.set_ylabel("Relative halfwidth (%)", color="#C44E52")
    ax2.tick_params(axis="y", labelcolor="#C44E52")

    ax.set_title("Run-length justification – CI halfwidth shrinks rapidly\n"
                 "and is well below 5 % of the mean at W=100 (90 active weeks)")
    lines_1, labels_1 = ax.get_legend_handles_labels()
    lines_2, labels_2 = ax2.get_legend_handles_labels()
    ax.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper right")
    fig.tight_layout()
    save(fig, "run_length_halfwidth.png")

    # summary
    final_abs = hw[-1]
    final_rel = 100 * final_abs / cum_mean[-1]
    print(f"\nAt W=100 (active weeks = {len(active)}):")
    print(f"  cumulative mean objective = {cum_mean[-1]:.5f}")
    print(f"  CI halfwidth             = {final_abs:.5f}")
    print(f"  relative halfwidth       = {final_rel:.3f} % of mean")


if __name__ == "__main__":
    main()
