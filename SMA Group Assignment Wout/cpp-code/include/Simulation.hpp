#ifndef Simulation_hpp
#define Simulation_hpp

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <list>
#include <string>
#include <vector>

#include "Helper.hpp"

using namespace std;

class simulation {
public:
    struct Slot {
        double startTime;   // start time of the slot, in hours
        double appTime;     // appointment time of the slot, in hours
        int slotType;       // 0=closed/none, 1=elective, 2=urgent normal, 3=urgent overtime
        int patientType;    // 0=none, 1=elective, 2=urgent

        Slot() : startTime(0.0), appTime(0.0), slotType(0), patientType(0) {}
    };

    struct Patient {
        int nr;
        int patientType;    // 1=elective, 2=urgent
        int scanType;       // urgent: 0=brain, 1=lumbar, 2=cervical, 3=abdomen, 4=other
        int callWeek;
        int callDay;
        double callTime;
        int scanWeek;
        int scanDay;
        int slotNr;
        double appTime;
        double tardiness;
        bool isNoShow;
        double scanTime;
        double duration;

        Patient(int nr_, int patientType_, int scanType_, int callWeek_, int callDay_,
                double callTime_, double tardiness_, bool isNoShow_, double duration_)
            : nr(nr_), patientType(patientType_), scanType(scanType_), callWeek(callWeek_),
              callDay(callDay_), callTime(callTime_), scanWeek(-1), scanDay(-1), slotNr(-1),
              appTime(-1.0), tardiness(tardiness_), isNoShow(isNoShow_), scanTime(-1.0),
              duration(duration_) {}

        double getAppWT() const {
            if (slotNr == -1) {
                printf("CANNOT CALCULATE APPOINTMENT WT OF PATIENT %d\n", nr);
                exit(1);
            }
            return ((scanWeek - callWeek) * 7 + scanDay - callDay) * 24.0 + appTime - callTime;
        }

        double getScanWT() const {
            if (scanTime < 0.0) {
                printf("CANNOT CALCULATE SCAN WT OF PATIENT %d\n", nr);
                exit(1);
            }
            double wt = 0.0;
            if (patientType == 1) {
                wt = scanTime - (appTime + tardiness);
            } else {
                wt = scanTime - callTime;
            }
            return max(0.0, wt);
        }
    };

    // Fixed assignment parameters.
    string inputFileName = "../input-S1-14.txt";
    int D = 6;
    int amountOTSlotsPerDay = 10;
    int S = 32 + 10;
    double slotLength = 15.0 / 60.0;
    double lambdaElective = 28.345;
    double meanTardiness = 0.0;
    double stdevTardiness = 2.5;
    double probNoShow = 0.02;
    double meanElectiveDuration = 15.0;
    double stdevElectiveDuration = 3.0;
    double lambdaUrgent[2] = {2.5, 1.25};
    double probUrgentType[5] = {0.7, 0.1, 0.1, 0.05, 0.05};
    double cumulativeProbUrgentType[5] = {0.7, 0.8, 0.9, 0.95, 1.0};
    double meanUrgentDuration[5] = {15.0, 17.5, 22.5, 30.0, 30.0};
    double stdevUrgentDuration[5] = {2.5, 1.0, 2.5, 1.0, 4.5};
    double weightEl = 1.0 / 168.0;
    double weightUr = 1.0 / 9.0;

    // Configurable run settings.
    int W = 100;
    int R = 100;
    int warmupWeeks = 0;
    int rule = 1;

    // Iteration variables retained for compatibility with the teacher template.
    int d = 0;
    int s = 0;
    int w = 0;
    int r = 0;

    Slot **weekSchedule = nullptr;
    list<Patient> patients;
    list<Patient>::iterator patient;

    double *movingAvgElectiveAppWT = nullptr;
    double *movingAvgElectiveScanWT = nullptr;
    double *movingAvgUrgentScanWT = nullptr;
    double *movingAvgOT = nullptr;

    double avgElectiveAppWT = 0.0;
    double avgElectiveScanWT = 0.0;
    double avgUrgentScanWT = 0.0;
    double avgOT = 0.0;
    int numberOfElectivePatientsPlanned = 0;
    int numberOfUrgentPatientsPlanned = 0;

    void allocateMovingArrays();
    void setWeekSchedule();
    void resetSystem();
    int getRandomScanType();
    void generatePatients();
    int getNextSlotNrFromTime(int day, int patientType, double time);
    void schedulePatients();
    void sortPatientsOnAppTime();
    void runOneSimulation();
    void runSimulations();

    simulation();
    ~simulation();
};

#endif
