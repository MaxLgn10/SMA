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
    srand(seed + 1);
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
                         const string &outFile) {
    simulation sim;
    sim.inputFileName = inputFile;
    sim.rule = rule;
    sim.W = W;
    sim.R = R;
    sim.warmupWeeks = warmupWeeks;
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

void write_warmup(const string &inputFile, int rule, int W, int R, const string &outFile) {
    simulation sim;
    sim.inputFileName = inputFile;
    sim.rule = rule;
    sim.W = W;
    sim.R = R;
    sim.warmupWeeks = 0;
    sim.setWeekSchedule();

    vector<double> sumElApp(W, 0.0), sumElScan(W, 0.0), sumUrScan(W, 0.0), sumOT(W, 0.0);

    for (int r = 0; r < R; r++) {
        sim.resetSystem();
        srand(r + 1);
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

void write_experiment(int W, int R, int warmupWeeks, const string &inputDir, const string &outFile) {
    ofstream out(outFile);
    if (!out.is_open()) {
        cerr << "ERROR: cannot write " << outFile << endl;
        exit(1);
    }

    out << "strategy,n_urgent,rule,mean_objective,ci_lo_objective,ci_hi_objective,"
        << "mean_el_app_wt,ci_lo_el_app,ci_hi_el_app,"
        << "mean_ur_scan_wt,ci_lo_ur_scan,ci_hi_ur_scan,"
        << "mean_el_scan_wt,mean_ot\n";

    simulation sim;
    sim.W = W;
    sim.R = R;
    sim.warmupWeeks = warmupWeeks;

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
    cout << "Experiment CSV written to: " << outFile << endl;
}

void print_usage(const char *program) {
    cout << "Usage:\n"
         << "  " << program << " single [inputFile=../input-S1-14.txt] [rule=1] [W=100] [R=100] [warmup=0] [outFile=../results/single_run_results.csv]\n"
         << "  " << program << " warmup [inputFile=../input-S1-14.txt] [rule=1] [W=100] [R=50] [outFile=../results/warmup_analysis.csv]\n"
         << "  " << program << " experiment [W=100] [R=100] [warmup=10] [inputDir=..] [outFile=../results/experiment_results.csv]\n";
}

int main(int argc, const char *argv[]) {
    make_dir("../results");

    if (argc == 1) {
        // IDE-friendly default run.
        write_single_config("../input-S1-14.txt", 1, 100, 100, 0, "../results/single_run_results.csv");
        print_usage(argv[0]);
        return 0;
    }

    string mode = argv[1];

    if (mode == "single") {
        string inputFile = (argc > 2) ? argv[2] : "../input-S1-14.txt";
        int rule = (argc > 3) ? atoi(argv[3]) : 1;
        int W = (argc > 4) ? atoi(argv[4]) : 100;
        int R = (argc > 5) ? atoi(argv[5]) : 100;
        int warmup = (argc > 6) ? atoi(argv[6]) : 0;
        string outFile = (argc > 7) ? argv[7] : "../results/single_run_results.csv";
        write_single_config(inputFile, rule, W, R, warmup, outFile);
    } else if (mode == "warmup") {
        string inputFile = (argc > 2) ? argv[2] : "../input-S1-14.txt";
        int rule = (argc > 3) ? atoi(argv[3]) : 1;
        int W = (argc > 4) ? atoi(argv[4]) : 100;
        int R = (argc > 5) ? atoi(argv[5]) : 50;
        string outFile = (argc > 6) ? argv[6] : "../results/warmup_analysis.csv";
        write_warmup(inputFile, rule, W, R, outFile);
    } else if (mode == "experiment") {
        int W = (argc > 2) ? atoi(argv[2]) : 100;
        int R = (argc > 3) ? atoi(argv[3]) : 100;
        int warmup = (argc > 4) ? atoi(argv[4]) : 10;
        string inputDir = (argc > 5) ? argv[5] : "..";
        string outFile = (argc > 6) ? argv[6] : "../results/experiment_results.csv";
        write_experiment(W, R, warmup, inputDir, outFile);
    } else {
        cerr << "Unknown mode: " << mode << endl;
        print_usage(argv[0]);
        return 1;
    }

    return 0;
}
