"""
Statistical analysis and plot generation.

Reads results/summary_table.csv and results/raw_results.csv (produced by full_factorial.py)
and generates:
  - results/main_effects_plot.png
  - results/interaction_plot.png
  - results/anova_summary.txt

Usage:
    cd "SMA Group Assignment Cedric"
    python -m experiments.analysis
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import statsmodels.formula.api as smf
from statsmodels.stats.anova import anova_lm

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")

sns.set_theme(style="whitegrid", palette="muted")


# ---- Main effects plot ----

def plot_main_effects(summary_df: pd.DataFrame):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    factors = [
        ("n_urgent",  "Urgent slots / week",          [10, 12, 14, 16, 18, 20]),
        ("strategy",  "Timing strategy",               [1, 2, 3]),
        ("rule",      "Appointment rule",              [1, 2, 3, 4]),
    ]
    rule_labels = {1: "R1 FCFS", 2: "R2 Bailey-Welch", 3: "R3 Blocking", 4: "R4 Benchmark"}
    strategy_labels = {1: "S1 End-of-block", 2: "S2 Uniform", 3: "S3 After-6"}

    for ax, (col, xlabel, levels) in zip(axes, factors):
        grp = summary_df.groupby(col)["objective_mean"].agg(["mean", "sem"]).reset_index()
        grp = grp[grp[col].isin(levels)]
        ax.errorbar(
            grp[col], grp["mean"], yerr=1.96 * grp["sem"],
            marker="o", capsize=4, linewidth=2, markersize=6
        )
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Weighted objective W")
        ax.set_xticks(levels)
        if col == "rule":
            ax.set_xticklabels([rule_labels[r] for r in levels], rotation=20, ha="right")
        elif col == "strategy":
            ax.set_xticklabels([strategy_labels[s] for s in levels])

    fig.suptitle("Main Effects on Weighted Objective W", fontsize=14, fontweight="bold")
    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "main_effects_plot.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Main effects plot saved: {path}")


# ---- Interaction plots ----

def plot_interactions(summary_df: pd.DataFrame):
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Interaction 1: n_urgent × strategy
    pivot1 = summary_df.groupby(["n_urgent", "strategy"])["objective_mean"].mean().reset_index()
    for s, grp in pivot1.groupby("strategy"):
        axes[0].plot(grp["n_urgent"], grp["objective_mean"], marker="o",
                     label=f"S{s}", linewidth=2)
    axes[0].set_xlabel("Urgent slots / week")
    axes[0].set_ylabel("Mean W")
    axes[0].set_title("n_urgent × Strategy")
    axes[0].legend(title="Strategy")

    # Interaction 2: n_urgent × rule
    pivot2 = summary_df.groupby(["n_urgent", "rule"])["objective_mean"].mean().reset_index()
    rule_names = {1: "FCFS", 2: "Bailey-Welch", 3: "Blocking", 4: "Benchmark"}
    for r, grp in pivot2.groupby("rule"):
        axes[1].plot(grp["n_urgent"], grp["objective_mean"], marker="s",
                     label=rule_names[r], linewidth=2)
    axes[1].set_xlabel("Urgent slots / week")
    axes[1].set_ylabel("Mean W")
    axes[1].set_title("n_urgent × Appointment Rule")
    axes[1].legend(title="Rule")

    # Interaction 3: strategy × rule
    pivot3 = summary_df.groupby(["strategy", "rule"])["objective_mean"].mean().reset_index()
    strat_names = {1: "End-of-block", 2: "Uniform", 3: "After-6"}
    for s, grp in pivot3.groupby("strategy"):
        axes[2].plot(grp["rule"], grp["objective_mean"], marker="^",
                     label=strat_names[s], linewidth=2)
    axes[2].set_xlabel("Appointment rule")
    axes[2].set_ylabel("Mean W")
    axes[2].set_title("Strategy × Appointment Rule")
    axes[2].set_xticks([1, 2, 3, 4])
    axes[2].set_xticklabels(["FCFS", "Bailey-W", "Blocking", "Benchmark"])
    axes[2].legend(title="Strategy")

    fig.suptitle("Interaction Effects on Weighted Objective W", fontsize=14, fontweight="bold")
    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "interaction_plot.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Interaction plot saved: {path}")


# ---- ANOVA ----

def run_anova(raw_df: pd.DataFrame) -> str:
    """
    Three-way ANOVA on the weighted objective using statsmodels.
    Factors: n_urgent (numeric treated as categorical), strategy, rule.
    """
    df = raw_df.copy()
    df["n_urgent_c"] = df["n_urgent"].astype(str)
    df["strategy_c"] = df["strategy"].astype(str)
    df["rule_c"] = df["rule"].astype(str)

    formula = (
        "objective ~ C(n_urgent_c) + C(strategy_c) + C(rule_c)"
        " + C(n_urgent_c):C(strategy_c)"
        " + C(n_urgent_c):C(rule_c)"
        " + C(strategy_c):C(rule_c)"
    )
    model = smf.ols(formula, data=df).fit()
    table = anova_lm(model, typ=2)

    lines = [
        "=" * 60,
        "Factorial ANOVA - Weighted Objective W",
        "=" * 60,
        table.to_string(),
        "",
        f"R^2 = {model.rsquared:.4f}",
        f"Adj-R^2 = {model.rsquared_adj:.4f}",
    ]
    text = "\n".join(lines)

    path = os.path.join(RESULTS_DIR, "anova_summary.txt")
    with open(path, "w") as f:
        f.write(text)
    print(f"ANOVA summary saved: {path}")
    return text


def run_blocked_anova(raw_df: pd.DataFrame) -> str:
    """
    Factorial ANOVA on replication-level output with replication index as a CRN block.
    This matches the experiment design because all configurations share replication IDs.
    """
    df = raw_df.copy()
    rep_col = "replication_id" if "replication_id" in df.columns else "rep"
    df["n_urgent_c"] = df["n_urgent"].astype(str)
    df["strategy_c"] = df["strategy"].astype(str)
    df["rule_c"] = df["rule"].astype(str)
    df["replication_c"] = df[rep_col].astype(str)

    formula = (
        "objective ~ C(n_urgent_c) * C(strategy_c) * C(rule_c)"
        " + C(replication_c)"
    )
    model = smf.ols(formula, data=df).fit()
    table = anova_lm(model, typ=2)

    lines = [
        "=" * 60,
        "Blocked Factorial ANOVA - Weighted Objective W",
        "=" * 60,
        "Model: W ~ C(n_urgent) * C(strategy) * C(rule) + C(replication_id)",
        table.to_string(),
        "",
        f"R^2 = {model.rsquared:.4f}",
        f"Adj-R^2 = {model.rsquared_adj:.4f}",
    ]
    text = "\n".join(lines)

    path = os.path.join(RESULTS_DIR, "blocked_anova_summary.txt")
    with open(path, "w") as f:
        f.write(text)
    print(f"Blocked ANOVA summary saved: {path}")
    return text


def t_ci(vals: pd.Series | np.ndarray, alpha: float = 0.05) -> dict:
    arr = np.asarray(vals, dtype=float)
    n = len(arr)
    mean = float(np.mean(arr))
    sd = float(np.std(arr, ddof=1)) if n > 1 else 0.0
    tcrit = float(stats.t.ppf(1 - alpha / 2, n - 1)) if n > 1 else 0.0
    half_width = tcrit * sd / np.sqrt(n) if n > 1 else 0.0
    return {
        "n": n,
        "mean": mean,
        "std": sd,
        "tcrit": tcrit,
        "half_width": float(half_width),
        "ci_low": mean - half_width,
        "ci_high": mean + half_width,
        "relative_half_width_pct": float(half_width / abs(mean) * 100) if mean else np.nan,
    }


def paired_ttest_crn(raw_df: pd.DataFrame, a: tuple[int, int, int], b: tuple[int, int, int],
                     metric: str = "objective", adjust: int | None = None) -> dict:
    """Paired CRN t-test for config a minus config b using common replication IDs."""
    rep_col = "replication_id" if "replication_id" in raw_df.columns else "rep"
    a_df = raw_df.query("n_urgent == @a[0] and strategy == @a[1] and rule == @a[2]").set_index(rep_col)
    b_df = raw_df.query("n_urgent == @b[0] and strategy == @b[1] and rule == @b[2]").set_index(rep_col)
    common = sorted(set(a_df.index) & set(b_df.index))
    diff = a_df.loc[common, metric] - b_df.loc[common, metric]
    test = stats.ttest_1samp(diff, 0.0)
    ci = t_ci(diff)
    p_adj = min(float(test.pvalue) * adjust, 1.0) if adjust else float(test.pvalue)
    return {
        "config_a": f"n={a[0]}, S{a[1]}, R{a[2]}",
        "config_b": f"n={b[0]}, S{b[1]}, R{b[2]}",
        "metric": metric,
        "n_pairs": len(common),
        "mean_diff_a_minus_b": ci["mean"],
        "ci_low": ci["ci_low"],
        "ci_high": ci["ci_high"],
        "t_stat": float(test.statistic),
        "raw_p_value": float(test.pvalue),
        "adjustment_multiplier": adjust or 1,
        "adjusted_p_value": p_adj,
    }


# ---- KPI heatmaps ----

def plot_kpi_heatmaps(summary_df: pd.DataFrame):
    """
    For each appointment rule, plot a heatmap of the weighted objective
    over (n_urgent × strategy).
    """
    rules = [1, 2, 3, 4]
    rule_names = {1: "FCFS", 2: "Bailey-Welch", 3: "Blocking", 4: "Benchmark"}
    fig, axes = plt.subplots(1, 4, figsize=(20, 4))

    for ax, r in zip(axes, rules):
        sub = summary_df[summary_df["rule"] == r]
        pivot = sub.pivot(index="strategy", columns="n_urgent", values="objective_mean")
        sns.heatmap(
            pivot, ax=ax, annot=True, fmt=".3f", cmap="YlOrRd",
            cbar=True, linewidths=0.5,
        )
        ax.set_title(f"Rule {r}: {rule_names[r]}")
        ax.set_xlabel("Urgent slots / week")
        ax.set_ylabel("Strategy")
        ax.set_yticklabels(["S1 End-block", "S2 Uniform", "S3 After-6"], rotation=0)

    fig.suptitle("Weighted Objective W by Configuration", fontsize=14, fontweight="bold")
    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "heatmap_objective.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Heatmap saved: {path}")


# ---- Line plot: objective per strategy vs n_urgent (like Part 2) ----

def plot_lines_per_strategy(summary_df: pd.DataFrame):
    """One line per strategy, x=n_urgent, y=mean W with 95% CI band."""
    strat_names = {1: "S1 End-of-block", 2: "S2 Uniform", 3: "S3 After-6"}
    colors = {1: "#e07b39", 2: "#3a7ebf", 3: "#4cae4c"}

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    kpis = [
        ("objective_mean",    "objective_ci_low",    "objective_ci_high",    "Weighted objective W"),
        ("awt_e_hours_mean",  "awt_e_hours_ci_low",  "awt_e_hours_ci_high",  "AWT_e (hours)"),
        ("swt_u_min_mean",    "swt_u_min_ci_low",    "swt_u_min_ci_high",    "SWT_u (minutes)"),
    ]

    for ax, (mean_col, lo_col, hi_col, ylabel) in zip(axes, kpis):
        for s in [1, 2, 3]:
            grp = summary_df[summary_df.strategy == s].groupby("n_urgent").agg(
                mean=(mean_col, "mean"),
                lo=(lo_col, "mean"),
                hi=(hi_col, "mean"),
            ).reset_index()
            ax.plot(grp["n_urgent"], grp["mean"], marker="o",
                    label=strat_names[s], color=colors[s], linewidth=2)
            ax.fill_between(grp["n_urgent"], grp["lo"], grp["hi"],
                            alpha=0.15, color=colors[s])
        ax.set_xlabel("Urgent slots / week")
        ax.set_ylabel(ylabel)
        ax.set_xticks([10, 12, 14, 16, 18, 20])
        ax.legend(title="Strategy")
        ax.grid(True, alpha=0.3)

    fig.suptitle("KPIs per Timing Strategy vs Urgent Slot Count", fontsize=14, fontweight="bold")
    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "lines_per_strategy.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Lines-per-strategy plot saved: {path}")


# ---- Box plot: appointment rule comparison ----

def plot_rule_boxplot(raw_df: pd.DataFrame):
    """Box plot of per-replication objective grouped by appointment rule."""
    rule_labels = {1: "R1\nFCFS", 2: "R2\nBailey-Welch", 3: "R3\nBlocking", 4: "R4\nBenchmark"}
    raw_df = raw_df.copy()
    raw_df["rule_label"] = raw_df["rule"].map(rule_labels)

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    cols = [
        ("objective",    "Weighted objective W"),
        ("awt_e_hours",  "AWT_e (hours)"),
        ("swt_u_min",    "SWT_u (minutes)"),
    ]

    for ax, (col, ylabel) in zip(axes, cols):
        order = [rule_labels[r] for r in [1, 2, 3, 4]]
        sns.boxplot(data=raw_df, x="rule_label", y=col, order=order,
                    hue="rule_label", legend=False,
                    palette="muted", ax=ax, width=0.5, fliersize=2)
        ax.set_xlabel("Appointment rule")
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=0.3)

    fig.suptitle("Effect of Appointment Rule on KPIs", fontsize=14, fontweight="bold")
    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "rule_boxplot.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Rule boxplot saved: {path}")


# ---- Top-10 horizontal bar chart with CI ----

def plot_top10_bar(summary_df: pd.DataFrame):
    top10 = summary_df.nsmallest(10, "objective_mean").copy()
    top10["label"] = top10.apply(
        lambda r: f"n={int(r.n_urgent)}, S{int(r.strategy)}, R{int(r.rule)}", axis=1
    )
    top10 = top10.iloc[::-1]  # reverse for bottom-to-top ordering

    errors = top10["objective_ci_high"] - top10["objective_mean"]

    fig, ax = plt.subplots(figsize=(9, 6))
    bars = ax.barh(top10["label"], top10["objective_mean"],
                   xerr=errors, capsize=4, color="#3a7ebf", alpha=0.8,
                   error_kw={"elinewidth": 1.5, "capthick": 1.5})
    ax.axvline(
        summary_df[(summary_df.n_urgent == 14) & (summary_df.strategy == 1) &
                   (summary_df.rule == 1)]["objective_mean"].values[0],
        color="red", linestyle="--", linewidth=1.5, label="Baseline (14, S1, R1)"
    )
    ax.set_xlabel("Weighted objective W (mean ± 95% CI)")
    ax.set_title("Top-10 Configurations by Weighted Objective", fontweight="bold")
    ax.legend()
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "top10_bar.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Top-10 bar chart saved: {path}")


# ---- Pareto: AWT_e vs SWT_u trade-off ----

def plot_pareto_tradeoff(summary_df: pd.DataFrame):
    """Scatter of AWT_e vs SWT_u for all 72 configs, coloured by n_urgent."""
    fig, ax = plt.subplots(figsize=(9, 6))

    scatter = ax.scatter(
        summary_df["awt_e_hours_mean"],
        summary_df["swt_u_min_mean"],
        c=summary_df["n_urgent"], cmap="plasma",
        s=60, alpha=0.7, edgecolors="k", linewidths=0.4,
    )
    cb = plt.colorbar(scatter, ax=ax)
    cb.set_label("n_urgent")

    # Highlight Pareto front (non-dominated)
    df = summary_df[["awt_e_hours_mean", "swt_u_min_mean",
                      "n_urgent", "strategy", "rule"]].copy()
    pareto_mask = np.ones(len(df), dtype=bool)
    for i, row in df.iterrows():
        if any(
            (df["awt_e_hours_mean"] <= row["awt_e_hours_mean"]) &
            (df["swt_u_min_mean"] <= row["swt_u_min_mean"]) &
            (
                (df["awt_e_hours_mean"] < row["awt_e_hours_mean"]) |
                (df["swt_u_min_mean"] < row["swt_u_min_mean"])
            )
        ):
            pareto_mask[i] = False

    front = df[pareto_mask].sort_values("awt_e_hours_mean")
    ax.plot(front["awt_e_hours_mean"], front["swt_u_min_mean"],
            "r--o", markersize=8, linewidth=1.5, label="Pareto front",
            markerfacecolor="red", markeredgecolor="k")

    # Baseline
    bl = summary_df[(summary_df.n_urgent == 14) & (summary_df.strategy == 1) & (summary_df.rule == 1)]
    ax.scatter(bl["awt_e_hours_mean"], bl["swt_u_min_mean"],
               marker="*", s=300, color="green", zorder=5, label="Baseline")

    ax.set_xlabel("AWT_e (hours)")
    ax.set_ylabel("SWT_u (minutes)")
    ax.set_title("Pareto Trade-off: AWT_e vs SWT_u", fontweight="bold")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "pareto_tradeoff.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Pareto trade-off plot saved: {path}")


# ---- Per-KPI breakdown: show what drives the objective ----

def plot_kpi_breakdown(summary_df: pd.DataFrame):
    """Stacked contribution of AWT_e and SWT_u to W, grouped by n_urgent."""
    grp = summary_df.groupby("n_urgent").agg(
        awt_contrib=("awt_e_hours_mean", lambda x: (x / 168).mean()),
        swt_contrib=("swt_u_min_mean", lambda x: (x / 60 / 9).mean()),
    ).reset_index()

    x = np.arange(len(grp))
    w = 0.5
    fig, ax = plt.subplots(figsize=(9, 5))
    bars1 = ax.bar(x, grp["awt_contrib"], w, label="AWT_e contribution (÷168)", color="#3a7ebf")
    bars2 = ax.bar(x, grp["swt_contrib"], w, bottom=grp["awt_contrib"],
                   label="SWT_u contribution (÷9÷60)", color="#e07b39")
    ax.set_xticks(x)
    ax.set_xticklabels([str(int(v)) for v in grp["n_urgent"]])
    ax.set_xlabel("Urgent slots / week")
    ax.set_ylabel("Contribution to W")
    ax.set_title("Decomposition of Weighted Objective W by n_urgent", fontweight="bold")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, "kpi_breakdown.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"KPI breakdown plot saved: {path}")


def main():
    summary_path = os.path.join(RESULTS_DIR, "summary_table.csv")
    raw_path = os.path.join(RESULTS_DIR, "raw_results.csv")

    if not os.path.exists(summary_path):
        print(f"ERROR: {summary_path} not found. Run full_factorial.py first.")
        sys.exit(1)

    summary_df = pd.read_csv(summary_path)
    raw_df = pd.read_csv(raw_path)

    print("Generating plots and statistical analysis...")
    plot_main_effects(summary_df)
    plot_interactions(summary_df)
    plot_kpi_heatmaps(summary_df)
    plot_lines_per_strategy(summary_df)
    plot_rule_boxplot(raw_df)
    plot_top10_bar(summary_df)
    plot_pareto_tradeoff(summary_df)
    plot_kpi_breakdown(summary_df)

    anova_text = run_anova(raw_df)
    blocked_anova_text = run_blocked_anova(raw_df)
    print("\n" + anova_text[:500] + "...")
    print("\n" + blocked_anova_text[:500] + "...")

    print("\nTop 10 configurations by weighted objective:")
    top10 = summary_df.nsmallest(10, "objective_mean")[
        ["n_urgent", "strategy", "rule", "objective_mean", "objective_ci_low", "objective_ci_high",
         "awt_e_hours_mean", "swt_u_min_mean"]
    ]
    print(top10.to_string(index=False))


if __name__ == "__main__":
    main()
