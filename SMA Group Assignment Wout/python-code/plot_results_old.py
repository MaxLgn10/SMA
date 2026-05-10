"""Create graphs from the CSV files produced by the C++ simulation.

Expected input files:
  ../results/warmup_analysis.csv
  ../results/experiment_results.csv

Generated plots are saved in:
  ../results/plots/
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR / "results"
PLOT_DIR = RESULTS_DIR / "plots"
EXPERIMENT_FILE = RESULTS_DIR / "experiment_results.csv"
WARMUP_FILE = RESULTS_DIR / "warmup_analysis.csv"

RULE_LABELS = {
    1: "Rule 1 - FCFS",
    2: "Rule 2 - Bailey-Welch",
    3: "Rule 3 - Blocking",
    4: "Rule 4 - Benchmarking",
}

STRATEGY_LABELS = {
    1: "Strategy 1 - end of sessions",
    2: "Strategy 2 - evenly distributed",
    3: "Strategy 3 - after elective blocks",
}


def save_current(name):
    path = PLOT_DIR / name
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved {path}")


def plot_warmup():
    if not WARMUP_FILE.exists():
        print(f"Skipping warmup plot: {WARMUP_FILE} not found")
        return
    df = pd.read_csv(WARMUP_FILE)
    plt.figure(figsize=(9, 4.5))
    plt.plot(df["week"], df["avg_objective"], marker="o", markersize=2, linewidth=1, label="weekly objective")
    smooth = df["avg_objective"].rolling(window=10, center=True, min_periods=1).mean()
    plt.plot(df["week"], smooth, linewidth=2, label="10-week moving average")
    plt.axvline(10, linestyle="--", linewidth=1, label="suggested warmup = 10 weeks")
    plt.xlabel("Week")
    plt.ylabel("Objective value")
    plt.title("Warmup analysis")
    plt.grid(axis="y", alpha=0.3)
    plt.legend()
    save_current("warmup_plot.png")


def plot_heatmaps(df):
    for strategy in sorted(df["strategy"].unique()):
        sub = df[df["strategy"] == strategy]
        pivot = sub.pivot(index="n_urgent", columns="rule", values="mean_objective").sort_index(ascending=False)
        plt.figure(figsize=(7, 6))
        image = plt.imshow(pivot.values, aspect="auto")
        plt.colorbar(image, label="Objective value")
        plt.xticks(np.arange(len(pivot.columns)), [RULE_LABELS[int(c)] for c in pivot.columns], rotation=25, ha="right")
        plt.yticks(np.arange(len(pivot.index)), [f"N={int(n)}" for n in pivot.index])
        plt.xlabel("Scheduling rule")
        plt.ylabel("Reserved urgent slots per week")
        plt.title(f"Objective heatmap - {STRATEGY_LABELS[int(strategy)]}")
        for row in range(pivot.shape[0]):
            for col in range(pivot.shape[1]):
                plt.text(col, row, f"{pivot.values[row, col]:.3f}", ha="center", va="center", fontsize=8)
        save_current(f"heatmap_S{int(strategy)}.png")


def plot_lines(df):
    for strategy in sorted(df["strategy"].unique()):
        sub = df[df["strategy"] == strategy]
        plt.figure(figsize=(8, 4.5))
        for rule in sorted(sub["rule"].unique()):
            r = sub[sub["rule"] == rule].sort_values("n_urgent")
            plt.plot(r["n_urgent"], r["mean_objective"], marker="o", label=RULE_LABELS[int(rule)])
            plt.fill_between(r["n_urgent"], r["ci_lo_objective"], r["ci_hi_objective"], alpha=0.15)
        plt.xlabel("Reserved urgent slots per week")
        plt.ylabel("Objective value")
        plt.title(f"Objective vs urgent capacity - {STRATEGY_LABELS[int(strategy)]}")
        plt.xticks(range(10, 21))
        plt.grid(axis="y", alpha=0.3)
        plt.legend(fontsize=8)
        save_current(f"lineplot_S{int(strategy)}.png")


def plot_top10(df):
    top = df.nsmallest(10, "mean_objective").copy()
    labels = [f"S{int(r.strategy)} N={int(r.n_urgent)} R{int(r.rule)}" for _, r in top.iterrows()]
    lower = top["mean_objective"] - top["ci_lo_objective"]
    upper = top["ci_hi_objective"] - top["mean_objective"]
    plt.figure(figsize=(9, 5))
    plt.barh(labels[::-1], top["mean_objective"].values[::-1], xerr=[lower.values[::-1], upper.values[::-1]], capsize=4)
    plt.xlabel("Objective value")
    plt.title("Top 10 configurations with 95% confidence intervals")
    plt.grid(axis="x", alpha=0.3)
    save_current("top10_barplot.png")


def plot_strategy_comparison(df):
    best = df.loc[df.groupby(["strategy", "rule"])["mean_objective"].idxmin()].copy()
    strategies = sorted(best["strategy"].unique())
    rules = sorted(best["rule"].unique())
    x = np.arange(len(strategies))
    width = 0.18
    plt.figure(figsize=(9, 5))
    for idx, rule in enumerate(rules):
        y = []
        err_low = []
        err_high = []
        for strategy in strategies:
            row = best[(best["strategy"] == strategy) & (best["rule"] == rule)].iloc[0]
            y.append(row["mean_objective"])
            err_low.append(row["mean_objective"] - row["ci_lo_objective"])
            err_high.append(row["ci_hi_objective"] - row["mean_objective"])
        offset = (idx - (len(rules) - 1) / 2) * width
        plt.bar(x + offset, y, width, yerr=[err_low, err_high], capsize=3, label=RULE_LABELS[int(rule)])
    plt.xticks(x, [f"S{int(s)}" for s in strategies])
    plt.xlabel("Strategy")
    plt.ylabel("Best objective value")
    plt.title("Best N per strategy and rule")
    plt.grid(axis="y", alpha=0.3)
    plt.legend(fontsize=8)
    save_current("strategy_comparison.png")


def main():
    if not EXPERIMENT_FILE.exists():
        raise SystemExit(f"Missing {EXPERIMENT_FILE}. Run the C++ experiment first.")
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    experiment = pd.read_csv(EXPERIMENT_FILE)
    plot_warmup()
    plot_heatmaps(experiment)
    plot_lines(experiment)
    plot_top10(experiment)
    plot_strategy_comparison(experiment)
    print(f"All plots saved to {PLOT_DIR}")


if __name__ == "__main__":
    main()
