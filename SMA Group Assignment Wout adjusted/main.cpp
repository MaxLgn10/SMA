#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#ifdef _WIN32
#include <direct.h>
#else
#include <sys/stat.h>
#endif

#include "Simulation.hpp"

using namespace std;

struct Metrics {
    double elApp = 0.0;
    double elScan = 0.0;
    double urScan = 0.0;
    double ot = 0.0;
    double objective = 0.0;
};

struct Stats {
    double mean = 0.0;
    double lo = 0.0;
    double hi = 0.0;
};

void make_dir(const string &path) {
#ifdef _WIN32
    _mkdir(path.c_str());
#else
    mkdir(path.c_str(), 0755);
#endif
}

double t_critical_95(int df) {
    if (df >= 120) return 1.980;
    if (df >= 100) return 1.984;
    if (df >= 80) return 1.990;
    if (df >= 60) return 2.000;
    if (df >= 50) return 2.009;
    if (df >= 40) return 2.021;
    if (df >= 30) return 2.042;
    if (df >= 25) return 2.060;
    if (df >= 20) return 2.086;
    if (df >= 15) return 2.131;
    if (df >= 10) return 2.228;
    if (df >= 5) return 2.571;
    return 4.303;
}

Stats compute_ci(const vector<double> &values) {
    Stats s;
    const int n = static_cast<int>(values.size());
    if (n == 0) return s;

    for (double x : values) s.mean += x;
    s.mean /= n;

    if (n == 1) {
        s.lo = s.mean;
        s.hi = s.mean;
        return s;
    }

    double var = 0.0;
    for (double x : values) var += (x - s.mean) * (x - s.mean);
    var /= (n - 1);

    double se = sqrt(var / n);
    double t = t_critical_95(n - 1);
    s.lo = s.mean - t * se;
    s.hi = s.mean + t * se;
    return s;
}

Metrics run_replication(simulation &sim, int seed, int warmupWeeks) {
    sim.resetSystem();
    // Fix 2: seed all six CRN streams; no global srand.
    sim.seed_streams(seed);
    sim.runOneSimulation();

    int firstWeek = max(0, warmupWeeks);
    int activeWeeks = sim.W - firstWeek;
    if (activeWeeks <= 0) {
        cerr << "ERROR: warmupWeeks must be smaller than W." << endl;
        exit(1);
    }

    Metrics m;
    for (int w = firstWeek; w < sim.W; w++) {
        m.elApp += sim.movingAvgElectiveAppWT[w];
        m.elScan += sim.movingAvgElectiveScanWT[w];
        m.urScan += sim.movingAvgUrgentScanWT[w];
        m.ot += sim.movingAvgOT[w];
    }

    m.elApp /= activeWeeks;
    m.elScan /= activeWeeks;
    m.urScan /= activeWeeks;
    m.ot /= activeWeeks;
    m.objective = sim.weightEl * m.elApp + sim.weightUr * m.urScan;
    return m;
}

void write_single_config(const string &inputFile, int rule, int W, int R, int warmupWeeks,
                         bool urgentTwoBlocks, const string &outFile) {
    simulation sim;
    sim.inputFileName = inputFile;
    sim.rule = rule;
    sim.W = W;
    sim.R = R;
    sim.warmupWeeks = warmupWeeks;
    sim.urgentArrivalTwoBlocks = urgentTwoBlocks;
    sim.setWeekSchedule();

    ofstream out(outFile);
    if (!out.is_open()) {
        cerr << "ERROR: cannot write " << outFile << endl;
        exit(1);
    }

    out << "replication,el_app_wt,el_scan_wt,ur_scan_wt,ot,objective\n";
    vector<double> objectives;
    vector<double> elAppValues;
    vector<double> urScanValues;

    for (int r = 0; r < R; r++) {
        Metrics m = run_replication(sim, r, warmupWeeks);
        objectives.push_back(m.objective);
        elAppValues.push_back(m.elApp);
        urScanValues.push_back(m.urScan);
        out << r << "," << setprecision(10) << m.elApp << "," << m.elScan << ","
            << m.urScan << "," << m.ot << "," << m.objective << "\n";
    }
    out.close();

    Stats obj = compute_ci(objectives);
    Stats el = compute_ci(elAppValues);
    Stats ur = compute_ci(urScanValues);

    cout << "Single configuration written to: " << outFile << endl;
    cout << fixed << setprecision(6)
         << "Mean objective = " << obj.mean << " [" << obj.lo << ", " << obj.hi << "]\n"
         << "Mean elective appointment WT = " << el.mean << " h\n"
         << "Mean urgent scan WT = " << ur.mean << " h\n";
}

void write_warmup(const string &inputFile, int rule, int W, int R, bool urgentTwoBlocks, const string &outFile) {
    simulation sim;
    sim.inputFileName = inputFile;
    sim.rule = rule;
    sim.W = W;
    sim.R = R;
    sim.warmupWeeks = 0;
    sim.urgentArrivalTwoBlocks = urgentTwoBlocks;
    sim.setWeekSchedule();

    vector<double> sumElApp(W, 0.0), sumElScan(W, 0.0), sumUrScan(W, 0.0), sumOT(W, 0.0);

    for (int r = 0; r < R; r++) {
        sim.resetSystem();
        // Fix 2: seed all six CRN streams; no global srand.
        sim.seed_streams(r);
        sim.runOneSimulation();
        for (int w = 0; w < W; w++) {
            sumElApp[w] += sim.movingAvgElectiveAppWT[w];
            sumElScan[w] += sim.movingAvgElectiveScanWT[w];
            sumUrScan[w] += sim.movingAvgUrgentScanWT[w];
            sumOT[w] += sim.movingAvgOT[w];
        }
    }

    ofstream out(outFile);
    if (!out.is_open()) {
        cerr << "ERROR: cannot write " << outFile << endl;
        exit(1);
    }

    out << "week,avg_el_app_wt_hrs,avg_el_scan_wt_hrs,avg_ur_scan_wt_hrs,avg_ot_hrs,avg_objective\n";
    for (int w = 0; w < W; w++) {
        double elApp = sumElApp[w] / R;
        double elScan = sumElScan[w] / R;
        double urScan = sumUrScan[w] / R;
        double ot = sumOT[w] / R;
        double objective = sim.weightEl * elApp + sim.weightUr * urScan;
        out << (w + 1) << "," << setprecision(10) << elApp << "," << elScan << ","
            << urScan << "," << ot << "," << objective << "\n";
    }
    out.close();
    cout << "Warmup CSV written to: " << outFile << endl;
}

void write_experiment(int W, int R, int warmupWeeks, bool urgentTwoBlocks, const string &inputDir, const string &outFile) {
    ofstream out(outFile);
    if (!out.is_open()) {
        cerr << "ERROR: cannot write " << outFile << endl;
        exit(1);
    }

    // Per-replication file for convergence analysis and paired t-tests.
    string repFile = outFile.substr(0, outFile.rfind('.')) + "_per_rep.csv";
    ofstream outRep(repFile);
    if (!outRep.is_open()) {
        cerr << "WARNING: cannot write per-rep file " << repFile << endl;
    }

    out << "strategy,n_urgent,rule,mean_objective,ci_lo_objective,ci_hi_objective,"
        << "mean_el_app_wt,ci_lo_el_app,ci_hi_el_app,"
        << "mean_ur_scan_wt,ci_lo_ur_scan,ci_hi_ur_scan,"
        << "mean_el_scan_wt,mean_ot\n";
    if (outRep.is_open())
        outRep << "strategy,n_urgent,rule,rep,objective,el_app_wt,ur_scan_wt,el_scan_wt,ot\n";

    simulation sim;
    sim.W = W;
    sim.R = R;
    sim.warmupWeeks = warmupWeeks;
    sim.urgentArrivalTwoBlocks = urgentTwoBlocks;

    const int total = 3 * 11 * 4;
    int done = 0;

    for (int strategy = 1; strategy <= 3; strategy++) {
        for (int nUrgent = 10; nUrgent <= 20; nUrgent++) {
            ostringstream filename;
            filename << inputDir << "/input-S" << strategy << "-" << nUrgent << ".txt";
            sim.inputFileName = filename.str();

            for (int rule = 1; rule <= 4; rule++) {
                done++;
                sim.rule = rule;
                sim.setWeekSchedule();

                vector<double> objectives, elApps, urScans, elScans, ots;
                for (int r = 0; r < R; r++) {
                    Metrics m = run_replication(sim, r, warmupWeeks);
                    objectives.push_back(m.objective);
                    elApps.push_back(m.elApp);
                    urScans.push_back(m.urScan);
                    elScans.push_back(m.elScan);
                    ots.push_back(m.ot);
                    if (outRep.is_open())
                        outRep << strategy << "," << nUrgent << "," << rule << "," << r << ","
                               << setprecision(10) << m.objective << "," << m.elApp << ","
                               << m.urScan << "," << m.elScan << "," << m.ot << "\n";
                }

                Stats obj = compute_ci(objectives);
                Stats el = compute_ci(elApps);
                Stats ur = compute_ci(urScans);
                Stats elScan = compute_ci(elScans);
                Stats ot = compute_ci(ots);

                cerr << "[" << done << "/" << total << "] S" << strategy
                     << " N=" << nUrgent << " rule=" << rule
                     << " objective=" << fixed << setprecision(5) << obj.mean << endl;

                out << strategy << "," << nUrgent << "," << rule << ","
                    << setprecision(10) << obj.mean << "," << obj.lo << "," << obj.hi << ","
                    << el.mean << "," << el.lo << "," << el.hi << ","
                    << ur.mean << "," << ur.lo << "," << ur.hi << ","
                    << elScan.mean << "," << ot.mean << "\n";
            }
        }
    }

    out.close();
    if (outRep.is_open()) outRep.close();
    cout << "Experiment CSV written to: " << outFile << endl;
    cout << "Per-replication CSV written to: " << repFile << endl;
}

// ---------------------------------------------------------------------------
// Welch analysis: determines warm-up period via moving-average method.
// Runs R replications of W weeks (no warmup applied), computes per-week mean
// of the objective, then applies a centered moving average of half-width
// movAvgHW.  Recommends the first week whose moving average is within
// tolerance (default 1%) of the long-run mean (average of last quarter).
// ---------------------------------------------------------------------------
int analyze_welch(const string &inputFile, int rule, int W, int R,
                  bool urgentTwoBlocks, int movAvgHW, double tolerance,
                  const string &outFile) {
    simulation sim;
    sim.inputFileName = inputFile;
    sim.rule = rule;
    sim.W = W;
    sim.R = R;
    sim.warmupWeeks = 0;
    sim.urgentArrivalTwoBlocks = urgentTwoBlocks;
    sim.setWeekSchedule();

    vector<double> sumObj(W, 0.0), sumElApp(W, 0.0), sumUrScan(W, 0.0);

    cerr << "Welch analysis: running " << R << " reps x " << W << " weeks..." << endl;
    for (int r = 0; r < R; r++) {
        sim.resetSystem();
        sim.seed_streams(r);
        sim.runOneSimulation();
        for (int w = 0; w < W; w++) {
            double obj = sim.weightEl * sim.movingAvgElectiveAppWT[w]
                       + sim.weightUr * sim.movingAvgUrgentScanWT[w];
            sumObj[w]    += obj;
            sumElApp[w]  += sim.movingAvgElectiveAppWT[w];
            sumUrScan[w] += sim.movingAvgUrgentScanWT[w];
        }
    }

    vector<double> meanObj(W), meanElApp(W), meanUrScan(W), movAvg(W);
    for (int w = 0; w < W; w++) {
        meanObj[w]    = sumObj[w]    / R;
        meanElApp[w]  = sumElApp[w]  / R;
        meanUrScan[w] = sumUrScan[w] / R;
    }

    // Centered moving average (trailing at edges).
    for (int w = 0; w < W; w++) {
        int lo = max(0, w - movAvgHW);
        int hi = min(W - 1, w + movAvgHW);
        double s = 0.0;
        for (int i = lo; i <= hi; i++) s += meanObj[i];
        movAvg[w] = s / (hi - lo + 1);
    }

    // Long-run reference: mean of last quarter of moving-average values.
    int qStart = W * 3 / 4;
    double steadyMean = 0.0;
    for (int w = qStart; w < W; w++) steadyMean += movAvg[w];
    steadyMean /= (W - qStart);

    // First week within tolerance of the steady-state mean.
    int recommended = W / 4;  // fallback
    for (int w = 0; w < qStart; w++) {
        if (fabs(movAvg[w] - steadyMean) / steadyMean <= tolerance) {
            recommended = w;
            break;
        }
    }

    ofstream out(outFile);
    out << "week,mean_objective,moving_avg_objective,mean_el_app_wt_hrs,mean_ur_scan_wt_hrs\n";
    for (int w = 0; w < W; w++) {
        out << (w + 1) << "," << setprecision(10)
            << meanObj[w] << "," << movAvg[w] << ","
            << meanElApp[w] << "," << meanUrScan[w] << "\n";
    }
    out << "\n# steady_state_mean_objective," << steadyMean << "\n";
    out << "# recommended_warmup_weeks," << recommended << "\n";
    out.close();

    cout << fixed << setprecision(6)
         << "Welch CSV written to: " << outFile << "\n"
         << "Steady-state mean objective : " << steadyMean << "\n"
         << "Recommended warmup          : " << recommended << " weeks\n";
    return recommended;
}

// ---------------------------------------------------------------------------
// Pilot study: determines required number of replications.
// Runs n_pilot replications with the given warmup and uses the formula
//   n >= ceil( (z_{alpha/2} * s / (epsilon * mu))^2 )
// with epsilon = desired relative half-width (default 5%) and alpha = 0.05.
// Enforces a minimum of 30 replications (Central Limit Theorem).
// ---------------------------------------------------------------------------
int analyze_pilot(const string &inputFile, int rule, int W, int warmup,
                  int nPilot, double epsilon, bool urgentTwoBlocks,
                  const string &outFile) {
    simulation sim;
    sim.inputFileName = inputFile;
    sim.rule = rule;
    sim.W = W;
    sim.R = nPilot;
    sim.warmupWeeks = warmup;
    sim.urgentArrivalTwoBlocks = urgentTwoBlocks;
    sim.setWeekSchedule();

    cerr << "Pilot study: running " << nPilot << " replications..." << endl;
    vector<double> objectives, elApps, urScans;
    for (int r = 0; r < nPilot; r++) {
        Metrics m = run_replication(sim, r, warmup);
        objectives.push_back(m.objective);
        elApps.push_back(m.elApp);
        urScans.push_back(m.urScan);
    }

    Stats obj  = compute_ci(objectives);
    Stats elA  = compute_ci(elApps);
    Stats urS  = compute_ci(urScans);

    double var = 0.0;
    for (double x : objectives) var += (x - obj.mean) * (x - obj.mean);
    var /= (nPilot - 1);
    double stddev = sqrt(var);

    // Use t_{alpha/2, nPilot-1} — correct for small pilot samples.
    double t = t_critical_95(nPilot - 1);
    double nExact = (t * stddev / (epsilon * obj.mean)) * (t * stddev / (epsilon * obj.mean));
    int nRequired = static_cast<int>(ceil(nExact));
    int nRecommended = max(30, nRequired);

    ofstream out(outFile);
    out << "replication,objective,el_app_wt_hrs,ur_scan_wt_hrs\n";
    for (int i = 0; i < nPilot; i++) {
        out << i << "," << setprecision(10)
            << objectives[i] << "," << elApps[i] << "," << urScans[i] << "\n";
    }
    out << "\n# pilot_n," << nPilot << "\n";
    out << "# mean_objective," << obj.mean << "\n";
    out << "# ci95_objective,[" << obj.lo << "," << obj.hi << "]\n";
    out << "# std_objective," << stddev << "\n";
    out << "# mean_el_app_wt_hrs," << elA.mean << "\n";
    out << "# mean_ur_scan_wt_hrs," << urS.mean << "\n";
    out << "# epsilon," << epsilon << "\n";
    out << "# t_alpha2_df" << (nPilot-1) << "," << t << "\n";
    out << "# n_exact," << nExact << "\n";
    out << "# n_required (ceil)," << nRequired << "\n";
    out << "# n_recommended (max 30)," << nRecommended << "\n";
    out.close();

    cout << fixed << setprecision(6)
         << "Pilot CSV written to: " << outFile << "\n"
         << "Mean objective   : " << obj.mean
         << "  95% CI [" << obj.lo << ", " << obj.hi << "]\n"
         << "Std objective    : " << stddev << "\n"
         << "Mean AWT_e (hrs) : " << elA.mean << "\n"
         << "Mean SWT_u (hrs) : " << urS.mean << "\n"
         << "t_{0.025, df=" << (nPilot-1) << "} : " << t << "\n"
         << "n_exact          : " << nExact << "\n"
         << "Recommended R    : " << nRecommended
         << "  (epsilon=" << epsilon << ", min=30)\n";
    return nRecommended;
}

void print_usage(const char *program) {
    cout << "Usage:\n"
         << "  " << program << " single     [inputFile] [rule] [W] [R] [warmup] [urgentTwoBlocks=0|1] [outFile]\n"
         << "  " << program << " warmup     [inputFile] [rule] [W] [R] [urgentTwoBlocks=0|1] [outFile]\n"
         << "  " << program << " welch      [inputFile] [rule] [W] [R] [urgentTwoBlocks=0|1] [movAvgHW=4] [tol=0.01] [outFile]\n"
         << "  " << program << " pilot      [inputFile] [rule] [W] [warmup] [nPilot=10] [epsilon=0.05] [urgentTwoBlocks=0|1] [outFile]\n"
         << "  " << program << " experiment [W] [R] [warmup] [urgentTwoBlocks=0|1] [inputDir] [outFile]\n";
}

int main(int argc, const char *argv[]) {
    make_dir("results");

    if (argc == 1) {
        // IDE-friendly default: run Welch + pilot on baseline, then full experiment.
        int warmup = analyze_welch("input-S1-14.txt", 1, 30, 50, false, 4, 0.01,
                                   "results/welch_analysis.csv");
        int R      = analyze_pilot("input-S1-14.txt", 1, warmup + 92, warmup, 30, 0.05,
                                   false, "results/pilot_study.csv");
        write_experiment(warmup + 92, R, warmup, false, ".", "results/experiment_results.csv");
        print_usage(argv[0]);
        return 0;
    }

    string mode = argv[1];

    if (mode == "single") {
        string inputFile = (argc > 2) ? argv[2] : "input-S1-14.txt";
        int rule = (argc > 3) ? atoi(argv[3]) : 1;
        int W = (argc > 4) ? atoi(argv[4]) : 100;
        int R = (argc > 5) ? atoi(argv[5]) : 100;
        int warmup = (argc > 6) ? atoi(argv[6]) : 8;
        bool urgentTwoBlocks = (argc > 7) ? (atoi(argv[7]) != 0) : false;
        string outFile = (argc > 8) ? argv[8] : "results/single_run_results.csv";
        write_single_config(inputFile, rule, W, R, warmup, urgentTwoBlocks, outFile);
    } else if (mode == "warmup") {
        string inputFile = (argc > 2) ? argv[2] : "input-S1-14.txt";
        int rule = (argc > 3) ? atoi(argv[3]) : 1;
        int W = (argc > 4) ? atoi(argv[4]) : 100;
        int R = (argc > 5) ? atoi(argv[5]) : 50;
        bool urgentTwoBlocks = (argc > 6) ? (atoi(argv[6]) != 0) : false;
        string outFile = (argc > 7) ? argv[7] : "results/warmup_analysis.csv";
        write_warmup(inputFile, rule, W, R, urgentTwoBlocks, outFile);
    } else if (mode == "welch") {
        string inputFile = (argc > 2) ? argv[2] : "input-S1-14.txt";
        int rule = (argc > 3) ? atoi(argv[3]) : 1;
        int W = (argc > 4) ? atoi(argv[4]) : 30;
        int R = (argc > 5) ? atoi(argv[5]) : 50;
        bool urgentTwoBlocks = (argc > 6) ? (atoi(argv[6]) != 0) : false;
        int movAvgHW = (argc > 7) ? atoi(argv[7]) : 4;
        double tol = (argc > 8) ? atof(argv[8]) : 0.01;
        string outFile = (argc > 9) ? argv[9] : "results/welch_analysis.csv";
        analyze_welch(inputFile, rule, W, R, urgentTwoBlocks, movAvgHW, tol, outFile);
    } else if (mode == "pilot") {
        string inputFile = (argc > 2) ? argv[2] : "input-S1-14.txt";
        int rule = (argc > 3) ? atoi(argv[3]) : 1;
        int W = (argc > 4) ? atoi(argv[4]) : 100;
        int warmup = (argc > 5) ? atoi(argv[5]) : 8;
        int nPilot = (argc > 6) ? atoi(argv[6]) : 30;
        double epsilon = (argc > 7) ? atof(argv[7]) : 0.05;
        bool urgentTwoBlocks = (argc > 8) ? (atoi(argv[8]) != 0) : false;
        string outFile = (argc > 9) ? argv[9] : "results/pilot_study.csv";
        analyze_pilot(inputFile, rule, W, warmup, nPilot, epsilon, urgentTwoBlocks, outFile);
    } else if (mode == "experiment") {
        int W = (argc > 2) ? atoi(argv[2]) : 100;
        int R = (argc > 3) ? atoi(argv[3]) : 100;
        int warmup = (argc > 4) ? atoi(argv[4]) : 8;
        bool urgentTwoBlocks = (argc > 5) ? (atoi(argv[5]) != 0) : false;
        string inputDir = (argc > 6) ? argv[6] : ".";
        string outFile = (argc > 7) ? argv[7] : "results/experiment_results.csv";
        write_experiment(W, R, warmup, urgentTwoBlocks, inputDir, outFile);
    } else {
        cerr << "Unknown mode: " << mode << endl;
        print_usage(argv[0]);
        return 1;
    }

    return 0;
}
