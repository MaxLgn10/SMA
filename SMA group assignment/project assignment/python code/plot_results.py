"""
Visualisation of experiment results.

Generates the following plots (saved to ../results/plots/):
  1. warmup_plot.png        - Objective value vs week (warm-up analysis)
  2. heatmap_S1/2/3.png     - Objective value heatmap (N x Rule) per strategy
  3. lineplot_S1/2/3.png    - Objective vs N, one line per Rule, per strategy
  4. top10_barplot.png      - Top 10 configurations with 95% CI
  5. strategy_comparison.png- Best config per strategy, all Rules, side-by-side
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import os

# --- Paths -------------------------------------------------------------------
RESULTS_FILE  = "../results/experiment_results.csv"
WARMUP_FILE   = "../results/warmup_analysis.csv"
PLOT_DIR      = "../results/plots"
# -----------------------------------------------------------------------------

RULE_LABELS = {1: "Rule 1\n(FCFS)", 2: "Rule 2\n(Bailey-Welch)",
               3: "Rule 3\n(Blocking)", 4: "Rule 4\n(Benchmarking)"}
STRATEGY_LABELS = {1: "Strategy 1 – End of session",
                   2: "Strategy 2 – Evenly distributed",
                   3: "Strategy 3 – After every block"}
RULE_COLORS = {1: "#4C72B0", 2: "#DD8452", 3: "#55A868", 4: "#C44E52"}


def save(fig, filename):
    path = os.path.join(PLOT_DIR, filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


# ── 1. Warm-up plot ──────────────────────────────────────────────────────────
def plot_warmup(df_w):
    fig, ax = plt.subplots(figsize=(9, 4))

    ax.plot(df_w["week"], df_w["avg_objective"], color="#4C72B0", lw=1.5, label="Weekly avg")

    # Smoothed moving average (window = 10)
    smooth = df_w["avg_objective"].rolling(10, center=True).mean()
    ax.plot(df_w["week"], smooth, color="#C44E52", lw=2, label="Moving avg (w=10)")

    ax.axvline(10, color="grey", lw=1.2, ls="--", label="Warm-up = 10 weeks")
    ax.set_xlabel("Week")
    ax.set_ylabel("Objective value")
    ax.set_title("Warm-up analysis – Objective value per week\n"
                 "(Strategy 1, N=14, Rule 1  |  50 replications)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    save(fig, "warmup_plot.png")


# ── 2. Heatmaps (one per strategy) ───────────────────────────────────────────
def plot_heatmaps(df):
    for s in [1, 2, 3]:
        sub = df[df["strategy"] == s].copy()
        pivot = sub.pivot(index="n_urgent", columns="rule", values="mean_objective")
        pivot.columns = [RULE_LABELS[c].replace("\n", " ") for c in pivot.columns]
        pivot = pivot.sort_index(ascending=False)

        fig, ax = plt.subplots(figsize=(7, 6))
        im = ax.imshow(pivot.values, aspect="auto", cmap="RdYlGn_r")
        plt.colorbar(im, ax=ax, label="Objective value")

        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels(pivot.columns, fontsize=9)
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([f"N={n}" for n in pivot.index])
        ax.set_title(f"Objective value heatmap\n{STRATEGY_LABELS[s]}")
        ax.set_xlabel("Scheduling rule")
        ax.set_ylabel("Number of urgent slots")

        # Annotate cells
        vmin, vmax = pivot.values.min(), pivot.values.max()
        for i in range(pivot.shape[0]):
            for j in range(pivot.shape[1]):
                val = pivot.values[i, j]
                color = "white" if (val - vmin) / (vmax - vmin) > 0.7 else "black"
                ax.text(j, i, f"{val:.3f}", ha="center", va="center",
                        fontsize=8, color=color)

        fig.tight_layout()
        save(fig, f"heatmap_S{s}.png")


# ── 3. Line plots (one per strategy) ─────────────────────────────────────────
def plot_lineplots(df):
    for s in [1, 2, 3]:
        sub = df[df["strategy"] == s]
        fig, ax = plt.subplots(figsize=(8, 4.5))

        for rule in [1, 2, 3, 4]:
            r = sub[sub["rule"] == rule].sort_values("n_urgent")
            ax.plot(r["n_urgent"], r["mean_objective"],
                    marker="o", lw=1.8, ms=5,
                    color=RULE_COLORS[rule],
                    label=RULE_LABELS[rule].replace("\n", " "))
            ax.fill_between(r["n_urgent"],
                            r["ci_lo_objective"], r["ci_hi_objective"],
                            alpha=0.12, color=RULE_COLORS[rule])

        ax.set_xlabel("Number of urgent slots (N)")
        ax.set_ylabel("Objective value")
        ax.set_title(f"Objective value vs. N  –  {STRATEGY_LABELS[s]}")
        ax.set_xticks(range(10, 21))
        ax.legend(loc="upper left", fontsize=8)
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        save(fig, f"lineplot_S{s}.png")


# ── 4. Top-10 bar plot ────────────────────────────────────────────────────────
def plot_top10(df):
    top = df.nsmallest(10, "mean_objective").copy()
    top["label"] = top.apply(
        lambda r: f"S{int(r.strategy)} N={int(r.n_urgent)} R{int(r.rule)}", axis=1)
    top["err_lo"] = top["mean_objective"] - top["ci_lo_objective"]
    top["err_hi"] = top["ci_hi_objective"] - top["mean_objective"]

    fig, ax = plt.subplots(figsize=(10, 5))
    colors = [RULE_COLORS[int(r)] for r in top["rule"]]
    bars = ax.barh(top["label"][::-1], top["mean_objective"][::-1],
                   xerr=[top["err_lo"][::-1], top["err_hi"][::-1]],
                   color=colors[::-1], capsize=4, edgecolor="white", height=0.6)

    # Legend for rules
    from matplotlib.patches import Patch
    handles = [Patch(color=RULE_COLORS[r], label=RULE_LABELS[r].replace("\n", " "))
               for r in [1, 2, 3, 4]]
    ax.legend(handles=handles, fontsize=8, loc="lower right")

    xmin = (top["ci_lo_objective"].min() * 0.998)
    xmax = (top["ci_hi_objective"].max() * 1.002)
    ax.set_xlim(xmin, xmax)
    ax.set_xlabel("Objective value  (lower is better)")
    ax.set_title("Top 10 configurations by objective value  (with 95% CI)")
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.4f"))
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    save(fig, "top10_barplot.png")


# ── 5. Strategy comparison (best N per strategy, all rules) ──────────────────
def plot_strategy_comparison(df):
    # For each (strategy, rule): pick the N with lowest objective
    best = df.loc[df.groupby(["strategy", "rule"])["mean_objective"].idxmin()].copy()

    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(3)
    width = 0.18
    offsets = [-1.5, -0.5, 0.5, 1.5]

    for idx, rule in enumerate([1, 2, 3, 4]):
        vals = [best[(best.strategy == s) & (best.rule == rule)]["mean_objective"].values[0]
                for s in [1, 2, 3]]
        err_lo = [best[(best.strategy == s) & (best.rule == rule)]["mean_objective"].values[0]
                  - best[(best.strategy == s) & (best.rule == rule)]["ci_lo_objective"].values[0]
                  for s in [1, 2, 3]]
        err_hi = [best[(best.strategy == s) & (best.rule == rule)]["ci_hi_objective"].values[0]
                  - best[(best.strategy == s) & (best.rule == rule)]["mean_objective"].values[0]
                  for s in [1, 2, 3]]
        ax.bar(x + offsets[idx] * width, vals, width,
               yerr=[err_lo, err_hi], capsize=3,
               color=RULE_COLORS[rule], label=RULE_LABELS[rule].replace("\n", " "),
               edgecolor="white")

    ax.set_xticks(x)
    ax.set_xticklabels([f"S{s}\n{STRATEGY_LABELS[s].split('–')[1].strip()}"
                        for s in [1, 2, 3]], fontsize=9)
    ax.set_ylabel("Best objective value  (lower is better)")
    ax.set_title("Best configuration per strategy and rule  (with 95% CI)\n"
                 "Each bar uses the optimal N for that strategy–rule combination")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    save(fig, "strategy_comparison.png")


# ── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    os.makedirs(PLOT_DIR, exist_ok=True)

    print("Loading data...")
    df   = pd.read_csv(RESULTS_FILE)
    df_w = pd.read_csv(WARMUP_FILE)

    print("Generating plots...")
    plot_warmup(df_w)
    plot_heatmaps(df)
    plot_lineplots(df)
    plot_top10(df)
    plot_strategy_comparison(df)

    print(f"\nAll plots saved to: {os.path.abspath(PLOT_DIR)}/")
