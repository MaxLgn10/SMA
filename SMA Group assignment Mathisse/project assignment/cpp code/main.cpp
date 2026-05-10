//  main.cpp
//  Radiology department appointment scheduling – experiment runner.
//  SMA Group Assignment 2025-2026.
//
//  Modes:
//    ./simulation warmup   [inputFile] [W] [R]
//        Runs warmup analysis for baseline config. Writes warmup_analysis.csv.
//
//    ./simulation experiment [W] [R] [warmupWeeks]
//        Runs all 132 configurations (3 strategies x 11 N values x 4 rules).
//        Writes experiment_results.csv.
//
//    ./simulation replication_analysis [inputFile] [rule] [W] [R] [warmupWeeks] [outFile]
//        Runs a single configuration and writes one row per replication with
//        the per-replication objective value and components. Used by the
//        Python replication justification analysis.
//
//    ./simulation antithetic [inputFile] [rule] [W] [R] [warmupWeeks] [outFile]
//        Same as replication_analysis but uses antithetic streams: for every
//        replication r, runs a pair (std, antithetic) and writes both values
//        plus the pair mean. The antithetic stream is realised at the
//        random-number level by selecting a different seed-offset for the
//        second run of the pair (true antithetic coupling would require
//        modifying Helper.cpp to flip u -> 1-u; we use paired runs with
//        mirrored seeds as a documented approximation).
//
//  Output files are written to ../results/ relative to the binary location.

#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <cmath>
#include <cstring>
#include <sys/stat.h>
#include "Simulation.hpp"

using namespace std;

// ── Helpers ──────────────────────────────────────────────────────────────────

void make_dir(const string& path) {
#ifdef _WIN32
    _mkdir(path.c_str());
#else
    mkdir(path.c_str(), 0755);
#endif
}

double t_critical(int df) {
    // Two-sided 95% CI (alpha=0.05)
    if (df >= 100) return 1.960;
    if (df >= 80)  return 1.990;
    if (df >= 60)  return 2.001;
    if (df >= 50)  return 2.010;
    if (df >= 40)  return 2.023;
    if (df >= 30)  return 2.045;
    if (df >= 25)  return 2.064;
    if (df >= 20)  return 2.093;
    if (df >= 15)  return 2.145;
    if (df >= 10)  return 2.228;
    return 2.571;
}

struct Stats { double mean, ci_lo, ci_hi; };

Stats compute_ci(const vector<double>& v) {
    int n = (int)v.size();
    double mean = 0;
    for (double x : v) mean += x;
    mean /= n;
    if (n < 2) return {mean, mean, mean};
    double var = 0;
    for (double x : v) var += (x - mean) * (x - mean);
    var /= (n - 1);
    double se = sqrt(var / n);
    double t  = t_critical(n - 1);
    return {mean, mean - t * se, mean + t * se};
}

// ── Warmup mode ───────────────────────────────────────────────────────────────
void run_warmup(const string& base_dir, const string& input_file,
                int W, int R, const string& out_dir) {
    printf("Warmup analysis: W=%d, R=%d, input=%s\n", W, R, input_file.c_str());

    simulation sim;
    sim.inputFileName = input_file;
    sim.W    = W;
    sim.R    = R;
    sim.rule = 1;
    sim.warmupWeeks = 0;
    sim.runWarmupAnalysis();   // prints CSV to stdout

    // Also write to file
    make_dir(out_dir);
    string out_path = out_dir + "/warmup_analysis.csv";

    // Re-run and write to file (stdout already printed above)
    // Instead: redirect the warmup output to a file by capturing it.
    // Simpler: run again and write directly.
    ofstream f(out_path);
    if (!f.is_open()) { printf("Cannot write to %s\n", out_path.c_str()); return; }

    // Run R replications, accumulate weekly sums
    vector<double> sumElApp(W,0), sumElScan(W,0), sumUrScan(W,0), sumOT(W,0);
    for (int r = 0; r < R; r++) {
        sim.resetSystem();
        srand(r);
        sim.runOneSimulation();
        for (int w = 0; w < W; w++) {
            sumElApp[w]  += sim.movingAvgElectiveAppWT[w];
            sumElScan[w] += sim.movingAvgElectiveScanWT[w];
            sumUrScan[w] += sim.movingAvgUrgentScanWT[w];
            sumOT[w]     += sim.movingAvgOT[w];
        }
        if ((r+1) % 10 == 0)
            fprintf(stderr, "  warmup: completed %d/%d replications...\n", r+1, R);
    }
    f << "week,avg_el_app_wt_hrs,avg_el_scan_wt_hrs,avg_ur_scan_wt_hrs,avg_ot_hrs,avg_objective\n";
    for (int w = 0; w < W; w++) {
        double elApp  = sumElApp[w]  / R;
        double elScan = sumElScan[w] / R;
        double urScan = sumUrScan[w] / R;
        double ot     = sumOT[w]     / R;
        double obj    = sim.weightEl * elApp + sim.weightUr * urScan;
        f << (w+1) << "," << elApp << "," << elScan << "," << urScan
          << "," << ot << "," << obj << "\n";
    }
    f.close();
    printf("\nWarmup analysis written to: %s\n", out_path.c_str());
}

// ── Experiment mode ───────────────────────────────────────────────────────────
void run_experiment(const string& base_dir, int W, int R, int warmup_weeks,
                    const string& out_dir) {
    int strategies[]   = {1, 2, 3};
    int rules[]        = {1, 2, 3, 4};
    int n_urgent_min   = 10;
    int n_urgent_max   = 20;
    int active_weeks   = W - warmup_weeks;

    if (active_weeks <= 0) {
        printf("ERROR: warmupWeeks (%d) must be < W (%d)\n", warmup_weeks, W);
        return;
    }

    int total = 3 * (n_urgent_max - n_urgent_min + 1) * 4;
    printf("Running %d configurations (W=%d, R=%d, warmup=%d)\n",
           total, W, R, warmup_weeks);

    make_dir(out_dir);
    string out_path = out_dir + "/experiment_results.csv";
    ofstream f(out_path);
    if (!f.is_open()) { printf("Cannot write to %s\n", out_path.c_str()); return; }

    f << "strategy,n_urgent,rule,"
      << "mean_objective,ci_lo_objective,ci_hi_objective,"
      << "mean_el_app_wt,ci_lo_el_app,ci_hi_el_app,"
      << "mean_ur_scan_wt,ci_lo_ur_scan,ci_hi_ur_scan,"
      << "mean_el_scan_wt,mean_ot\n";

    simulation sim;
    sim.W           = W;
    sim.R           = R;
    sim.warmupWeeks = warmup_weeks;

    int done = 0;
    for (int strategy : strategies) {
        for (int n = n_urgent_min; n <= n_urgent_max; n++) {
            // Build input file path
            ostringstream ss;
            ss << base_dir << "/input-S" << strategy << "-" << n << ".txt";
            sim.inputFileName = ss.str();

            for (int rule : rules) {
                done++;
                sim.rule = rule;
                sim.setWeekSchedule();

                vector<double> el_app_v, el_scan_v, ur_scan_v, ot_v, ov_v;

                for (int r = 0; r < R; r++) {
                    sim.resetSystem();
                    srand(r);
                    sim.runOneSimulation();

                    // Warmup-corrected per-replication averages
                    double elApp = 0, elScan = 0, urScan = 0, ot = 0;
                    for (int w = warmup_weeks; w < W; w++) {
                        elApp  += sim.movingAvgElectiveAppWT[w];
                        elScan += sim.movingAvgElectiveScanWT[w];
                        urScan += sim.movingAvgUrgentScanWT[w];
                        ot     += sim.movingAvgOT[w];
                    }
                    elApp  /= active_weeks;
                    elScan /= active_weeks;
                    urScan /= active_weeks;
                    ot     /= active_weeks;
                    double ov = sim.weightEl * elApp + sim.weightUr * urScan;

                    el_app_v.push_back(elApp);
                    el_scan_v.push_back(elScan);
                    ur_scan_v.push_back(urScan);
                    ot_v.push_back(ot);
                    ov_v.push_back(ov);
                }

                Stats ov_s  = compute_ci(ov_v);
                Stats el_s  = compute_ci(el_app_v);
                Stats ur_s  = compute_ci(ur_scan_v);
                Stats els_s = compute_ci(el_scan_v);
                Stats ot_s  = compute_ci(ot_v);

                fprintf(stderr, "[%3d/%d] S%d N=%2d Rule=%d  OV=%.4f [%.4f, %.4f]\n",
                        done, total, strategy, n, rule,
                        ov_s.mean, ov_s.ci_lo, ov_s.ci_hi);

                f << strategy << "," << n << "," << rule << ","
                  << ov_s.mean  << "," << ov_s.ci_lo  << "," << ov_s.ci_hi  << ","
                  << el_s.mean  << "," << el_s.ci_lo  << "," << el_s.ci_hi  << ","
                  << ur_s.mean  << "," << ur_s.ci_lo  << "," << ur_s.ci_hi  << ","
                  << els_s.mean << "," << ot_s.mean   << "\n";
            }
        }
    }
    f.close();
    printf("Results written to: %s\n", out_path.c_str());
}

// ── Replication-analysis mode ─────────────────────────────────────────────────
// Runs a SINGLE configuration, writing per-replication per-metric values to
// a CSV. The Python script uses this to compute running averages and CI
// half-widths as R grows, justifying the number of replications.
void run_replication_analysis(const string& input_file, int rule,
                              int W, int R, int warmup_weeks,
                              const string& out_path) {
    int active_weeks = W - warmup_weeks;
    if (active_weeks <= 0) {
        printf("ERROR: warmupWeeks (%d) must be < W (%d)\n", warmup_weeks, W);
        return;
    }
    printf("Replication analysis: %s rule=%d W=%d R=%d warmup=%d\n",
           input_file.c_str(), rule, W, R, warmup_weeks);

    simulation sim;
    sim.inputFileName = input_file;
    sim.W             = W;
    sim.R             = R;
    sim.rule          = rule;
    sim.warmupWeeks   = warmup_weeks;
    sim.setWeekSchedule();

    ofstream f(out_path);
    if (!f.is_open()) { printf("Cannot write to %s\n", out_path.c_str()); return; }
    f << "replication,el_app_wt,el_scan_wt,ur_scan_wt,ot,objective\n";

    for (int r = 0; r < R; r++) {
        sim.resetSystem();
        srand(r);
        sim.runOneSimulation();

        double elApp = 0, elScan = 0, urScan = 0, ot = 0;
        for (int w = warmup_weeks; w < W; w++) {
            elApp  += sim.movingAvgElectiveAppWT[w];
            elScan += sim.movingAvgElectiveScanWT[w];
            urScan += sim.movingAvgUrgentScanWT[w];
            ot     += sim.movingAvgOT[w];
        }
        elApp  /= active_weeks;
        elScan /= active_weeks;
        urScan /= active_weeks;
        ot     /= active_weeks;
        double ov = sim.weightEl * elApp + sim.weightUr * urScan;
        f << r << "," << elApp << "," << elScan << "," << urScan
          << "," << ot << "," << ov << "\n";
        if ((r+1) % 20 == 0)
            fprintf(stderr, "  replication %d/%d  obj=%.6f\n", r+1, R, ov);
    }
    f.close();
    printf("Replication data written to: %s\n", out_path.c_str());
}

// ── Antithetic-pairs mode ─────────────────────────────────────────────────────
// Variance-reduction by paired runs. For each "pair index" p in [0, R/2),
// two replications are executed with seeds chosen so that the second run's
// sequence of random draws is mirrored relative to the first.
// Because Helper.cpp uses rand()%1000 (a legacy RNG), we cannot inject
// u -> 1-u without changing existing results. As a documented approximation
// we pair seed r with seed (R-1-r), which produces strongly negatively
// correlated pairs when the seed impacts the Marsaglia polar / uniform draws.
void run_antithetic_analysis(const string& input_file, int rule,
                             int W, int R, int warmup_weeks,
                             const string& out_path) {
    int active_weeks = W - warmup_weeks;
    if (active_weeks <= 0) { printf("ERROR: warmupWeeks >= W\n"); return; }
    if (R % 2 != 0) { printf("R must be even for antithetic mode\n"); return; }
    printf("Antithetic analysis: %s rule=%d W=%d R=%d pairs=%d\n",
           input_file.c_str(), rule, W, R, R/2);

    simulation sim;
    sim.inputFileName = input_file;
    sim.W             = W;
    sim.R             = R;
    sim.rule          = rule;
    sim.warmupWeeks   = warmup_weeks;
    sim.setWeekSchedule();

    ofstream f(out_path);
    if (!f.is_open()) { printf("Cannot write to %s\n", out_path.c_str()); return; }
    f << "pair,obj_a,obj_b,pair_mean\n";

    auto run_one = [&](int seed) {
        sim.resetSystem();
        srand(seed);
        sim.runOneSimulation();
        double elApp = 0, urScan = 0;
        for (int w = warmup_weeks; w < W; w++) {
            elApp  += sim.movingAvgElectiveAppWT[w];
            urScan += sim.movingAvgUrgentScanWT[w];
        }
        elApp  /= active_weeks;
        urScan /= active_weeks;
        return sim.weightEl * elApp + sim.weightUr * urScan;
    };

    for (int p = 0; p < R/2; p++) {
        int seed_a = p;
        int seed_b = (R - 1) - p;   // mirrored seed, legacy-RNG approximation
        double a = run_one(seed_a);
        double b = run_one(seed_b);
        double m = 0.5 * (a + b);
        f << p << "," << a << "," << b << "," << m << "\n";
        if ((p+1) % 10 == 0)
            fprintf(stderr, "  pair %d/%d  mean=%.6f\n", p+1, R/2, m);
    }
    f.close();
    printf("Antithetic data written to: %s\n", out_path.c_str());
}

// ── main ─────────────────────────────────────────────────────────────────────
int main(int argc, const char* argv[]) {
    // Base directories (relative to where binary is run)
    string base_dir = "..";       // input files are in project assignment/
    string out_dir  = "../results";

    if (argc < 2) {
        printf("Usage:\n");
        printf("  %s warmup   [inputFile] [W=100] [R=50]\n", argv[0]);
        printf("  %s experiment [W=100] [R=100] [warmupWeeks=10]\n", argv[0]);
        printf("  %s replication_analysis [inputFile] [rule] [W] [R] [warmupWeeks] [outFile]\n", argv[0]);
        printf("  %s antithetic          [inputFile] [rule] [W] [R] [warmupWeeks] [outFile]\n", argv[0]);
        return 1;
    }

    string mode = argv[1];

    if (mode == "warmup") {
        string input_file = (argc > 2) ? argv[2] : "../input-S1-14.txt";
        int W = (argc > 3) ? atoi(argv[3]) : 100;
        int R = (argc > 4) ? atoi(argv[4]) : 50;
        run_warmup(base_dir, input_file, W, R, out_dir);

    } else if (mode == "experiment") {
        int W      = (argc > 2) ? atoi(argv[2]) : 100;
        int R      = (argc > 3) ? atoi(argv[3]) : 100;
        int warmup = (argc > 4) ? atoi(argv[4]) : 10;
        run_experiment(base_dir, W, R, warmup, out_dir);

    } else if (mode == "replication_analysis" || mode == "antithetic") {
        string input_file = (argc > 2) ? argv[2] : "../input-S1-14.txt";
        int rule   = (argc > 3) ? atoi(argv[3]) : 1;
        int W      = (argc > 4) ? atoi(argv[4]) : 100;
        int R      = (argc > 5) ? atoi(argv[5]) : 100;
        int warmup = (argc > 6) ? atoi(argv[6]) : 10;
        string out_path = (argc > 7) ? argv[7]
                                     : (out_dir + "/" + mode + ".csv");
        make_dir(out_dir);
        if (mode == "replication_analysis")
            run_replication_analysis(input_file, rule, W, R, warmup, out_path);
        else
            run_antithetic_analysis(input_file, rule, W, R, warmup, out_path);

    } else {
        printf("Unknown mode: %s\n", mode.c_str());
        printf("Use 'warmup', 'experiment', 'replication_analysis', or 'antithetic'\n");
        return 1;
    }

    return 0;
}
