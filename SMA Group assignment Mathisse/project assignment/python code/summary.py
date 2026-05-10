"""
pareto_summary.py
=================
Prints a structured text summary of all Pareto frontiers.
Run this after the simulation and analyze_pareto.py.
Paste the full output to Claude for interpretation.

Run from the python code folder:
    python pareto_summary.py
"""

import os
import glob
import csv
import statistics

# ---------------------------------------------------------------------------
# Weights — must match the assignment specification
#   w_e = 1 / 168   (max elective appointment wait = 1 week = 168 h)
#   w_u = 1 / 9     (max urgent scan wait = 9 h)
# ---------------------------------------------------------------------------
WEIGHT_ELECTIVE = 1.0 / 168.0
WEIGHT_URGENT   = 1.0 / 9.0

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results_v2")

RULE_LABELS = {
    1: "FCFS",
    2: "Bailey-Welch K=2",
    3: "Blocking B=2",
    4: "Benchmarking",
    5: "Bailey-Welch K=3",
    6: "Bailey-Welch K=4",
    7: "Bailey-Welch K=5",
}

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_experiment_results(path):
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


def load_replication_stdevs(results_dir):
    """
    Compute std dev of the weighted objective across replications
    for each (strategy, n_urgent, rule) from the per-replication CSVs.
    Falls back to CI half-width if a file is missing.
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
            for row in csv.DictReader(f):
                el  = float(row.get("electiveAppWT") or row.get("el_app_wt") or 0)
                ur  = float(row.get("urgentScanWT")  or row.get("ur_scan_wt") or 0)
                objectives.append(WEIGHT_ELECTIVE * el + WEIGHT_URGENT * ur)
        if len(objectives) >= 2:
            stdevs[(strategy, n_urgent, rule)] = statistics.stdev(objectives)
    return stdevs


# ---------------------------------------------------------------------------
# Pareto dominance
# ---------------------------------------------------------------------------

def is_dominated(row, others, objectives):
    eps = 1e-9
    for other in others:
        if other is row:
            continue
        if all(other[o] <= row[o] + eps for o in objectives) and \
           any(other[o] <  row[o] - eps for o in objectives):
            return True
    return False


def pareto_front(rows, objectives):
    return [not is_dominated(r, rows, objectives) for r in rows]


def get_pareto_configs(rows, objectives):
    mask = pareto_front(rows, objectives)
    return [r for r, m in zip(rows, mask) if m]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def config_id(r):
    return f"S{int(r['strategy'])}-N{int(r['n_urgent'])}-R{int(r['rule'])}"


def sep(char="─", width=80):
    print(char * width)


def header(title):
    sep("═")
    print(f"  {title}")
    sep("═")


def print_frontier(configs, sort_key, stdevs, show_sd=False):
    for r in sorted(configs, key=sort_key):
        obj = WEIGHT_ELECTIVE * r["mean_electiveAppWT"] + WEIGHT_URGENT * r["mean_urgentScanWT"]
        hw  = (r["ci_hi_objective"] - r["ci_lo_objective"]) / 2
        key = (int(r["strategy"]), int(r["n_urgent"]), int(r["rule"]))
        sd  = stdevs.get(key, hw)
        line = (f"  {config_id(r):<16}"
                f"  obj={obj:.5f}"
                f"  CI±{hw:.5f}"
                f"  sd={sd:.5f}"
                f"  elAppWT={r['mean_electiveAppWT']:6.2f}h"
                f"  urScanWT={r['mean_urgentScanWT']:.3f}h"
                f"  elScanWT={r['mean_electiveScanWT']:.4f}h"
                f"  OT={r['mean_OT']:.3f}h")
        print(line)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    print()
    print("Loading data...")
    results_path = os.path.join(RESULTS_DIR, "experiment_results_v2.csv")
    rows   = load_experiment_results(results_path)
    stdevs = load_replication_stdevs(RESULTS_DIR)

    # deduplicate
    seen, deduped = set(), []
    for r in rows:
        key = (int(r["strategy"]), int(r["n_urgent"]), int(r["rule"]))
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    rows = deduped

    print(f"  {len(rows)} unique configurations")
    print(f"  {len(stdevs)} replication std devs loaded "
          f"({'complete' if len(stdevs) == len(rows) else 'INCOMPLETE — some replication CSVs missing'})")

    # augment for risk-return frontier
    augmented = []
    for r in rows:
        key = (int(r["strategy"]), int(r["n_urgent"]), int(r["rule"]))
        sd  = stdevs.get(key, (r["ci_hi_objective"] - r["ci_lo_objective"]) / 2)
        obj = WEIGHT_ELECTIVE * r["mean_electiveAppWT"] + WEIGHT_URGENT * r["mean_urgentScanWT"]
        augmented.append({**r, "_obj": obj, "_sd": sd})

    # compute frontiers
    front_eur     = get_pareto_configs(rows,      ["mean_electiveAppWT", "mean_urgentScanWT"])
    front_eot     = get_pareto_configs(rows,      ["mean_electiveAppWT", "mean_OT"])
    front_rr      = get_pareto_configs(augmented, ["_obj", "_sd"])
    front_rr_rows = [r for r in rows if config_id(r) in {config_id(x) for x in front_rr}]

    ids_eur = {config_id(r) for r in front_eur}
    ids_eot = {config_id(r) for r in front_eot}
    ids_rr  = {config_id(r) for r in front_rr_rows}
    ids_all = ids_eur & ids_eot & ids_rr
    ids_any = ids_eur | ids_eot | ids_rr

    # ── Output ───────────────────────────────────────────────────────────

    header("FRONTIER 1: Elective appointment wait vs Urgent scan wait")
    print(f"  {len(front_eur)} Pareto-efficient configurations\n")
    print_frontier(front_eur, lambda r: r["mean_electiveAppWT"], stdevs)

    print()
    header("FRONTIER 2: Elective appointment wait vs Overtime")
    print(f"  {len(front_eot)} Pareto-efficient configurations\n")
    print_frontier(front_eot, lambda r: r["mean_electiveAppWT"], stdevs)

    print()
    header("FRONTIER 3: Risk-return (mean objective vs std dev)")
    print(f"  {len(front_rr_rows)} Pareto-efficient configurations\n")
    print_frontier(front_rr_rows, lambda r: r["mean_objective"], stdevs)

    print()
    header("CONFIGURATIONS ON ALL THREE FRONTIERS SIMULTANEOUSLY")
    all_configs = [r for r in rows if config_id(r) in ids_all]
    if all_configs:
        print(f"  {len(all_configs)} configurations\n")
        print_frontier(all_configs, lambda r: r["mean_objective"], stdevs)
    else:
        print("  None.")

    print()
    header("CONFIGURATIONS ON AT LEAST TWO FRONTIERS")
    two_plus = [r for r in rows if len([1 for ids in [ids_eur, ids_eot, ids_rr]
                                        if config_id(r) in ids]) >= 2]
    print(f"  {len(two_plus)} configurations\n")
    for r in sorted(two_plus, key=lambda r: r["mean_objective"]):
        obj    = WEIGHT_ELECTIVE * r["mean_electiveAppWT"] + WEIGHT_URGENT * r["mean_urgentScanWT"]
        hw     = (r["ci_hi_objective"] - r["ci_lo_objective"]) / 2
        key    = (int(r["strategy"]), int(r["n_urgent"]), int(r["rule"]))
        sd     = stdevs.get(key, hw)
        f_on   = ("EUR " if config_id(r) in ids_eur else "    ") + \
                 ("EOT " if config_id(r) in ids_eot else "    ") + \
                 ("RR"   if config_id(r) in ids_rr  else "  ")
        print(f"  {config_id(r):<16}  [{f_on}]"
              f"  obj={obj:.5f}  CI±{hw:.5f}  sd={sd:.5f}"
              f"  elAppWT={r['mean_electiveAppWT']:6.2f}h"
              f"  urScanWT={r['mean_urgentScanWT']:.3f}h"
              f"  OT={r['mean_OT']:.3f}h")

    print()
    header("RULE FREQUENCY ACROSS ALL THREE FRONTIERS")
    print(f"  (each frontier counts independently; max = 3)\n")
    rule_counts = {r: 0 for r in RULE_LABELS}
    for front in [front_eur, front_eot, front_rr_rows]:
        for r in front:
            rule_counts[int(r["rule"])] += 1
    for rule in sorted(rule_counts, key=lambda r: -rule_counts[r]):
        bar = "█" * rule_counts[rule]
        print(f"  R{rule}  {RULE_LABELS[rule]:<22}  {bar:<5}  ({rule_counts[rule]})")

    print()
    header("BEST CONFIGURATION PER STRATEGY")
    for s in [1, 2, 3]:
        best = min([r for r in rows if int(r["strategy"]) == s],
                   key=lambda r: r["mean_objective"])
        obj = WEIGHT_ELECTIVE * best["mean_electiveAppWT"] + WEIGHT_URGENT * best["mean_urgentScanWT"]
        hw  = (best["ci_hi_objective"] - best["ci_lo_objective"]) / 2
        key = (int(best["strategy"]), int(best["n_urgent"]), int(best["rule"]))
        sd  = stdevs.get(key, hw)
        print(f"  Strategy {s}: {config_id(best)}"
              f"  obj={obj:.5f}  CI±{hw:.5f}  sd={sd:.5f}"
              f"  elAppWT={best['mean_electiveAppWT']:.2f}h"
              f"  urScanWT={best['mean_urgentScanWT']:.3f}h"
              f"  OT={best['mean_OT']:.3f}h")

    print()
    header("MONOTONICITY CHECK: urScanWT and elAppWT vs N (Strategy 3, Rule 4)")
    s3r4 = sorted([r for r in rows if int(r["strategy"]) == 3 and int(r["rule"]) == 4],
                  key=lambda r: r["n_urgent"])
    for r in s3r4:
        obj = WEIGHT_ELECTIVE * r["mean_electiveAppWT"] + WEIGHT_URGENT * r["mean_urgentScanWT"]
        print(f"  N={int(r['n_urgent']):2}  obj={obj:.5f}"
              f"  elAppWT={r['mean_electiveAppWT']:7.2f}h"
              f"  urScanWT={r['mean_urgentScanWT']:.3f}h"
              f"  OT={r['mean_OT']:.3f}h")

    print()
    sep("═")
    print()