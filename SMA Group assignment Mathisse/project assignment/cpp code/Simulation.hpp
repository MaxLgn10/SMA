//  Simulation.hpp
//  Radiology department appointment scheduling simulation.
//  Original: Tine Meersman (2022). Extended: SMA Group Assignment 2025-2026.

#ifndef Simulation_hpp
#define Simulation_hpp

#include <stdio.h>
#include <string>
#include <fstream>
#include <random>
#include <list>
#include <iterator>
#include "Helper.hpp"

using namespace std;

class simulation {
public:
    // ── Slot ────────────────────────────────────────────────────────────────
    struct Slot {
        double startTime;   // start time of the slot (hours)
        double appTime;     // appointment time (depends on rule)
        int    slotType;    // 0=none, 1=elective, 2=urgent normal, 3=urgent OT
        int    patientType; // 0=none, 1=elective, 2=urgent
    };

    // ── Patient ─────────────────────────────────────────────────────────────
    struct Patient {
        int    nr;
        int    patientType; // 1=elective, 2=urgent
        int    scanType;    // 0=brain,1=lumbar,2=cervical,3=abdomen,4=other
        int    callWeek;
        int    callDay;
        double callTime;
        int    scanWeek;
        int    scanDay;
        int    slotNr;
        double appTime;
        double tardiness;   // hours
        bool   isNoShow;
        double scanTime;
        double duration;    // hours

        Patient(int nr_, int pt_, int st_, int cw_, int cd_, double ct_,
                double tard_, bool ns_, double dur_)
            : nr(nr_), patientType(pt_), scanType(st_),
              callWeek(cw_), callDay(cd_), callTime(ct_),
              tardiness(tard_), isNoShow(ns_), duration(dur_),
              scanWeek(-1), scanDay(-1), slotNr(-1), appTime(-1), scanTime(-1.0) {}

        double getAppWT() {
            if (slotNr == -1) { printf("CANNOT CALC APP WT patient %d\n", nr); exit(1); }
            return (double)(((scanWeek - callWeek) * 7 + scanDay - callDay) * 24
                            + appTime - callTime);
        }
        double getScanWT() {
            if (scanTime < 0) { printf("CANNOT CALC SCAN WT patient %d\n", nr); exit(1); }
            double wt = (patientType == 1) ? scanTime - (appTime + tardiness)
                                           : scanTime - callTime;
            return max(0.0, wt);
        }
    };

    // ── Fixed parameters ────────────────────────────────────────────────────
    int    D                    = 6;
    int    amountOTSlotsPerDay  = 10;
    int    S                    = 32 + 10;   // updated when amountOTSlotsPerDay changes
    double slotLength           = 15.0 / 60.0;
    double lambdaElective       = 28.345;
    double meanTardiness        = 0.0;
    double stdevTardiness       = 2.5;
    double probNoShow           = 0.02;
    double meanElectiveDuration = 15.0;
    double stdevElectiveDuration= 3.0;
    double lambdaUrgent[2]      = {2.5, 1.25};
    double probUrgentType[5]    = {0.7, 0.1, 0.1, 0.05, 0.05};
    double cumulativeProbUrgentType[5] = {0.7, 0.8, 0.9, 0.95, 1.0};
    double meanUrgentDuration[5]  = {15, 17.5, 22.5, 30, 30};
    double stdevUrgentDuration[5] = {2.5, 1, 2.5, 1, 4.5};
    double weightEl = 1.0 / 168.0;
    double weightUr = 1.0 / 9.0;

    // ── Configurable parameters (set before calling setWeekSchedule) ────────
    string inputFileName;
    int    W            = 100;
    int    R            = 100;
    int    rule         = 1;
    int    warmupWeeks  = 0;

    // ── State ────────────────────────────────────────────────────────────────
    int d, s, w, r;
    Slot** weekSchedule = nullptr;

    list<Patient>           patients;
    list<Patient>::iterator patient;

    double* movingAvgElectiveAppWT  = nullptr;
    double* movingAvgElectiveScanWT = nullptr;
    double* movingAvgUrgentScanWT   = nullptr;
    double* movingAvgOT             = nullptr;

    double avgElectiveAppWT  = 0;
    double avgElectiveScanWT = 0;
    double avgUrgentScanWT   = 0;
    double avgOT             = 0;
    int    numberOfElectivePatientsPlanned = 0;
    int    numberOfUrgentPatientsPlanned   = 0;

    // ── Methods ──────────────────────────────────────────────────────────────
    void setWeekSchedule();
    void resetSystem();
    int  getRandomScanType();
    void generatePatients();
    int  getNextSlotNrFromTime(int day, int patientType, double time);
    void schedulePatients();
    void sortPatientsOnAppTime();
    void runOneSimulation();
    void runSimulations();        // legacy: prints per-replication to stdout
    void runWarmupAnalysis();     // outputs weekly CSV to stdout

    simulation();
    ~simulation();
};

#endif /* Simulation_hpp */
