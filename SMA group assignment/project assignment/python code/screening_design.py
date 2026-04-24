"""
screening_design.py
-------------------
Performs a 2^k factorial screening design on the experiment results.

Three factors, each encoded at two levels (low = -1, high = +1):

    Factor A: Strategy positioning
      low  = S1 (end of session)
      high = S3 (after every block of 6)          (S2 omitted for 2-level design)
    Factor B: Number of urgent slots N
      low  = 10
      high = 20
    Factor C: Scheduling rule
      low  = Rule 1 (FCFS)
      high = Rule 4 (Benchmarking)                (Rules 2, 3 omitted)

The 2^3 = 8 corner points are read from experiment_results.csv (which
contains all 132 configurations with mean and 95 % CI of the objective).
Main effects and 2-way/3-way interactions are then estimated from the
usual signed sums.

Outputs
-------
  ../results/plots/screening_pareto.png        (Pareto of |effects|)
  ../results/plots/screening_interaction.png   (2-way interaction plots)
  console summary table of main + interaction effects
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
PLOT_DIR    = os.path.join(RESULTS_DIR, "plots")
os.makedirs(PLOT_DIR, exist_ok=True)

# ── Level assignment ────────────────────────────────────────────────────────
LEVELS = {
    "A": {"name": "Strategy",  "low": ("strategy", 1), "high": ("strategy", 3)},
    "B": {"name": "N_urgent",  "low": ("n_urgent", 10), "high": ("n_urgent", 20)},
    "C": {"name": "Rule",      "low": ("rule",     1), "high": ("rule",     4)},
}

# Run order of the 2^3 design (Yates' standard order)
SIGNS = [
    #  A   B   C
    (-1, -1, -1),
    (+1, -1, -1),
    (-1, +1, -1),
    (+1, +1, -1),
    (-1, -1, +1),
    (+1, -1, +1),
    (-1, +1, +1),
    (+1, +1, +1),
]


def value_for(sign, factor):
    spec = LEVELS[factor]["high" if sign == +1 else "low"]
    return spec  # (column, value)


def fetch_response(df, a, b, c):
    """Return mean_objective for the 2^3 corner (a, b, c) in {-1, +1}^3."""
    col_a, val_a = value_for(a, "A")
    col_b, val_b = value_for(b, "B")
    col_c, val_c = value_for(c, "C")
    sub = df[(df[col_a] == val_a) & (df[col_b] == val_b) & (df[col_c] == val_c)]
    if len(sub) != 1:
        raise RuntimeError(f"Expected one row for ({a},{b},{c}); got {len(sub)}")
    return float(sub["mean_objective"].values[0])


def main():
    df = pd.read_csv(os.path.join(RESULTS_DIR, "experiment_results.csv"))

    responses = []
    for a, b, c in SIGNS:
        y = fetch_response(df, a, b, c)
        responses.append(y)
    y = np.array(responses)

    # ── Effect estimates ────────────────────────────────────────────────────
    # For a 2^k design with 8 runs, each effect = (1/4) * sum(sign * y)
    # (sum of contrasts with +/-1 signs, divided by 2^(k-1) = 4).
    A = np.array([s[0] for s in SIGNS])
    B = np.array([s[1] for s in SIGNS])
    C = np.array([s[2] for s in SIGNS])
    AB = A * B
    AC = A * C
    BC = B * C
    ABC = A * B * C

    grand_mean = y.mean()
    effects = {
        "A (Strategy)":          (A   @ y) / 4.0,
        "B (N_urgent)":          (B   @ y) / 4.0,
        "C (Rule)":              (C   @ y) / 4.0,
        "AB":                    (AB  @ y) / 4.0,
        "AC":                    (AC  @ y) / 4.0,
        "BC":                    (BC  @ y) / 4.0,
        "ABC":                   (ABC @ y) / 4.0,
    }
    # Summary table
    print("\n2^3 Screening design (corners of full factorial)")
    print("--------------------------------------------------")
    print("Run-order table:")
    header = f"{'#':>2} {'A':>3} {'B':>3} {'C':>3} {'y (mean_obj)':>14}"
    print(header)
    for i, (s, v) in enumerate(zip(SIGNS, y)):
        print(f"{i+1:>2} {s[0]:>+3d} {s[1]:>+3d} {s[2]:>+3d} {v:>14.5f}")
    print(f"\nGrand mean: {grand_mean:.5f}\n")

    print(f"{'Effect':<18}{'Value':>10}{'|Effect|':>12}")
    print("-" * 40)
    rows = sorted(effects.items(), key=lambda kv: abs(kv[1]), reverse=True)
    for name, val in rows:
        print(f"{name:<18}{val:>10.5f}{abs(val):>12.5f}")

    # ── Pareto of |effects| ────────────────────────────────────────────────
    labels = [r[0] for r in rows]
    vals   = [abs(r[1]) for r in rows]
    colors = ["#4C72B0" if r[1] < 0 else "#C44E52" for r in rows]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(range(len(labels)), vals, color=colors, edgecolor="white")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("|Effect| on objective value")
    ax.set_title("Screening design – Pareto chart of effects\n"
                 "Red = positive (worsens objective), Blue = negative (improves)")
    for i, v in enumerate(vals):
        ax.text(v, i, f"  {v:.4f}", va="center", fontsize=8)
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(PLOT_DIR, "screening_pareto.png"),
                dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\nSaved: {os.path.join(PLOT_DIR, 'screening_pareto.png')}")

    # ── 2-way interaction plots ─────────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))

    def interaction_means(fac1, fac2):
        """Return dict[(lvl1,lvl2)] -> mean y for levels in {-1,+1}^2."""
        out = {}
        for l1 in (-1, +1):
            for l2 in (-1, +1):
                mask = (np.array([s[0 if fac1 == "A" else
                                  1 if fac1 == "B" else 2] for s in SIGNS]) == l1) & \
                       (np.array([s[0 if fac2 == "A" else
                                  1 if fac2 == "B" else 2] for s in SIGNS]) == l2)
                out[(l1, l2)] = y[mask].mean()
        return out

    pair_info = [("A", "B"), ("A", "C"), ("B", "C")]
    for ax, (f1, f2) in zip(axes, pair_info):
        mm = interaction_means(f1, f2)
        for l2, lbl in ((-1, "low"), (+1, "high")):
            ys = [mm[(-1, l2)], mm[(+1, l2)]]
            ax.plot([-1, +1], ys, marker="o", lw=2,
                    label=f"{LEVELS[f2]['name']}={lbl}")
        ax.set_xticks([-1, +1])
        ax.set_xticklabels(["low", "high"])
        ax.set_xlabel(f"{LEVELS[f1]['name']}")
        ax.set_ylabel("Mean objective")
        ax.set_title(f"Interaction {f1}×{f2}")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle("2-way interaction plots  (non-parallel lines => interaction)")
    fig.tight_layout()
    fig.savefig(os.path.join(PLOT_DIR, "screening_interaction.png"),
                dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {os.path.join(PLOT_DIR, 'screening_interaction.png')}")


if __name__ == "__main__":
    main()
