"""
analyze_replications.py
-----------------------
Justifies the number of replications R used in the experiment.

For one or more configurations, reads per-replication objective values from
CSVs produced by  `./simulation replication_analysis ...`  and plots the
running (cumulative) mean with an intermediate 95 % confidence interval as R
grows from 2 to R_max. The plot is saved to
   ../results/plots/replication_justification.png

The corresponding CI half-width curve (absolute and as a percentage of the
running mean) is saved to
   ../results/plots/replication_halfwidth.png

Usage
-----
    python analyze_replications.py

Requires that
   ../results/replication_analysis_S3N13R4.csv   (best config)
   ../results/replication_analysis_S1N20R3.csv   (a worse config)
exist.  Generate them with, for example:
   ./simulation replication_analysis ../input-S3-13.txt 4 100 100 10 \
       ../results/replication_analysis_S3N13R4.csv
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
PLOT_DIR    = os.path.join(RESULTS_DIR, "plots")
os.makedirs(PLOT_DIR, exist_ok=True)

# (file, label, colour)
DATASETS = [
    ("replication_analysis_S3N13R4.csv",
     "Best config  (S3, N=13, Rule 4)", "#4C72B0"),
    ("replication_analysis_S1N20R3.csv",
     "Worse config (S1, N=20, Rule 3)", "#C44E52"),
]

ALPHA = 0.05    # 95% CI


def running_stats(values):
    """Return running mean and 95% t-CI halfwidth as R grows."""
    n = len(values)
    means      = np.zeros(n)
    halfwidths = np.zeros(n)
    means[0]  = values[0]
    halfwidths[0] = np.nan          # CI undefined for R=1
    for k in range(2, n + 1):
        x = values[:k]
        m = x.mean()
        s = x.std(ddof=1)
        t = stats.t.ppf(1 - ALPHA / 2, df=k - 1)
        means[k - 1]      = m
        halfwidths[k - 1] = t * s / np.sqrt(k)
    return means, halfwidths


def main():
    fig1, ax1 = plt.subplots(figsize=(9, 5))
    fig2, ax2 = plt.subplots(figsize=(9, 5))

    for fname, label, color in DATASETS:
        path = os.path.join(RESULTS_DIR, fname)
        if not os.path.exists(path):
            print(f"Missing {path} – skip")
            continue
        df = pd.read_csv(path)
        values = df["objective"].values
        means, hw = running_stats(values)
        R = np.arange(1, len(values) + 1)

        # Running mean ± halfwidth
        ax1.plot(R, means, color=color, lw=2, label=label)
        ax1.fill_between(R, means - hw, means + hw,
                         alpha=0.20, color=color)

        # Relative halfwidth (%) — main quantity the professor grades
        with np.errstate(invalid="ignore", divide="ignore"):
            rel = 100.0 * hw / means
        ax2.plot(R, rel, color=color, lw=2, label=label)

    ax1.set_xlabel("Number of replications R")
    ax1.set_ylabel("Running mean objective  (± 95 % CI)")
    ax1.set_title("Replication justification – running mean with 95 % CI\n"
                  "as number of replications increases")
    ax1.grid(alpha=0.3)
    ax1.legend()
    fig1.tight_layout()
    fig1.savefig(os.path.join(PLOT_DIR, "replication_justification.png"),
                 dpi=150, bbox_inches="tight")

    ax2.set_xlabel("Number of replications R")
    ax2.set_ylabel("Relative CI half-width  (%)")
    ax2.set_title("Replication justification – CI half-width "
                  "as a percentage of the running mean")
    ax2.axhline(5.0, color="grey", ls="--", lw=1, label="5 % reference")
    ax2.grid(alpha=0.3)
    ax2.legend()
    fig2.tight_layout()
    fig2.savefig(os.path.join(PLOT_DIR, "replication_halfwidth.png"),
                 dpi=150, bbox_inches="tight")

    plt.close(fig1)
    plt.close(fig2)
    print(f"Saved: {os.path.join(PLOT_DIR, 'replication_justification.png')}")
    print(f"Saved: {os.path.join(PLOT_DIR, 'replication_halfwidth.png')}")

    # Summary statistics at R = 100
    print("\nSummary at R = 100:")
    for fname, label, _ in DATASETS:
        path = os.path.join(RESULTS_DIR, fname)
        if not os.path.exists(path):
            continue
        df = pd.read_csv(path)
        values = df["objective"].values
        R = len(values)
        m = values.mean()
        s = values.std(ddof=1)
        t = stats.t.ppf(1 - ALPHA / 2, df=R - 1)
        hw = t * s / np.sqrt(R)
        print(f"  {label}")
        print(f"    mean={m:.5f}  sd={s:.5f}  R={R}  CI halfwidth={hw:.5f} "
              f"({100 * hw / m:.3f} % of mean)")


if __name__ == "__main__":
    main()
