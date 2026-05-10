"""
analyze_pareto.py
=================
Generates five analysis plots from simulation output CSVs:

  1. 2D Pareto scatter  –  elective appointment wait vs urgent scan wait
  2. 2D Pareto scatter  –  elective appointment wait vs overtime
  3. Risk-return scatter – mean objective vs std dev (performance vs consistency)
  4. Rule frequency bar  –  how often each rule appears on the Pareto frontier
  5. 3D scatter          –  elective wait / urgent wait / overtime, Pareto front highlighted

Objective function (as specified in the assignment):
    Minimize  w_e * E[AppWT_elective]  +  w_u * E[ScanWT_urgent]

    where:
        w_e = 1 / 168   (max desired elective wait = 1 week = 168 hours)
        w_u = 1 / 9     (max desired urgent wait   = 9 hours)

To experiment with different weights, edit WEIGHT_ELECTIVE and WEIGHT_URGENT below.
All plots that depend on the weighted objective update automatically.

Directory layout assumed (mirrors the simulation output structure):
    project assignment/
    ├── python code/
    │   └── analyze_pareto.py   <- this file
    ├── results_v2/
    │   ├── experiment_results_v2.csv
    │   └── replication_analysis_*.csv
    └── plots_v2/               <- created automatically
"""

import os
import glob
import csv
import statistics

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from mpl_toolkits.mplot3d import Axes3D          # noqa: F401  (registers 3d projection)

# ---------------------------------------------------------------------------
# Objective function weights  –  as specified in the assignment
#   w_e = 1 / 168   because max acceptable elective appointment wait = 1 week = 168 h
#   w_u = 1 / 9     because max acceptable urgent scan wait          = 9 h
# ---------------------------------------------------------------------------

WEIGHT_ELECTIVE = 1.0 / 168.0   # w_e
WEIGHT_URGENT   = 1.0 / 9.0     # w_u

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results_v2")
PLOTS_DIR   = os.path.join(os.path.dirname(__file__), "..", "plots_v2")
os.makedirs(PLOTS_DIR, exist_ok=True)

# Colour palette (strategy -> colour, rule -> marker)
STRATEGY_COLORS = {1: "#E07B39", 2: "#3A86FF", 3: "#06D6A0"}
STRATEGY_LABELS = {1: "Strategy 1", 2: "Strategy 2", 3: "Strategy 3"}
RULE_MARKERS    = {1: "o", 2: "s", 3: "D", 4: "^", 5: "v", 6: "P", 7: "X"}
RULE_LABELS     = {
    1: "R1 – FCFS",
    2: "R2 – BW K=2",
    3: "R3 – Blocking",
    4: "R4 – Benchmark",
    5: "R5 – BW K=3",
    6: "R6 – BW K=4",
    7: "R7 – BW K=5",
}

PARETO_EDGE_COLOR = "#1a1a2e"
DOMINATED_ALPHA   = 0.25
PARETO_ALPHA      = 0.90
PARETO_EDGE_WIDTH = 1.2
FIGURE_DPI        = 150

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_experiment_results(path: str) -> list[dict]:
    """Load experiment_results_v2.csv and cast numeric fields."""
    numeric = {
        "strategy", "n_urgent", "rule",
        "mean_electiveAppWT", "mean_electiveScanWT",
        "mean_urgentScanWT", "mean_OT",
        "mean_objective", "ci_lo_objective", "ci_hi_objective",
    }
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            rows.append({k: (float(v) if k in numeric else v) for k, v in row.items()})
    return rows


def load_replication_stdevs(results_dir: str) -> dict[tuple, float]:
    """
    Scan all replication_analysis_*.csv files and compute the standard deviation
    of the objective across replications for each (strategy, n_urgent, rule).

    The objective is recomputed from raw metrics using the module-level weights
    so that changing WEIGHT_ELECTIVE / WEIGHT_URGENT is automatically reflected.

    Returns a dict keyed by (strategy, n_urgent, rule) -> stdev.
    """
    pattern = os.path.join(results_dir, "replication_analysis_*.csv")
    stdevs  = {}

    for filepath in glob.glob(pattern):
        basename = os.path.basename(filepath)
        tag      = basename.replace("replication_analysis_", "").replace(".csv", "")
        try:
            s_idx    = tag.index("S")
            n_idx    = tag.index("N")
            r_idx    = tag.index("R")
            strategy = int(tag[s_idx + 1: n_idx])
            n_urgent = int(tag[n_idx + 1: r_idx])
            rule     = int(tag[r_idx + 1:])
        except (ValueError, IndexError):
            continue

        objectives = []
        with open(filepath, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # support both original and v2 column name conventions
                el  = float(row.get("electiveAppWT") or row.get("el_app_wt") or 0)
                ur  = float(row.get("urgentScanWT")  or row.get("ur_scan_wt") or 0)
                obj = WEIGHT_ELECTIVE * el + WEIGHT_URGENT * ur
                objectives.append(obj)

        if len(objectives) >= 2:
            stdevs[(strategy, n_urgent, rule)] = statistics.stdev(objectives)

    return stdevs


# ---------------------------------------------------------------------------
# Pareto dominance
# ---------------------------------------------------------------------------

def is_dominated(row: dict, others: list[dict], objectives: list[str]) -> bool:
    """Return True if `row` is dominated by any configuration in `others`."""
    eps = 1e-9
    for other in others:
        if other is row:
            continue
        if all(other[o] <= row[o] + eps for o in objectives) and \
           any(other[o] <  row[o] - eps for o in objectives):
            return True
    return False


def pareto_front(rows: list[dict], objectives: list[str]) -> list[bool]:
    """Return a boolean mask: True = Pareto-efficient."""
    return [not is_dominated(r, rows, objectives) for r in rows]


# ---------------------------------------------------------------------------
# Plot helpers
# ---------------------------------------------------------------------------

def save(fig: plt.Figure, name: str) -> None:
    path = os.path.join(PLOTS_DIR, f"{name}.png")
    fig.savefig(path, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {path}")


def strategy_legend_handles() -> list:
    return [
        mpatches.Patch(color=STRATEGY_COLORS[s], label=STRATEGY_LABELS[s])
        for s in sorted(STRATEGY_COLORS)
    ]


def rule_legend_handles(rules_present: set) -> list:
    return [
        plt.Line2D([0], [0], marker=RULE_MARKERS[r], color="grey",
                   linestyle="None", markersize=7, label=RULE_LABELS[r])
        for r in sorted(rules_present)
    ]


# ---------------------------------------------------------------------------
# Plot 1 & 2 – 2D Pareto scatters
# ---------------------------------------------------------------------------

def plot_2d_pareto(rows: list[dict],
                   x_col: str, y_col: str,
                   x_label: str, y_label: str,
                   title: str, filename: str) -> None:
    """Generic 2D Pareto scatter coloured by strategy, shaped by rule."""
    mask = pareto_front(rows, [x_col, y_col])

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.set_facecolor("#f8f8f8")
    fig.patch.set_facecolor("white")

    rules_present = set()
    for row, is_pareto in zip(rows, mask):
        s      = int(row["strategy"])
        r      = int(row["rule"])
        rules_present.add(r)
        color  = STRATEGY_COLORS[s]
        marker = RULE_MARKERS[r]
        alpha  = PARETO_ALPHA  if is_pareto else DOMINATED_ALPHA
        zorder = 4             if is_pareto else 2
        ec     = PARETO_EDGE_COLOR if is_pareto else "none"
        lw     = PARETO_EDGE_WIDTH if is_pareto else 0
        ax.scatter(row[x_col], row[y_col],
                   c=color, marker=marker, alpha=alpha,
                   edgecolors=ec, linewidths=lw,
                   s=70, zorder=zorder)

    # Pareto frontier step line
    pareto_rows = sorted([r for r, m in zip(rows, mask) if m], key=lambda r: r[x_col])
    if pareto_rows:
        ax.step(
            [r[x_col] for r in pareto_rows],
            [r[y_col] for r in pareto_rows],
            where="post", color="#1a1a2e", linewidth=1.2,
            linestyle="--", alpha=0.5, zorder=3
        )

    ax.set_xlabel(x_label, fontsize=11)
    ax.set_ylabel(y_label, fontsize=11)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.grid(True, linestyle="--", alpha=0.4)

    leg1 = ax.legend(handles=strategy_legend_handles(),
                     title="Strategy", loc="upper left", fontsize=9)
    ax.add_artist(leg1)
    ax.legend(handles=rule_legend_handles(rules_present),
              title="Rule", loc="lower right", fontsize=9)

    # annotate Pareto points with N value
    for row, is_pareto in zip(rows, mask):
        if is_pareto:
            ax.annotate(f"N={int(row['n_urgent'])}",
                        xy=(row[x_col], row[y_col]),
                        xytext=(4, 4), textcoords="offset points",
                        fontsize=6, alpha=0.75)

    save(fig, filename)


# ---------------------------------------------------------------------------
# Plot 3 – Risk-return: mean objective vs std dev across replications
# ---------------------------------------------------------------------------

def plot_risk_return(rows: list[dict], stdevs: dict) -> None:
    """
    X axis: mean weighted objective  (w_e * E[AppWT] + w_u * E[UrgWT])
    Y axis: std dev of objective across replications
    Bottom-left corner = best (low mean AND low variance).
    Pareto front on (mean, stdev) is highlighted.
    """
    augmented = []
    for row in rows:
        key = (int(row["strategy"]), int(row["n_urgent"]), int(row["rule"]))
        sd  = stdevs.get(key)
        if sd is None:
            # fall back to half the CI width if no replication file is present
            sd = (float(row["ci_hi_objective"]) - float(row["ci_lo_objective"])) / 2
        # recompute objective from raw metrics so weight changes propagate
        obj = WEIGHT_ELECTIVE * row["mean_electiveAppWT"] + WEIGHT_URGENT * row["mean_urgentScanWT"]
        augmented.append({**row, "_obj": obj, "_sd": sd})

    mask = pareto_front(augmented, ["_obj", "_sd"])

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.set_facecolor("#f8f8f8")
    fig.patch.set_facecolor("white")

    rules_present = set()
    for row, is_pareto in zip(augmented, mask):
        s      = int(row["strategy"])
        r      = int(row["rule"])
        rules_present.add(r)
        color  = STRATEGY_COLORS[s]
        marker = RULE_MARKERS[r]
        alpha  = PARETO_ALPHA  if is_pareto else DOMINATED_ALPHA
        ec     = PARETO_EDGE_COLOR if is_pareto else "none"
        lw     = PARETO_EDGE_WIDTH if is_pareto else 0
        ax.scatter(row["_obj"], row["_sd"],
                   c=color, marker=marker, alpha=alpha,
                   edgecolors=ec, linewidths=lw,
                   s=70, zorder=4 if is_pareto else 2)

    pareto_pts = sorted(
        [(r["_obj"], r["_sd"]) for r, m in zip(augmented, mask) if m],
        key=lambda t: t[0]
    )
    if pareto_pts:
        ax.step([p[0] for p in pareto_pts], [p[1] for p in pareto_pts],
                where="post", color="#1a1a2e", linewidth=1.2,
                linestyle="--", alpha=0.5, zorder=3)

    ax.set_xlabel(
        f"Mean objective  "
        f"(w_e={WEIGHT_ELECTIVE:.6f},  w_u={WEIGHT_URGENT:.6f})",
        fontsize=10)
    ax.set_ylabel("Std dev of objective across replications", fontsize=11)
    ax.set_title("Performance vs Consistency  (bottom-left = best)",
                 fontsize=13, fontweight="bold", pad=12)
    ax.grid(True, linestyle="--", alpha=0.4)

    leg1 = ax.legend(handles=strategy_legend_handles(),
                     title="Strategy", loc="upper left", fontsize=9)
    ax.add_artist(leg1)
    ax.legend(handles=rule_legend_handles(rules_present),
              title="Rule", loc="lower right", fontsize=9)

    save(fig, "risk_return")


# ---------------------------------------------------------------------------
# Plot 4 – Rule frequency on Pareto frontiers
# ---------------------------------------------------------------------------

def plot_rule_frequency(rows: list[dict], stdevs: dict) -> None:
    """
    Count how many times each rule appears across all three Pareto frontiers:
      - elective appointment wait vs urgent scan wait
      - elective appointment wait vs overtime
      - mean objective vs std dev (risk-return)
    """
    # build augmented rows for the risk-return front
    augmented = []
    for row in rows:
        key = (int(row["strategy"]), int(row["n_urgent"]), int(row["rule"]))
        sd  = stdevs.get(key, (row["ci_hi_objective"] - row["ci_lo_objective"]) / 2)
        obj = WEIGHT_ELECTIVE * row["mean_electiveAppWT"] + WEIGHT_URGENT * row["mean_urgentScanWT"]
        augmented.append({**row, "_obj": obj, "_sd": sd})

    fronts = [
        (rows,      ["mean_electiveAppWT", "mean_urgentScanWT"]),
        (rows,      ["mean_electiveAppWT", "mean_OT"]),
        (augmented, ["_obj", "_sd"]),
    ]

    pareto_rule_counts = {r: 0 for r in RULE_LABELS}
    for rset, objectives in fronts:
        mask = pareto_front(rset, objectives)
        for row, is_p in zip(rset, mask):
            if is_p:
                pareto_rule_counts[int(row["rule"])] += 1

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor("white")

    rules  = sorted(pareto_rule_counts)
    counts = [pareto_rule_counts[r] for r in rules]
    bars   = ax.bar(
        [RULE_LABELS[r] for r in rules], counts,
        color=STRATEGY_COLORS[2],
        edgecolor=PARETO_EDGE_COLOR, linewidth=0.8, alpha=0.85
    )

    for bar, count in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.15,
                str(count), ha="center", va="bottom", fontsize=10)

    ax.set_xlabel("Appointment scheduling rule", fontsize=11)
    ax.set_ylabel(
        "Appearances on Pareto frontiers\n(elective vs urgent  |  elective vs OT  |  risk-return)",
        fontsize=10)
    ax.set_title("Rule frequency on Pareto frontiers",
                 fontsize=13, fontweight="bold", pad=12)
    ax.set_ylim(0, max(counts) + 2)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    plt.xticks(rotation=20, ha="right", fontsize=9)
    fig.tight_layout()

    save(fig, "rule_frequency")


# ---------------------------------------------------------------------------
# Plot 5 – 3D scatter
# ---------------------------------------------------------------------------

def plot_3d(rows: list[dict]) -> None:
    """
    3D scatter: elective appointment wait (x), urgent scan wait (y), overtime (z).
    Pareto-efficient points are large, opaque, edge-highlighted with a full legend.
    """
    objectives = ["mean_electiveAppWT", "mean_urgentScanWT", "mean_OT"]
    mask       = pareto_front(rows, objectives)

    fig = plt.figure(figsize=(12, 8))
    ax  = fig.add_subplot(111, projection="3d")
    fig.patch.set_facecolor("white")

    rules_present = {int(r["rule"]) for r in rows}

    for row, is_pareto in zip(rows, mask):
        s      = int(row["strategy"])
        r      = int(row["rule"])
        color  = STRATEGY_COLORS[s]
        marker = RULE_MARKERS[r]
        if is_pareto:
            ax.scatter(row["mean_electiveAppWT"],
                       row["mean_urgentScanWT"],
                       row["mean_OT"],
                       c=color, marker=marker,
                       s=120, alpha=PARETO_ALPHA,
                       edgecolors=PARETO_EDGE_COLOR,
                       linewidths=PARETO_EDGE_WIDTH,
                       depthshade=True, zorder=5)
        else:
            ax.scatter(row["mean_electiveAppWT"],
                       row["mean_urgentScanWT"],
                       row["mean_OT"],
                       c=color, marker=marker,
                       s=40, alpha=DOMINATED_ALPHA,
                       edgecolors="none",
                       depthshade=True, zorder=2)

    ax.set_xlabel("Elective appt wait (h)", fontsize=10, labelpad=8)
    ax.set_ylabel("Urgent scan wait (h)",   fontsize=10, labelpad=8)
    ax.set_zlabel("Overtime (h)",           fontsize=10, labelpad=8)
    ax.set_title(
        "3D objective space  –  Pareto-efficient configurations highlighted",
        fontsize=12, fontweight="bold", pad=16)

    # combined legend: Pareto status + strategy + rule
    blank = mpatches.Patch(color="none", label=" ")
    pareto_handle = plt.Line2D(
        [0], [0], marker="o", color="white",
        markeredgecolor=PARETO_EDGE_COLOR, markeredgewidth=1.5,
        markersize=10, linestyle="None", label="Pareto-efficient")
    dominated_handle = plt.Line2D(
        [0], [0], marker="o", color="grey",
        markersize=7, linestyle="None", alpha=0.3, label="Dominated")

    all_handles = (
        [mpatches.Patch(color="none", label="─── Pareto status ───")] +
        [pareto_handle, dominated_handle, blank] +
        [mpatches.Patch(color="none", label="─── Strategy ───")] +
        strategy_legend_handles() + [blank] +
        [mpatches.Patch(color="none", label="─── Rule ───")] +
        rule_legend_handles(rules_present)
    )
    ax.legend(handles=all_handles,
              loc="upper left", bbox_to_anchor=(1.02, 1.0),
              fontsize=8, framealpha=0.9,
              borderpad=0.8, handlelength=1.5)

    fig.tight_layout()
    save(fig, "3d_objective_space")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Loading data...")
    results_path = os.path.join(RESULTS_DIR, "experiment_results_v2.csv")
    rows   = load_experiment_results(results_path)
    stdevs = load_replication_stdevs(RESULTS_DIR)
    print(f"  {len(rows)} configurations loaded")
    print(f"  {len(stdevs)} replication std devs loaded")
    print(f"\n  Objective weights:")
    print(f"    w_e = 1 / 168 = {WEIGHT_ELECTIVE:.6f}  (elective appt wait)")
    print(f"    w_u = 1 / 9   = {WEIGHT_URGENT:.6f}   (urgent scan wait)")

    print("\nGenerating plots...")

    plot_2d_pareto(
        rows,
        x_col="mean_electiveAppWT", y_col="mean_urgentScanWT",
        x_label="Mean elective appointment wait (h)",
        y_label="Mean urgent scan wait (h)",
        title="Pareto frontier: Elective appointment wait vs Urgent scan wait",
        filename="pareto_elective_vs_urgent",
    )

    plot_2d_pareto(
        rows,
        x_col="mean_electiveAppWT", y_col="mean_OT",
        x_label="Mean elective appointment wait (h)",
        y_label="Mean daily overtime (h)",
        title="Pareto frontier: Elective appointment wait vs Overtime",
        filename="pareto_elective_vs_overtime",
    )

    plot_risk_return(rows, stdevs)
    plot_rule_frequency(rows, stdevs)
    plot_3d(rows)

    print(f"\nAll plots saved to {os.path.abspath(PLOTS_DIR)}/")