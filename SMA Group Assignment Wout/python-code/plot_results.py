"""Generate report figures and tables from the C++ simulation CSV output.

Checked and strengthened for academic reporting: robust CSV path handling,
data-validation diagnostics, corrected Top-10 bar labels, and added uncertainty
and metric-correlation figures.

Expected default layout:
    project/
    ├── python-code/plot_results.py
    └── results/
        ├── experiment_results.csv
        └── warmup_analysis.csv

Outputs:
    results/plots/
    results/tables/

Run:
    python3 plot_results.py

Optional:
    python3 plot_results.py --results-dir ../results
    python3 plot_results.py --experiment-file ../results/experiment_results.csv
"""

from __future__ import annotations

import argparse
import math
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from scipy import stats as scipy_stats
except Exception:
    scipy_stats = None


WEIGHT_ELECTIVE = 1.0 / 168.0
WEIGHT_URGENT = 1.0 / 9.0
WARMUP_CUTOFF_WEEK = 10
FIGURE_DPI = 200

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
DEFAULT_RESULTS_DIR = BASE_DIR / "results"
DEFAULT_RESULTS_V2_DIR = BASE_DIR / "results_v2"
DEFAULT_LOCAL_RESULTS_DIR = SCRIPT_DIR

RULE_LABELS = {
    1: "R1 - FCFS",
    2: "R2 - Bailey-Welch",
    3: "R3 - Blocking",
    4: "R4 - Benchmark",
    5: "R5 - BW K=3",
    6: "R6 - BW K=4",
    7: "R7 - BW K=5",
}

STRATEGY_LABELS = {
    1: "S1 - end of sessions",
    2: "S2 - evenly distributed",
    3: "S3 - after elective blocks",
}

COLUMN_ALIASES = {
    "strategy": "strategy",
    "nurgent": "n_urgent",
    "nurgentslots": "n_urgent",
    "reservedurgentslots": "n_urgent",
    "rule": "rule",
    "week": "week",
    "rep": "replication",
    "replication": "replication",
    "run": "replication",
    "r": "replication",

    "meanobjective": "W",
    "avgobjective": "W",
    "objective": "W",
    "w": "W",
    "cilowobjective": "W_lo",
    "ciloobjective": "W_lo",
    "cihiobjective": "W_hi",
    "cihighobjective": "W_hi",
    "cihiobj": "W_hi",
    "ciloobj": "W_lo",

    "meanelappwt": "AWT_e",
    "meanelectiveappwt": "AWT_e",
    "meanelectiveappointmentwt": "AWT_e",
    "meanelectiveappointmentwait": "AWT_e",
    "avgelappwthrs": "AWT_e",
    "electiveappwt": "AWT_e",
    "elappwt": "AWT_e",
    "awte": "AWT_e",
    "ciloelapp": "AWT_e_lo",
    "cilowelapp": "AWT_e_lo",
    "cihielapp": "AWT_e_hi",
    "cihighelapp": "AWT_e_hi",

    "meanurscanwt": "SWT_u",
    "meanurgentscanwt": "SWT_u",
    "meanurgentscanwait": "SWT_u",
    "avgurscanwthrs": "SWT_u",
    "urgentscanwt": "SWT_u",
    "urscanwt": "SWT_u",
    "swtu": "SWT_u",
    "cilourscan": "SWT_u_lo",
    "cilowurscan": "SWT_u_lo",
    "cihiurscan": "SWT_u_hi",
    "cihighurscan": "SWT_u_hi",

    "meanelscanwt": "SWT_e",
    "meanelectivescanwt": "SWT_e",
    "meanelectivescanwait": "SWT_e",
    "avgelscanwthrs": "SWT_e",
    "electivescanwt": "SWT_e",
    "elscanwt": "SWT_e",
    "swte": "SWT_e",

    "meanot": "OT",
    "meanotl": "OT",
    "avgothrs": "OT",
    "ot": "OT",
    "overtime": "OT",
    "meanovertime": "OT",
}


@dataclass(frozen=True)
class ConfigKey:
    strategy: int
    n_urgent: int
    rule: int


def norm_col(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name).strip().lower())


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for col in df.columns:
        key = norm_col(col)
        if key in COLUMN_ALIASES:
            rename[col] = COLUMN_ALIASES[key]

    out = df.rename(columns=rename).copy()

    duplicate_cols = out.columns[out.columns.duplicated()].unique().tolist()
    for col in duplicate_cols:
        same = out.loc[:, out.columns == col]
        merged = same.bfill(axis=1).iloc[:, 0]
        out = out.drop(columns=[col])
        out[col] = merged

    for col in out.columns:
        if col not in {"label", "config", "description"}:
            try:
                out[col] = pd.to_numeric(out[col])
            except (ValueError, TypeError):
                pass

    return out


def require_columns(df: pd.DataFrame, columns: Iterable[str], source: Path) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns in {source}: {missing}. "
            f"Available columns: {list(df.columns)}"
        )


def add_objective_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if "W" not in out.columns:
        require_columns(out, ["AWT_e", "SWT_u"], Path("experiment CSV"))
        out["W"] = WEIGHT_ELECTIVE * out["AWT_e"] + WEIGHT_URGENT * out["SWT_u"]
    elif {"AWT_e", "SWT_u"}.issubset(out.columns):
        out["W_recomputed"] = WEIGHT_ELECTIVE * out["AWT_e"] + WEIGHT_URGENT * out["SWT_u"]

    if {"AWT_e", "SWT_u"}.issubset(out.columns):
        out["AWT_e_contribution"] = WEIGHT_ELECTIVE * out["AWT_e"]
        out["SWT_u_contribution"] = WEIGHT_URGENT * out["SWT_u"]

    return out


def label_rule(rule: int | float) -> str:
    try:
        r = int(rule)
    except Exception:
        return str(rule)
    return RULE_LABELS.get(r, f"R{r}")


def label_strategy(strategy: int | float) -> str:
    try:
        s = int(strategy)
    except Exception:
        return str(strategy)
    return STRATEGY_LABELS.get(s, f"S{s}")


def config_key(row: pd.Series) -> ConfigKey:
    return ConfigKey(int(row["strategy"]), int(row["n_urgent"]), int(row["rule"]))


def config_label(row: pd.Series) -> str:
    return f"S{int(row['strategy'])}, N={int(row['n_urgent'])}, {label_rule(row['rule'])}"


def choose_existing_file(candidates: list[Path], description: str, required: bool = True) -> Path | None:
    for path in candidates:
        if path.exists():
            return path

    if required:
        raise FileNotFoundError(
            f"Could not find {description}. Tried:\n" + "\n".join(f"  - {p}" for p in candidates)
        )

    return None


def normal_two_sided_p(z: float) -> float:
    if not np.isfinite(z):
        return float("nan")
    return float(math.erfc(abs(z) / math.sqrt(2.0)))


def two_sided_t_p(t_value: float, df: int) -> float:
    if not np.isfinite(t_value) or df <= 0:
        return float("nan")

    if scipy_stats is not None:
        return float(2.0 * scipy_stats.t.sf(abs(t_value), df=df))

    return normal_two_sided_p(t_value)


def ci_to_se(row: pd.Series) -> float:
    if {"W_lo", "W_hi"}.issubset(row.index):
        half_width = (float(row["W_hi"]) - float(row["W_lo"])) / 2.0
        if np.isfinite(half_width) and half_width > 0:
            return half_width / 1.96

    return float("nan")


def pareto_mask(df: pd.DataFrame, objective_cols: list[str]) -> np.ndarray:
    values = df[objective_cols].astype(float).to_numpy()
    mask = np.ones(len(values), dtype=bool)

    for i, point in enumerate(values):
        if not np.all(np.isfinite(point)):
            mask[i] = False
            continue

        others = values[np.arange(len(values)) != i]
        finite_others = others[np.all(np.isfinite(others), axis=1)]

        if len(finite_others) == 0:
            continue

        dominated = np.any(
            np.all(finite_others <= point, axis=1)
            & np.any(finite_others < point, axis=1)
        )
        mask[i] = not dominated

    return mask


def save_figure(fig: plt.Figure, plots_dir: Path, filename: str) -> None:
    plots_dir.mkdir(parents=True, exist_ok=True)
    path = plots_dir / filename

    # tight_layout can warn for figures with colorbars or 3D axes; bbox_inches still
    # preserves the complete figure in the saved output. Some figures, such as
    # multi-panel heatmaps with a dedicated colorbar axis, use manual layout and
    # explicitly opt out of tight_layout to avoid colorbar overlap.
    if not getattr(fig, "_skip_tight_layout", False):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            try:
                fig.tight_layout()
            except Exception:
                pass

    fig.savefig(path, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


def save_table(df: pd.DataFrame, tables_dir: Path, basename: str, float_format: str = "%.4f") -> None:
    tables_dir.mkdir(parents=True, exist_ok=True)

    csv_path = tables_dir / f"{basename}.csv"
    tex_path = tables_dir / f"{basename}.tex"

    df.to_csv(csv_path, index=False)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df.to_latex(tex_path, index=False, escape=False, float_format=float_format)

    print(f"Saved {csv_path}")
    print(f"Saved {tex_path}")


def annotate_configurations(
    ax: plt.Axes,
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    max_labels: int = 12,
    ranking_col: str = "W",
) -> None:
    """Annotate a limited number of configurations to keep academic figures readable."""
    if df.empty:
        return

    if ranking_col in df.columns:
        label_df = df.nsmallest(min(max_labels, len(df)), ranking_col).copy()
    else:
        label_df = df.head(max_labels).copy()

    for _, row in label_df.iterrows():
        ax.annotate(
            f"S{int(row['strategy'])}/N{int(row['n_urgent'])}/R{int(row['rule'])}",
            (row[x_col], row[y_col]),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=7,
            alpha=0.85,
        )

    if len(df) > max_labels:
        ax.text(
            0.99,
            0.01,
            f"Labels shown for best {max_labels} efficient points by {ranking_col}",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=7,
            alpha=0.75,
        )


def load_experiment(path: Path) -> pd.DataFrame:
    df = standardize_columns(pd.read_csv(path))
    require_columns(df, ["strategy", "n_urgent", "rule", "AWT_e", "SWT_u", "OT"], path)

    df = add_objective_columns(df)

    for col in ["strategy", "n_urgent", "rule"]:
        df[col] = df[col].astype(int)

    return df.sort_values(["strategy", "n_urgent", "rule"]).reset_index(drop=True)


def validate_experiment(df: pd.DataFrame, source: Path) -> None:
    """Run lightweight data-integrity checks before plotting."""
    key_cols = ["strategy", "n_urgent", "rule"]
    duplicate_count = int(df.duplicated(key_cols).sum())
    if duplicate_count:
        raise ValueError(f"{source} contains {duplicate_count} duplicate strategy/n_urgent/rule rows.")

    metric_cols = [c for c in ["W", "AWT_e", "SWT_u", "SWT_e", "OT"] if c in df.columns]
    if df[key_cols + metric_cols].isna().any().any():
        missing = df[key_cols + metric_cols].isna().sum()
        raise ValueError(f"{source} contains missing values in required plotting columns: {missing.to_dict()}")

    for col in ["W", "AWT_e", "SWT_u", "OT"]:
        if col in df.columns and (df[col] < 0).any():
            raise ValueError(f"{source} contains negative values in {col}, which is unexpected for waiting-time outputs.")

    if "W_recomputed" in df.columns:
        max_abs_diff = float((df["W"] - df["W_recomputed"]).abs().max())
        print(f"Objective validation: max |reported W - recomputed W| = {max_abs_diff:.3e}")
        if max_abs_diff > 1e-6:
            warnings.warn(
                "Reported objective W differs from W recomputed from AWT_e and SWT_u. "
                "Check whether the CSV was generated with different objective weights.",
                RuntimeWarning,
            )

    print(
        "Design validation: "
        f"{len(df)} unique configurations; "
        f"strategies={sorted(map(int, df['strategy'].unique()))}; "
        f"n_urgent={int(df['n_urgent'].min())}-{int(df['n_urgent'].max())}; "
        f"rules={sorted(map(int, df['rule'].unique()))}"
    )


def load_warmup(path: Path | None) -> pd.DataFrame | None:
    if path is None or not path.exists():
        return None

    df = standardize_columns(pd.read_csv(path))

    if "W" not in df.columns and {"AWT_e", "SWT_u"}.issubset(df.columns):
        df["W"] = WEIGHT_ELECTIVE * df["AWT_e"] + WEIGHT_URGENT * df["SWT_u"]

    if "week" not in df.columns or "W" not in df.columns:
        print(f"Skipping Figure 1: {path} does not contain week/objective columns")
        return None

    return df.sort_values("week").reset_index(drop=True)


def load_replication_objectives(results_dir: Path) -> dict[ConfigKey, pd.Series]:
    replication_series: dict[ConfigKey, pd.Series] = {}
    pattern = re.compile(r"S(?P<strategy>\d+).*?N(?P<n_urgent>\d+).*?R(?P<rule>\d+)", re.IGNORECASE)

    for path in sorted(results_dir.glob("replication_analysis_*.csv")):
        match = pattern.search(path.stem)
        if not match:
            continue

        key = ConfigKey(
            int(match.group("strategy")),
            int(match.group("n_urgent")),
            int(match.group("rule")),
        )

        rep_df = standardize_columns(pd.read_csv(path))
        rep_df = add_objective_columns(rep_df)

        if "W" not in rep_df.columns:
            continue

        if "replication" in rep_df.columns:
            rep_index = rep_df["replication"].astype(int)
        else:
            rep_index = pd.RangeIndex(start=1, stop=len(rep_df) + 1, name="replication")

        replication_series[key] = pd.Series(rep_df["W"].astype(float).to_numpy(), index=rep_index, name=key)

    return replication_series


def add_spread_column(df: pd.DataFrame, replication_series: dict[ConfigKey, pd.Series]) -> pd.DataFrame:
    out = df.copy()
    spreads = []
    sources = []

    for _, row in out.iterrows():
        key = config_key(row)

        if key in replication_series and len(replication_series[key].dropna()) >= 2:
            spreads.append(float(replication_series[key].dropna().std(ddof=1)))
            sources.append("replication_sd")
        else:
            se = ci_to_se(row)
            if np.isfinite(se):
                spreads.append(se)
                sources.append("ci_se")
            else:
                spreads.append(float("nan"))
                sources.append("not_available")

    out["W_spread"] = spreads
    out["spread_source"] = sources

    if out["W_spread"].isna().all():
        out["W_spread"] = 0.0
    else:
        out["W_spread"] = out["W_spread"].fillna(out["W_spread"].median(skipna=True))

    return out


def plot_figure_1_welch(warmup: pd.DataFrame | None, plots_dir: Path) -> None:
    if warmup is None:
        print("Skipping Figure 1: warmup_analysis.csv not found or incomplete")
        return

    fig, ax = plt.subplots(figsize=(9, 4.8))

    ax.plot(
        warmup["week"],
        warmup["W"],
        marker="o",
        markersize=2.5,
        linewidth=1.0,
        label="Weekly mean W",
    )

    rolling = warmup["W"].rolling(window=10, center=True, min_periods=1).mean()
    ax.plot(warmup["week"], rolling, linewidth=2.0, label="10-week moving average")
    ax.axvline(
        WARMUP_CUTOFF_WEEK,
        linestyle="--",
        linewidth=1.2,
        label=f"Warm-up cut-off = week {WARMUP_CUTOFF_WEEK}",
    )

    ax.set_xlabel("Simulation week")
    ax.set_ylabel("Weighted objective W")
    ax.set_title("Figure 1 - Welch plot after corrected simulation")
    ax.grid(axis="y", alpha=0.3)
    ax.legend()

    save_figure(fig, plots_dir, "fig01_welch_plot.png")


def plot_figure_2_main_effects(df: pd.DataFrame, plots_dir: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))

    n_effect = df.groupby("n_urgent", as_index=False)["W"].mean()
    axes[0].plot(n_effect["n_urgent"], n_effect["W"], marker="o")
    axes[0].set_xlabel("Reserved urgent slots per week (n_urgent)")
    axes[0].set_ylabel("Mean Weighted Objective W")
    axes[0].set_title("Main effect: n_urgent")
    axes[0].set_xticks(sorted(df["n_urgent"].unique()))
    axes[0].grid(axis="y", alpha=0.3)

    s_effect = df.groupby("strategy", as_index=False)["W"].mean().sort_values("W")
    axes[1].bar([label_strategy(s) for s in s_effect["strategy"]], s_effect["W"])
    axes[1].set_xlabel("Strategy")
    axes[1].set_ylabel("Mean weighted objective W")
    axes[1].set_title("Main effect: strategy")
    axes[1].tick_params(axis="x", rotation=20)
    axes[1].grid(axis="y", alpha=0.3)

    r_effect = df.groupby("rule", as_index=False)["W"].mean().sort_values("W")
    axes[2].bar([label_rule(r) for r in r_effect["rule"]], r_effect["W"])
    axes[2].set_xlabel("Rule")
    axes[2].set_ylabel("Mean weighted objective W")
    axes[2].set_title("Main effect: rule")
    axes[2].tick_params(axis="x", rotation=20)
    axes[2].grid(axis="y", alpha=0.3)

    fig.suptitle("Figure 2 - Descriptive main effects on weighted objective W", y=1.03, fontsize=13)

    save_figure(fig, plots_dir, "fig02_main_effects.png")


def plot_figure_3_w_by_strategy_nurgent(df: pd.DataFrame, plots_dir: Path) -> None:
    best = df.loc[df.groupby(["strategy", "n_urgent"])["W"].idxmin()].copy()

    fig, ax = plt.subplots(figsize=(9, 5.2))

    for strategy in sorted(best["strategy"].unique()):
        sub = best[best["strategy"] == strategy].sort_values("n_urgent")
        line = ax.plot(
            sub["n_urgent"],
            sub["W"],
            marker="o",
            linewidth=1.8,
            label=label_strategy(strategy),
        )[0]

        if {"W_lo", "W_hi"}.issubset(sub.columns):
            ax.fill_between(
                sub["n_urgent"],
                sub["W_lo"],
                sub["W_hi"],
                color=line.get_color(),
                alpha=0.15,
            )

    ax.set_xlabel("Reserved urgent slots per week")
    ax.set_ylabel("Best W over rules")
    ax.set_title("Figure 3 - W per strategy per n_urgent")
    ax.set_xticks(sorted(best["n_urgent"].unique()))
    ax.grid(axis="y", alpha=0.3)
    ax.legend()

    save_figure(fig, plots_dir, "fig03_W_per_strategy_per_nurgent.png")


def plot_figure_4_top10(df: pd.DataFrame, plots_dir: Path) -> pd.DataFrame:
    top = df.nsmallest(10, "W").copy().reset_index(drop=True)
    top["rank"] = np.arange(1, len(top) + 1)
    top["configuration"] = top.apply(config_label, axis=1)

    labels = top["configuration"].tolist()

    fig, ax = plt.subplots(figsize=(10, 5.6))

    y = np.arange(len(top))[::-1]
    x = top["W"].to_numpy()[::-1]

    if {"W_lo", "W_hi"}.issubset(top.columns):
        lower = (top["W"] - top["W_lo"]).to_numpy()[::-1]
        upper = (top["W_hi"] - top["W"]).to_numpy()[::-1]
        ax.barh(y, x, xerr=[lower, upper], capsize=4)
    else:
        ax.barh(y, x)

    ax.set_yticks(y)
    ax.set_yticklabels(labels[::-1])
    ax.set_xlabel("Weighted objective W")
    ax.set_title("Figure 4 - Top-10 configurations")
    ax.grid(axis="x", alpha=0.3)
    
    # Add value labels to the right of their corresponding bars.
    label_offset = max(0.002, 0.015 * (float(np.nanmax(x)) - float(np.nanmin(x))))
    for yi, v in zip(y, x):
        ax.text(v + label_offset, yi, f"{v:.4f}", va="center", fontsize=9)
    ax.set_xlim(right=float(np.nanmax(x)) + 6 * label_offset)

    save_figure(fig, plots_dir, "fig04_top10_bar_chart.png")

    return top


def plot_pareto_2d(
    df: pd.DataFrame,
    plots_dir: Path,
    x_col: str,
    y_col: str,
    title: str,
    filename: str,
    x_label: str,
    y_label: str,
) -> pd.DataFrame:
    work = df.dropna(subset=[x_col, y_col, "W"]).copy()
    work["pareto"] = pareto_mask(work, [x_col, y_col])

    fig, ax = plt.subplots(figsize=(8.8, 5.8))

    dominated = work[~work["pareto"]]
    efficient = work[work["pareto"]]

    sc = ax.scatter(
        dominated[x_col],
        dominated[y_col],
        c=dominated["W"],
        cmap="viridis",
        s=42,
        alpha=0.35,
        label="Dominated",
    )

    ax.scatter(
        efficient[x_col],
        efficient[y_col],
        c=efficient["W"],
        cmap="viridis",
        s=85,
        edgecolors="black",
        linewidths=0.8,
        label="Pareto-efficient",
    )

    frontier = efficient.sort_values(x_col)
    if len(frontier) > 1:
        ax.step(
            frontier[x_col],
            frontier[y_col],
            where="post",
            linestyle="--",
            linewidth=1.2,
            alpha=0.65,
        )

    annotate_configurations(ax, efficient, x_col, y_col, max_labels=12, ranking_col="W")

    fig.colorbar(sc, ax=ax, label="Weighted objective W")
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.grid(alpha=0.3)
    ax.legend()

    save_figure(fig, plots_dir, filename)

    return work


def plot_figure_A2_interactions(df: pd.DataFrame, plots_dir: Path) -> None:
    strategies = sorted(df["strategy"].unique())
    fig, axes = plt.subplots(1, len(strategies), figsize=(5.4 * len(strategies), 4.8), sharey=True)

    if len(strategies) == 1:
        axes = [axes]

    for ax, strategy in zip(axes, strategies):
        sub = df[df["strategy"] == strategy]

        for rule in sorted(sub["rule"].unique()):
            r = sub[sub["rule"] == rule].sort_values("n_urgent")
            line = ax.plot(r["n_urgent"], r["W"], marker="o", linewidth=1.5, label=label_rule(rule))[0]
            if {"W_lo", "W_hi"}.issubset(r.columns):
                ax.fill_between(
                    r["n_urgent"],
                    r["W_lo"],
                    r["W_hi"],
                    color=line.get_color(),
                    alpha=0.15,
                )

        ax.set_title(label_strategy(strategy))
        ax.set_xlabel("n_urgent")
        ax.grid(axis="y", alpha=0.3)

    axes[0].set_ylabel("Weighted objective W")
    axes[-1].legend(fontsize=8, loc="best")

    fig.suptitle("Figure A2 - Interaction effects: strategy x rule x n_urgent", y=1.03, fontsize=13)

    save_figure(fig, plots_dir, "figA2_interaction_effects.png")


def plot_figure_A3_heatmap(df: pd.DataFrame, plots_dir: Path) -> None:
    strategies = sorted(df["strategy"].unique())

    vmin = float(df["W"].min())
    vmax = float(df["W"].max())

    # Reserve a separate, narrow axis for the colorbar. This prevents the legend
    # from being drawn on top of the right-most heatmap panel.
    fig = plt.figure(figsize=(5.4 * len(strategies) + 0.9, 5.8))
    grid = fig.add_gridspec(
        1,
        len(strategies) + 1,
        width_ratios=[1.0] * len(strategies) + [0.055],
        wspace=0.20,
    )
    axes = []
    shared_axis = None
    for i in range(len(strategies)):
        ax = fig.add_subplot(grid[0, i], sharey=shared_axis)
        if shared_axis is None:
            shared_axis = ax
        axes.append(ax)
    cax = fig.add_subplot(grid[0, -1])

    last_im = None

    for ax, strategy in zip(axes, strategies):
        sub = df[df["strategy"] == strategy]
        pivot = (
            sub.pivot_table(index="n_urgent", columns="rule", values="W", aggfunc="mean")
            .sort_index(ascending=False)
        )

        last_im = ax.imshow(pivot.to_numpy(), aspect="auto", vmin=vmin, vmax=vmax, cmap="viridis")

        ax.set_title(label_strategy(strategy))
        ax.set_xlabel("Scheduling rule")
        ax.set_xticks(np.arange(len(pivot.columns)))
        ax.set_xticklabels([label_rule(c) for c in pivot.columns], rotation=30, ha="right")
        ax.set_yticks(np.arange(len(pivot.index)))
        ax.set_yticklabels([str(int(n)) for n in pivot.index])

        for i in range(pivot.shape[0]):
            for j in range(pivot.shape[1]):
                value = pivot.iloc[i, j]
                if np.isfinite(value):
                    ax.text(j, i, f"{value:.3f}", ha="center", va="center", fontsize=7)

    axes[0].set_ylabel("Reserved urgent slots per week (n_urgent)")

    if last_im is not None:
        colorbar = fig.colorbar(last_im, cax=cax)
        colorbar.set_label("Weighted objective W", rotation=90, labelpad=12)

    fig.suptitle("Figure A3 - Heatmap of weighted objective W by rule and n_urgent", y=0.98, fontsize=13)
    fig.subplots_adjust(left=0.06, right=0.965, bottom=0.24, top=0.86, wspace=0.20)
    fig._skip_tight_layout = True

    save_figure(fig, plots_dir, "figA3_heatmap.png")


def plot_figure_A4_boxplots_per_rule(df: pd.DataFrame, plots_dir: Path) -> None:
    rules = sorted(df["rule"].unique())
    data = [df[df["rule"] == rule]["W"].to_numpy() for rule in rules]

    fig, ax = plt.subplots(figsize=(8.5, 5.2))

    ax.boxplot(data, tick_labels=[label_rule(rule) for rule in rules], showmeans=True)
    ax.set_xlabel("Rule")
    ax.set_ylabel("Weighted objective W")
    ax.set_title("Figure A4 - Distribution of W per rule")
    ax.grid(axis="y", alpha=0.3)

    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")

    save_figure(fig, plots_dir, "figA4_boxplots_per_rule.png")


def plot_figure_A5_stacked_contribution(top10: pd.DataFrame, plots_dir: Path) -> None:
    if not {"AWT_e_contribution", "SWT_u_contribution"}.issubset(top10.columns):
        print("Skipping Figure A5: contribution columns not available")
        return

    work = top10.sort_values("W", ascending=False).copy()
    labels = work["configuration"].tolist()
    y = np.arange(len(work))

    fig, ax = plt.subplots(figsize=(10, 5.8))

    ax.barh(y, work["AWT_e_contribution"], label="AWT_e contribution")
    ax.barh(
        y,
        work["SWT_u_contribution"],
        left=work["AWT_e_contribution"],
        label="SWT_u contribution",
    )

    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Contribution to W")
    ax.set_title("Figure A5 - Objective contribution for Top-10 configurations")
    ax.grid(axis="x", alpha=0.3)
    ax.legend()

    save_figure(fig, plots_dir, "figA5_stacked_AWTe_SWTu_contribution.png")


def plot_objective_vs_spread(df: pd.DataFrame, plots_dir: Path) -> pd.DataFrame:
    work = df.dropna(subset=["W", "W_spread"]).copy()
    work["pareto_consistency"] = pareto_mask(work, ["W", "W_spread"])

    fig, ax = plt.subplots(figsize=(8.8, 5.6))

    dominated = work[~work["pareto_consistency"]]
    efficient = work[work["pareto_consistency"]]

    ax.scatter(dominated["W"], dominated["W_spread"], s=42, alpha=0.35, label="Dominated")
    ax.scatter(
        efficient["W"],
        efficient["W_spread"],
        s=85,
        edgecolors="black",
        linewidths=0.8,
        label="Consistency-efficient",
    )

    annotate_configurations(ax, efficient, "W", "W_spread", max_labels=12, ranking_col="W")

    ax.set_xlabel("Mean weighted objective W")
    ax.set_ylabel("Spread of W across replications / CI-derived SE")
    ax.set_title("Objective vs spread - consistency plot")
    ax.grid(alpha=0.3)
    ax.legend()

    save_figure(fig, plots_dir, "figA7_objective_vs_spread_consistency.png")

    return work


def plot_pareto_rule_bar(df: pd.DataFrame, plots_dir: Path) -> pd.DataFrame:
    pool = df.dropna(subset=["AWT_e", "SWT_u", "OT"]).copy()
    pool["pareto_3d"] = pareto_mask(pool, ["AWT_e", "SWT_u", "OT"])

    efficient = pool[pool["pareto_3d"]]
    counts = efficient.groupby("rule").size().reindex(sorted(pool["rule"].unique()), fill_value=0)

    fig, ax = plt.subplots(figsize=(8.2, 5.0))

    ax.bar([label_rule(rule) for rule in counts.index], counts.to_numpy())
    ax.set_xlabel("Rule")
    ax.set_ylabel("Count in 3-objective Pareto pool")
    ax.set_title("Rules within the Pareto-efficient pool")
    ax.grid(axis="y", alpha=0.3)

    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")

    for i, count in enumerate(counts.to_numpy()):
        ax.text(i, count + 0.05, str(int(count)), ha="center", va="bottom")

    save_figure(fig, plots_dir, "figA8_rules_within_pareto_pool.png")

    return pool


def plot_3d_scatter(df: pd.DataFrame, plots_dir: Path) -> None:
    work = df.dropna(subset=["AWT_e", "SWT_u", "OT", "W"]).copy()
    work["pareto_3d"] = pareto_mask(work, ["AWT_e", "SWT_u", "OT"])

    fig = plt.figure(figsize=(10.5, 7.5))
    ax = fig.add_subplot(111, projection="3d")

    dominated = work[~work["pareto_3d"]]
    efficient = work[work["pareto_3d"]]

    sc = ax.scatter(
        dominated["AWT_e"],
        dominated["SWT_u"],
        dominated["OT"],
        c=dominated["W"],
        cmap="viridis",
        s=35,
        alpha=0.35,
        label="Dominated",
    )

    ax.scatter(
        efficient["AWT_e"],
        efficient["SWT_u"],
        efficient["OT"],
        c=efficient["W"],
        cmap="viridis",
        s=85,
        edgecolors="black",
        linewidths=0.8,
        label="3D Pareto-efficient",
    )

    ax.set_xlabel("AWT_e: elective appointment wait (h)")
    ax.set_ylabel("SWT_u: urgent scan wait (h)")
    ax.set_zlabel("OT: overtime (h)")
    ax.set_title("3D scatter: AWT_e, SWT_u, OT with W colour scale")

    fig.colorbar(sc, ax=ax, shrink=0.68, pad=0.10, label="Weighted objective W")
    ax.legend(loc="best")

    save_figure(fig, plots_dir, "figA9_3d_scatter_AWTe_SWTu_OT.png")


def plot_figure_A10_subobjectives_by_nurgent(df: pd.DataFrame, plots_dir: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    
    metrics = [
        ("AWT_e", "Mean elective wait (AWT_e) [h]", "Elective Wait by n_urgent"), 
        ("SWT_u", "Mean urgent wait (SWT_u) [h]", "Urgent Wait by n_urgent"), 
        ("OT", "Mean overtime (OT) [h]", "Overtime by n_urgent")
    ]
    
    for i, (col, ylabel, title) in enumerate(metrics):
        if col not in df.columns:
            continue
            
        ax = axes[i]
        for strategy in sorted(df["strategy"].unique()):
            sub = df[df["strategy"] == strategy].groupby("n_urgent", as_index=False)[col].mean()
            ax.plot(
                sub["n_urgent"],
                sub[col],
                marker="o",
                linewidth=1.8,
                label=label_strategy(strategy)
            )
            
        ax.set_xlabel("Reserved urgent slots per week (n_urgent)")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.set_xticks(sorted(df["n_urgent"].unique()))
        ax.grid(axis="y", alpha=0.3)
        if i == 0:
            ax.legend()
            
    fig.suptitle("Figure A10 - Sub-objectives by Strategy and n_urgent", y=1.03, fontsize=13)
    save_figure(fig, plots_dir, "figA10_subobjectives_by_nurgent.png")




def plot_figure_5_top15_forest(df: pd.DataFrame, plots_dir: Path, n: int = 15) -> pd.DataFrame | None:
    """Forest plot for uncertainty-aware comparison of the best configurations."""
    if not {"W_lo", "W_hi"}.issubset(df.columns):
        print("Skipping Figure 5: objective confidence-interval columns are not available")
        return None

    top = df.nsmallest(n, "W").copy().reset_index(drop=True)
    top["rank"] = np.arange(1, len(top) + 1)
    top["configuration"] = top.apply(config_label, axis=1)

    y = np.arange(len(top))
    lower = (top["W"] - top["W_lo"]).clip(lower=0).to_numpy()
    upper = (top["W_hi"] - top["W"]).clip(lower=0).to_numpy()

    fig, ax = plt.subplots(figsize=(10, 0.38 * len(top) + 2.4))
    ax.errorbar(
        top["W"],
        y,
        xerr=[lower, upper],
        fmt="o",
        capsize=3,
        markersize=4.5,
        linewidth=1.0,
        label="Mean W with 95% CI",
    )
    ax.axvline(
        float(top["W"].min()),
        linestyle="--",
        linewidth=1.0,
        label="Best observed mean W",
    )

    ax.set_yticks(y)
    ax.set_yticklabels(top["configuration"])
    ax.invert_yaxis()
    ax.set_xlabel("Weighted objective W")
    ax.set_ylabel("Configuration")
    ax.set_title(f"Figure 5 - 95% confidence intervals for top-{len(top)} configurations")
    ax.grid(axis="x", alpha=0.3)
    ax.legend(loc="best")

    save_figure(fig, plots_dir, "fig05_top15_forest_CI.png")
    return top


def plot_metric_correlation_matrix(df: pd.DataFrame, plots_dir: Path, tables_dir: Path) -> None:
    """Correlation matrix helps document trade-offs among the reported performance metrics."""
    metric_cols = [c for c in ["W", "AWT_e", "SWT_u", "SWT_e", "OT"] if c in df.columns]
    if len(metric_cols) < 2:
        print("Skipping Figure A11: fewer than two metric columns are available")
        return

    corr = df[metric_cols].corr(method="pearson")

    fig, ax = plt.subplots(figsize=(1.15 * len(metric_cols) + 3.0, 1.0 * len(metric_cols) + 2.7))
    im = ax.imshow(corr.to_numpy(), vmin=-1, vmax=1, cmap="coolwarm")

    ax.set_xticks(np.arange(len(metric_cols)))
    ax.set_yticks(np.arange(len(metric_cols)))
    ax.set_xticklabels(metric_cols, rotation=35, ha="right")
    ax.set_yticklabels(metric_cols)

    for i in range(len(metric_cols)):
        for j in range(len(metric_cols)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=9)

    fig.colorbar(im, ax=ax, shrink=0.82, label="Pearson correlation coefficient")
    ax.set_title("Figure A11 - Correlation matrix of performance metrics")

    save_figure(fig, plots_dir, "figA11_metric_correlation_matrix.png")

    corr_out = corr.reset_index().rename(columns={"index": "metric"})
    save_table(corr_out, tables_dir, "metric_correlation_matrix", float_format="%.3f")


def make_table_4_top10(top10: pd.DataFrame, tables_dir: Path) -> None:
    columns = [
        "rank",
        "configuration",
        "strategy",
        "n_urgent",
        "rule",
        "W",
        "W_lo",
        "W_hi",
        "AWT_e",
        "SWT_u",
        "SWT_e",
        "OT",
    ]
    available = [c for c in columns if c in top10.columns]

    save_table(top10[available], tables_dir, "table4_top10_configurations")


def default_planned_comparisons(df: pd.DataFrame) -> list[tuple[ConfigKey, ConfigKey, str]]:
    ranked = df.sort_values("W").reset_index(drop=True)
    best = ranked.iloc[0]
    best_key = config_key(best)

    comparisons: list[tuple[ConfigKey, ConfigKey, str]] = []

    def add(other_row: pd.Series, name: str) -> None:
        other_key = config_key(other_row)
        if other_key != best_key and all(not (a == best_key and b == other_key) for a, b, _ in comparisons):
            comparisons.append((best_key, other_key, name))

    if len(ranked) > 1:
        add(ranked.iloc[1], "Best overall vs runner-up")

    if len(ranked) > 2:
        add(ranked.iloc[2], "Best overall vs third-best")

    for strategy in sorted(df["strategy"].unique()):
        sub = df[df["strategy"] == strategy]
        row = sub.loc[sub["W"].idxmin()]
        add(row, f"Best overall vs best {label_strategy(strategy)}")

    for rule in sorted(df["rule"].unique()):
        sub = df[df["rule"] == rule]
        row = sub.loc[sub["W"].idxmin()]
        add(row, f"Best overall vs best {label_rule(rule)}")

    return comparisons[:10]


def comparison_from_replications(
    series_a: pd.Series,
    series_b: pd.Series,
) -> tuple[float, float, int, str]:
    paired = pd.concat(
        [series_a.rename("A"), series_b.rename("B")],
        axis=1,
        join="inner",
    ).dropna()

    if len(paired) < 2:
        return float("nan"), float("nan"), len(paired), "replication_data_insufficient"

    diff = paired["B"] - paired["A"]
    delta = float(diff.mean())
    sd = float(diff.std(ddof=1))

    if sd == 0.0:
        p_value = 0.0 if delta != 0.0 else 1.0
    else:
        t_value = delta / (sd / math.sqrt(len(diff)))
        p_value = two_sided_t_p(t_value, len(diff) - 1)

    return delta, p_value, len(diff), "paired_replication_t_test"


def comparison_from_ci(row_a: pd.Series, row_b: pd.Series) -> tuple[float, float, int, str]:
    delta = float(row_b["W"] - row_a["W"])
    se_a = ci_to_se(row_a)
    se_b = ci_to_se(row_b)

    if not (np.isfinite(se_a) and np.isfinite(se_b)):
        return delta, float("nan"), 0, "no_replications_or_ci_available"

    se_delta = math.sqrt(se_a**2 + se_b**2)

    if se_delta == 0.0:
        p_value = 0.0 if delta != 0.0 else 1.0
    else:
        p_value = normal_two_sided_p(delta / se_delta)

    return delta, p_value, 0, "ci_based_independent_normal_approximation"


def make_table_5_planned_comparisons(
    df: pd.DataFrame,
    replication_series: dict[ConfigKey, pd.Series],
    tables_dir: Path,
) -> None:
    indexed = {config_key(row): row for _, row in df.iterrows()}
    rows = []

    for key_a, key_b, name in default_planned_comparisons(df):
        row_a = indexed[key_a]
        row_b = indexed[key_b]

        if key_a in replication_series and key_b in replication_series:
            delta, p_value, n_pairs, method = comparison_from_replications(
                replication_series[key_a],
                replication_series[key_b],
            )
        else:
            delta, p_value, n_pairs, method = comparison_from_ci(row_a, row_b)

        rows.append(
            {
                "comparison": name,
                "A_reference": config_label(row_a),
                "B_comparator": config_label(row_b),
                "W_A": float(row_a["W"]),
                "W_B": float(row_b["W"]),
                "delta_W_B_minus_A": delta,
                "p_value_two_sided": p_value,
                "n_pairs": n_pairs,
                "method": method,
            }
        )

    table = pd.DataFrame(rows)
    save_table(table, tables_dir, "table5_planned_paired_comparisons", float_format="%.6f")


def make_table_6_rule_comparison(df: pd.DataFrame, tables_dir: Path) -> None:
    rows = []

    for rule, sub in df.groupby("rule"):
        best = sub.loc[sub["W"].idxmin()]

        rows.append(
            {
                "rule": int(rule),
                "rule_label": label_rule(rule),
                "n_configurations": len(sub),
                "mean_W": sub["W"].mean(),
                "median_W": sub["W"].median(),
                "best_W": best["W"],
                "best_configuration": config_label(best),
                "mean_AWT_e": sub["AWT_e"].mean(),
                "mean_SWT_u": sub["SWT_u"].mean(),
                "mean_OT": sub["OT"].mean(),
            }
        )

    table = pd.DataFrame(rows).sort_values("mean_W")
    save_table(table, tables_dir, "table6_rule_comparison")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate SMA report plots and tables from simulation CSV files.")

    parser.add_argument("--results-dir", type=Path, default=None, help="Directory containing experiment/warmup CSV files.")
    parser.add_argument("--experiment-file", type=Path, default=None, help="Path to experiment_results.csv.")
    parser.add_argument("--warmup-file", type=Path, default=None, help="Path to warmup_analysis.csv.")
    parser.add_argument("--plots-dir", type=Path, default=None, help="Output directory for figures.")
    parser.add_argument("--tables-dir", type=Path, default=None, help="Output directory for tables.")

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    results_dir = args.results_dir
    if results_dir is None:
        candidate_dirs = [DEFAULT_RESULTS_DIR, DEFAULT_RESULTS_V2_DIR, DEFAULT_LOCAL_RESULTS_DIR, Path.cwd()]
        results_dir = next(
            (p for p in candidate_dirs if (p / "experiment_results.csv").exists() or (p / "experiment_results_v2.csv").exists()),
            DEFAULT_RESULTS_DIR,
        )

    results_dir = results_dir.resolve()

    experiment_file = args.experiment_file
    if experiment_file is None:
        experiment_file = choose_existing_file(
            [
                results_dir / "experiment_results.csv",
                results_dir / "experiment_results_v2.csv",
                DEFAULT_RESULTS_DIR / "experiment_results.csv",
                DEFAULT_RESULTS_DIR / "experiment_results_v2.csv",
                DEFAULT_RESULTS_V2_DIR / "experiment_results.csv",
                DEFAULT_RESULTS_V2_DIR / "experiment_results_v2.csv",
                DEFAULT_LOCAL_RESULTS_DIR / "experiment_results.csv",
                DEFAULT_LOCAL_RESULTS_DIR / "experiment_results_v2.csv",
                Path.cwd() / "experiment_results.csv",
                Path.cwd() / "experiment_results_v2.csv",
            ],
            "experiment results CSV",
            required=True,
        )

    experiment_file = experiment_file.resolve()

    warmup_file = args.warmup_file
    if warmup_file is None:
        warmup_file = choose_existing_file(
            [
                results_dir / "warmup_analysis.csv",
                results_dir / "warmup_analysis_v2.csv",
                DEFAULT_RESULTS_DIR / "warmup_analysis.csv",
                DEFAULT_RESULTS_V2_DIR / "warmup_analysis.csv",
                DEFAULT_LOCAL_RESULTS_DIR / "warmup_analysis.csv",
                DEFAULT_LOCAL_RESULTS_DIR / "warmup_analysis_v2.csv",
                Path.cwd() / "warmup_analysis.csv",
                Path.cwd() / "warmup_analysis_v2.csv",
            ],
            "warmup analysis CSV",
            required=False,
        )
    elif not warmup_file.exists():
        warmup_file = None

    plots_dir = (args.plots_dir or (results_dir / "plots")).resolve()
    tables_dir = (args.tables_dir or (results_dir / "tables")).resolve()

    experiment = load_experiment(experiment_file)
    validate_experiment(experiment, experiment_file)
    warmup = load_warmup(warmup_file)
    replication_series = load_replication_objectives(results_dir)
    experiment = add_spread_column(experiment, replication_series)

    print(f"Loaded {len(experiment)} configurations from {experiment_file}")
    print(f"Loaded {len(replication_series)} replication-analysis files from {results_dir}")
    print(f"Using objective: W = {WEIGHT_ELECTIVE:.8f} * AWT_e + {WEIGHT_URGENT:.8f} * SWT_u")

    plot_figure_1_welch(warmup, plots_dir)
    plot_figure_2_main_effects(experiment, plots_dir)
    plot_figure_3_w_by_strategy_nurgent(experiment, plots_dir)
    top10 = plot_figure_4_top10(experiment, plots_dir)
    plot_figure_5_top15_forest(experiment, plots_dir)

    plot_pareto_2d(
        experiment,
        plots_dir,
        x_col="AWT_e",
        y_col="SWT_u",
        title="Figure A1 - Pareto scatter: AWT_e vs SWT_u",
        filename="figA1_pareto_AWTe_vs_SWTu.png",
        x_label="AWT_e: elective appointment wait (h)",
        y_label="SWT_u: urgent scan wait (h)",
    )

    plot_figure_A2_interactions(experiment, plots_dir)
    plot_figure_A3_heatmap(experiment, plots_dir)
    plot_figure_A4_boxplots_per_rule(experiment, plots_dir)
    plot_figure_A5_stacked_contribution(top10, plots_dir)

    plot_pareto_2d(
        experiment,
        plots_dir,
        x_col="AWT_e",
        y_col="OT",
        title="Pareto scatter: AWT_e vs OT",
        filename="figA6_pareto_AWTe_vs_OT.png",
        x_label="AWT_e: elective appointment wait (h)",
        y_label="OT: overtime (h)",
    )

    plot_objective_vs_spread(experiment, plots_dir)
    pareto_pool = plot_pareto_rule_bar(experiment, plots_dir)
    plot_3d_scatter(experiment, plots_dir)
    plot_figure_A10_subobjectives_by_nurgent(experiment, plots_dir)
    plot_metric_correlation_matrix(experiment, plots_dir, tables_dir)

    make_table_4_top10(top10, tables_dir)
    make_table_5_planned_comparisons(experiment, replication_series, tables_dir)
    make_table_6_rule_comparison(experiment, tables_dir)

    save_table(
        pareto_pool[pareto_pool["pareto_3d"]][
            ["strategy", "n_urgent", "rule", "W", "AWT_e", "SWT_u", "OT"]
        ].sort_values("W"),
        tables_dir,
        "pareto_efficient_pool_3d",
    )

    print(f"All figures saved to {plots_dir}")
    print(f"All tables saved to {tables_dir}")


if __name__ == "__main__":
    main()
