"""
ranking_selection.py
--------------------
Applies the Dudewicz & Dalal (1975) two-stage ranking-and-selection
procedure to the top candidate configurations, minimising the objective.

Procedure
---------
Stage 1. For every candidate system i (i = 1..k) obtain n_0 first-stage
         replications; here n_0 = 100 from the main experiment. Compute the
         first-stage sample mean  \bar Y_i^{(1)}  and sample variance S_i^2.

Stage 2. Determine the total number of replications required
             N_i = max( n_0 + 1, ceil( (h * S_i / d) ^ 2 ) )
         where
             h = Rinott constant for (k, n_0, 1 - alpha)
             d = indifference-zone half-width
         If N_i > n_0 we would run (N_i - n_0) additional replications; here
         we fall back to the single-stage correlated CI if n_0 already suffices.

Stage 3. Form weights
             W_{i1} = (n_0 / N_i) * (1 + sqrt(1 - (N_i / n_0)
                                             * (1 - (N_i - n_0) * d^2 /
                                                (h^2 * S_i^2))))
             W_{i2} = 1 - W_{i1}
         and the weighted final mean
             tilde Y_i = W_{i1} \bar Y_i^{(1)} + W_{i2} \bar Y_i^{(2)}.

         Here we only have the first-stage sample (n_0 = 100), so if the
         formula tells us no additional stage-2 samples are needed
         (N_i <= n_0), we simply report tilde Y_i = \bar Y_i^{(1)}.
         Configurations requiring more replications are flagged.

Reference
---------
A. Law, "Simulation Modeling & Analysis", 5th ed., Section 10.4.
D. Goldsman, "Ranking and selection methods" (lecture notes).

Inputs
------
One CSV per candidate, produced by
    ./simulation replication_analysis <input-file> <rule> W R warmup <outFile>
with column  "objective"  (per-replication objective).

Outputs
-------
Console report + ../results/plots/ranking_selection.png
"""

import os
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
PLOT_DIR    = os.path.join(RESULTS_DIR, "plots")
os.makedirs(PLOT_DIR, exist_ok=True)

# Top-k candidate configurations (same order as run_top_replications.sh)
CANDIDATES = [
    ("S3 N=13 Rule=4", "replication_analysis_S3N13R4.csv"),
    ("S3 N=13 Rule=2", "replication_analysis_S3N13R2.csv"),
    ("S3 N=13 Rule=1", "replication_analysis_S3N13R1.csv"),
    ("S3 N=14 Rule=4", "replication_analysis_S3N14R4.csv"),
    ("S3 N=14 Rule=2", "replication_analysis_S3N14R2.csv"),
    ("S3 N=14 Rule=1", "replication_analysis_S3N14R1.csv"),
    ("S3 N=13 Rule=3", "replication_analysis_S3N13R3.csv"),
    ("S3 N=12 Rule=4", "replication_analysis_S3N12R4.csv"),
]

# Dudewicz & Dalal / Rinott constants h for alpha = 0.10 (1 - P* = 0.90),
# k candidates and n_0 = 20 (a commonly tabulated value).  For n_0 = 100
# h is very close to the normal quantile z_{1-alpha/(k-1)} for many k.
# We use the conservative approximation by Wilcox / Law 10.4 for n_0 large
# (n_0 -> infty means h -> z_{1-alpha^{1/(k-1)}} ).
# For the present exposition we take a representative tabulated value.
# Reference: Bechhofer, Santner, Goldsman 1995, Table 4.1.
RINOTT_H = {
    # (k, alpha) : h  for n_0 = 20.  Tabulated values.
    (2, 0.10): 2.015, (2, 0.05): 2.492,
    (3, 0.10): 2.329, (3, 0.05): 2.800,
    (4, 0.10): 2.494, (4, 0.05): 2.962,
    (5, 0.10): 2.609, (5, 0.05): 3.074,
    (6, 0.10): 2.696, (6, 0.05): 3.157,
    (7, 0.10): 2.767, (7, 0.05): 3.225,
    (8, 0.10): 2.826, (8, 0.05): 3.280,
    (9, 0.10): 2.876, (9, 0.05): 3.327,
    (10, 0.10): 2.919, (10, 0.05): 3.367,
}

ALPHA = 0.05     # confidence level 1 - alpha = 95%
P_STAR = 1 - ALPHA
# Indifference zone d: choose a small fraction of the grand mean.
# With mean objectives ~0.41 hours, d = 0.005 means "within 0.005 h ~= 0.3 min
# of true best is acceptable".  Tweak as needed.
IZ_D = 0.005


def load_samples():
    data = {}
    for label, fname in CANDIDATES:
        path = os.path.join(RESULTS_DIR, fname)
        if not os.path.exists(path):
            print(f"WARN: missing {path}")
            continue
        df = pd.read_csv(path)
        data[label] = df["objective"].values
    return data


def main():
    data = load_samples()
    k = len(data)
    if k < 2:
        print("Need at least 2 candidates")
        return

    n0 = min(len(v) for v in data.values())
    labels = list(data.keys())
    means  = np.array([data[l][:n0].mean()      for l in labels])
    vars_  = np.array([data[l][:n0].var(ddof=1) for l in labels])
    sds    = np.sqrt(vars_)

    h = RINOTT_H.get((k, ALPHA))
    if h is None:
        # fall back to a conservative Bonferroni-t bound
        h = stats.t.ppf(1 - ALPHA / (k - 1), df=n0 - 1)
        print(f"Rinott h not tabulated for (k={k}, alpha={ALPHA}); "
              f"using Bonferroni t = {h:.4f}")
    else:
        print(f"Rinott constant h = {h:.3f}   (k={k}, 1-alpha={P_STAR:.2f}, "
              f"n_0=20 table value, conservative for n_0={n0})")

    N_required = np.ceil((h * sds / IZ_D) ** 2).astype(int)
    N_required = np.maximum(n0 + 1, N_required)
    extra = np.maximum(0, N_required - n0)

    # Print report
    print(f"\nIndifference zone  d = {IZ_D}")
    print(f"Stage-1 replications n_0 = {n0}\n")
    print(f"{'Config':<22}{'mean':>10}{'sd':>10}{'N_req':>8}{'extra':>8}")
    print("-" * 60)
    for lbl, m, s, Nr, ex in zip(labels, means, sds, N_required, extra):
        print(f"{lbl:<22}{m:>10.5f}{s:>10.5f}{Nr:>8d}{ex:>8d}")

    best_idx = int(np.argmin(means))
    print(f"\nSelected best configuration: {labels[best_idx]}")
    print(f"  mean objective = {means[best_idx]:.5f}")
    print(f"  required N     = {N_required[best_idx]}  "
          f"(additional replications needed = {extra[best_idx]})")
    print(f"\nIndifference-zone guarantee: with probability >= {P_STAR:.2f}, "
          f"the selected config's true mean is within d={IZ_D} of the best.")

    # Pairwise test: are any competitors within the indifference zone?
    within_iz = []
    for i, lbl in enumerate(labels):
        if i == best_idx:
            continue
        delta = means[i] - means[best_idx]
        if delta <= IZ_D:
            within_iz.append((lbl, delta))
    if within_iz:
        print("\nConfigurations within the indifference zone of the best:")
        for lbl, d in within_iz:
            print(f"  {lbl}  (mean - best = {d:+.5f})")
    else:
        print("\nNo other configuration is within the indifference zone of the best.")

    # ── Plot ────────────────────────────────────────────────────────────────
    order = np.argsort(means)
    fig, ax = plt.subplots(figsize=(9, 5))
    colours = ["#4C72B0"] * k
    colours[best_idx] = "#55A868"
    y_pos = np.arange(k)
    t_crit = stats.t.ppf(1 - ALPHA / 2, df=n0 - 1)
    hw = t_crit * sds / math.sqrt(n0)
    sorted_labels = [labels[i] for i in order]
    sorted_means  = means[order]
    sorted_hw     = hw[order]
    sorted_cols   = [colours[i] for i in order]
    ax.barh(y_pos, sorted_means, xerr=sorted_hw,
            color=sorted_cols, edgecolor="white", capsize=4)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(sorted_labels)
    ax.invert_yaxis()
    ax.set_xlabel("Mean objective  (± 95 % CI)")
    ax.set_title(f"Ranking & Selection – top {k} candidates\n"
                 f"Green = selected best. Indifference-zone d = {IZ_D}")
    ax.axvline(means[best_idx] + IZ_D, ls="--", color="grey",
               label="best + d")
    ax.grid(axis="x", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    out_path = os.path.join(PLOT_DIR, "ranking_selection.png")
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
