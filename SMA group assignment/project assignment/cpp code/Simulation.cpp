//  Simulation.cpp
//  Radiology department appointment scheduling simulation.
//  Original: Tine Meersman (2022). Extended: SMA Group Assignment 2025-2026.

#include "Simulation.hpp"
#include <cmath>
#include <vector>

simulation::simulation() {
    // Allocate the week schedule grid (D days x S slots)
    weekSchedule = new Slot*[D];
    for (d = 0; d < D; d++) {
        weekSchedule[d] = new Slot[S];
    }
    // Moving average arrays are allocated in setWeekSchedule() once W is known.
}

simulation::~simulation() {
    for (d = 0; d < D; d++) delete[] weekSchedule[d];
    delete[] weekSchedule;
    delete[] movingAvgElectiveAppWT;
    delete[] movingAvgElectiveScanWT;
    delete[] movingAvgUrgentScanWT;
    delete[] movingAvgOT;
}

// ── setWeekSchedule ──────────────────────────────────────────────────────────
void simulation::setWeekSchedule() {
    // (Re-)allocate moving average arrays based on current W
    delete[] movingAvgElectiveAppWT;
    delete[] movingAvgElectiveScanWT;
    delete[] movingAvgUrgentScanWT;
    delete[] movingAvgOT;
    movingAvgElectiveAppWT  = new double[W]();
    movingAvgElectiveScanWT = new double[W]();
    movingAvgUrgentScanWT   = new double[W]();
    movingAvgOT             = new double[W]();

    // Read slot types from input file
    ifstream inputFile;
    inputFile.open(inputFileName);
    if (!inputFile.is_open()) {
        printf("ERROR: cannot open input file: %s\n", inputFileName.c_str());
        exit(1);
    }
    int elementInt;
    for (s = 0; s < 32; s++) {
        for (d = 0; d < D; d++) {
            inputFile >> elementInt;
            weekSchedule[d][s].slotType    = elementInt;
            weekSchedule[d][s].patientType = elementInt;
        }
    }
    inputFile.close();

    // Overtime slots (slotType=3, patientType=2)
    for (d = 0; d < D; d++) {
        for (s = 32; s < S; s++) {
            weekSchedule[d][s].slotType    = 3;
            weekSchedule[d][s].patientType = 2;
        }
    }

    // Set start times and appointment times according to rule
    for (d = 0; d < D; d++) {
        double time         = 8.0;
        double sessionStart = 8.0;    // start of current session (8 or 13)
        int    electiveInSession  = 0; // Rule 2: elective count in session
        int    electiveBlockCount = 0; // Rule 3: elective count for block grouping
        double blockStartTime     = 8.0; // Rule 3: start time of current 2-slot block

        for (s = 0; s < S; s++) {
            // Detect session change (morning -> afternoon)
            if (time == 13.0 && sessionStart == 8.0) {
                sessionStart      = 13.0;
                electiveInSession = 0;
                electiveBlockCount = 0;
            }

            weekSchedule[d][s].startTime = time;

            if (weekSchedule[d][s].slotType != 1) {
                // Non-elective slots: appointment time = slot start time
                weekSchedule[d][s].appTime = time;
            } else {
                // Elective slots: apply scheduling rule
                if (rule == 1) {
                    // Plain FCFS
                    weekSchedule[d][s].appTime = time;

                } else if (rule == 2) {
                    // Bailey-Welch: first 2 elective per session -> session start
                    // rest -> slot start - 1 slot length, capped at session start
                    if (electiveInSession < 2) {
                        weekSchedule[d][s].appTime = sessionStart;
                    } else {
                        weekSchedule[d][s].appTime = max(sessionStart, time - slotLength);
                    }
                    electiveInSession++;

                } else if (rule == 3) {
                    // Blocking (B=2): both slots in a 2-slot block -> block start time
                    if (electiveBlockCount % 2 == 0) {
                        blockStartTime = time;
                    }
                    weekSchedule[d][s].appTime = blockStartTime;
                    electiveBlockCount++;

                } else if (rule == 4) {
                    // Benchmarking: appTime = slot start - k_a * sigma_e
                    // k_a = 0.5, sigma_e = stdevElectiveDuration (min) / 60
                    double offset = 0.5 * stdevElectiveDuration / 60.0;
                    weekSchedule[d][s].appTime = max(sessionStart, time - offset);
                }
            }

            time += slotLength;
            if (time == 12.0) time = 13.0; // skip lunch break
        }
    }
}

// ── resetSystem ──────────────────────────────────────────────────────────────
void simulation::resetSystem() {
    patients.clear();
    avgElectiveAppWT  = 0;
    avgElectiveScanWT = 0;
    avgUrgentScanWT   = 0;
    avgOT             = 0;
    numberOfElectivePatientsPlanned = 0;
    numberOfUrgentPatientsPlanned   = 0;
    for (w = 0; w < W; w++) {
        movingAvgElectiveAppWT[w]  = 0;
        movingAvgElectiveScanWT[w] = 0;
        movingAvgUrgentScanWT[w]   = 0;
        movingAvgOT[w]             = 0;
    }
}

// ── getRandomScanType ────────────────────────────────────────────────────────
int simulation::getRandomScanType() {
    float rnd = (float)(rand() % 1000) / 1000.0f;
    for (int i = 0; i < 5; i++) {
        if (rnd < cumulativeProbUrgentType[i]) return i;
    }
    return 4;
}

// ── generatePatients ─────────────────────────────────────────────────────────
void simulation::generatePatients() {
    double arrivalTimeNext;
    int counter = 0;
    for (w = 0; w < W; w++) {
        for (d = 0; d < D; d++) {
            // Elective patients (Mon-Fri front desk, d < D-1 means not Saturday)
            if (d < D - 1) {
                arrivalTimeNext = 8.0 + Exponential_distribution(lambdaElective) * (17.0 - 8.0);
                while (arrivalTimeNext < 17.0) {
                    double tardiness = Normal_distribution(meanTardiness, stdevTardiness) / 60.0;
                    bool   noShow    = (float)(rand() % 1000) / 1000.0f < (float)probNoShow;
                    double duration  = Normal_distribution(meanElectiveDuration, stdevElectiveDuration) / 60.0;
                    patients.push_back(Patient(counter++, 1, 0, w, d, arrivalTimeNext,
                                               tardiness, noShow, duration));
                    arrivalTimeNext += Exponential_distribution(lambdaElective) * (17.0 - 8.0);
                }
            }
            // Urgent patients
            double lambda  = (d == 3 || d == 5) ? lambdaUrgent[1] : lambdaUrgent[0];
            double endTime = (d == 3 || d == 5) ? 12.0 : 17.0;
            arrivalTimeNext = 8.0 + Exponential_distribution(lambda) * (endTime - 8.0);
            while (arrivalTimeNext < endTime) {
                int    scanType = getRandomScanType();
                double duration = Normal_distribution(meanUrgentDuration[scanType],
                                                      stdevUrgentDuration[scanType]) / 60.0;
                patients.push_back(Patient(counter++, 2, scanType, w, d, arrivalTimeNext,
                                           0.0, false, duration));
                arrivalTimeNext += Exponential_distribution(lambda) * (endTime - 8.0);
            }
        }
    }
}

// ── getNextSlotNrFromTime ────────────────────────────────────────────────────
int simulation::getNextSlotNrFromTime(int day, int patientType, double time) {
    for (s = 0; s < S; s++) {
        if (weekSchedule[day][s].appTime > time &&
            patientType == weekSchedule[day][s].patientType) {
            return s;
        }
    }
    printf("NO SLOT EXISTS DURING TIME %.2f\n", time);
    exit(0);
}

// ── schedulePatients ─────────────────────────────────────────────────────────
void simulation::schedulePatients() {
    patients.sort([](const Patient& p1, const Patient& p2) {
        if (p1.callWeek  != p2.callWeek)  return p1.callWeek  < p2.callWeek;
        if (p1.callDay   != p2.callDay)   return p1.callDay   < p2.callDay;
        if (p1.callTime  != p2.callTime)  return p1.callTime  < p2.callTime;
        if (p1.patientType == 2)          return true;
        if (p2.patientType == 2)          return false;
        return true;
    });

    int week[2] = {0, 0};
    int day[2]  = {0, 0};
    int slot[2] = {0, 0};

    bool found = false;
    // First elective slot
    for (s = 0; s < S && !found; s++) {
        if (weekSchedule[0][s].patientType == 1) { slot[0] = s; found = true; }
    }
    // First urgent slot
    found = false;
    for (s = 0; s < S && !found; s++) {
        if (weekSchedule[0][s].patientType == 2) { slot[1] = s; found = true; }
    }

    int    previousWeek = 0, numberOfElective = 0, numberOfElectivePerWeek = 0;
    double wt;
    int    slotNr;

    for (patient = patients.begin(); patient != patients.end(); patient++) {
        int i = patient->patientType - 1;
        if (week[i] < W) {
            if (patient->callWeek > week[i]) {
                week[i] = patient->callWeek;
                day[i]  = 0;
                slot[i] = getNextSlotNrFromTime(day[i], patient->patientType, 0);
            }
            if (patient->callWeek == week[i] && patient->callDay > day[i]) {
                day[i]  = patient->callDay;
                slot[i] = getNextSlotNrFromTime(day[i], patient->patientType, 0);
            }
            if (patient->callWeek == week[i] && patient->callDay == day[i] &&
                patient->callTime >= weekSchedule[day[i]][slot[i]].appTime) {
                found = false; slotNr = -1;
                for (s = S - 1; s >= 0 && !found; s--) {
                    if (weekSchedule[day[i]][s].patientType == patient->patientType) {
                        found = true; slotNr = s;
                    }
                }
                if (patient->patientType == 2 ||
                    patient->callTime < weekSchedule[day[i]][slotNr].appTime) {
                    slot[i] = getNextSlotNrFromTime(day[i], patient->patientType,
                                                    patient->callTime);
                } else {
                    if (day[i] < D - 1) {
                        day[i]++;
                    } else {
                        day[i] = 0;
                        week[i]++;
                    }
                    if (week[i] < W)
                        slot[i] = getNextSlotNrFromTime(day[i], patient->patientType, 0);
                }
            }

            patient->scanWeek = week[i];
            patient->scanDay  = day[i];
            patient->slotNr   = slot[i];
            patient->appTime  = weekSchedule[day[i]][slot[i]].appTime;

            if (patient->patientType == 1) {
                if (previousWeek < week[i]) {
                    if (numberOfElectivePerWeek > 0)
                        movingAvgElectiveAppWT[previousWeek] /= numberOfElectivePerWeek;
                    else
                        movingAvgElectiveAppWT[previousWeek] = 0.0;
                    numberOfElectivePerWeek = 0;
                    previousWeek = week[i];
                }
                wt = patient->getAppWT();
                movingAvgElectiveAppWT[week[i]] += wt;
                numberOfElectivePerWeek++;
                avgElectiveAppWT += wt;
                numberOfElective++;
            }

            found = false;
            int startD = day[i], startS = slot[i] + 1;
            for (w = week[i]; w < W && !found; w++) {
                for (d = startD; d < D && !found; d++) {
                    for (s = startS; s < S && !found; s++) {
                        if (weekSchedule[d][s].patientType == patient->patientType) {
                            week[i] = w; day[i] = d; slot[i] = s; found = true;
                        }
                    }
                    startS = 0;
                }
                startD = 0;
            }
            if (!found) week[i] = W;
        }
    }
    if (numberOfElectivePerWeek > 0)
        movingAvgElectiveAppWT[W - 1] /= numberOfElectivePerWeek;
    else
        movingAvgElectiveAppWT[W - 1] = 0.0;
    if (numberOfElective > 0)
        avgElectiveAppWT /= numberOfElective;
}

// ── sortPatientsOnAppTime ─────────────────────────────────────────────────────
void simulation::sortPatientsOnAppTime() {
    patients.sort([](const Patient& p1, const Patient& p2) {
        if (p1.scanWeek == -1 && p2.scanWeek == -1) {
            if (p1.callWeek != p2.callWeek) return p1.callWeek < p2.callWeek;
            if (p1.callDay  != p2.callDay)  return p1.callDay  < p2.callDay;
            if (p1.callTime != p2.callTime) return p1.callTime < p2.callTime;
            if (p1.patientType == 2) return true;
            if (p2.patientType == 2) return false;
            return true;
        }
        if (p1.scanWeek == -1) return false;
        if (p2.scanWeek == -1) return true;
        if (p1.scanWeek != p2.scanWeek) return p1.scanWeek < p2.scanWeek;
        if (p1.scanDay  != p2.scanDay)  return p1.scanDay  < p2.scanDay;
        if (p1.appTime  != p2.appTime)  return p1.appTime  < p2.appTime;
        if (p1.patientType == 2) return true;
        if (p2.patientType == 2) return false;
        return p1.nr < p2.nr;
    });
}

// ── runOneSimulation ─────────────────────────────────────────────────────────
void simulation::runOneSimulation() {
    generatePatients();
    schedulePatients();
    sortPatientsOnAppTime();

    int    prevWeek = 0, prevDay = -1;
    int    numberOfPatientsWeek[2] = {0, 0};
    int    numberOfPatients[2]     = {0, 0};
    double prevScanEndTime = 0.0;
    bool   prevIsNoShow    = false;
    double arrivalTime, wt;

    for (patient = patients.begin(); patient != patients.end(); patient++) {
        if (patient->scanWeek == -1) break;

        arrivalTime = patient->appTime + patient->tardiness;

        if (!patient->isNoShow) {
            if (patient->scanWeek != prevWeek || patient->scanDay != prevDay) {
                patient->scanTime = arrivalTime;
            } else {
                if (prevIsNoShow) {
                    patient->scanTime = max(weekSchedule[patient->scanDay][patient->slotNr].startTime,
                                            max(prevScanEndTime, arrivalTime));
                } else {
                    patient->scanTime = max(prevScanEndTime, arrivalTime);
                }
            }
            wt = patient->getScanWT();
            if (patient->patientType == 1) {
                movingAvgElectiveScanWT[patient->scanWeek] += wt;
                avgElectiveScanWT += wt;
            } else {
                movingAvgUrgentScanWT[patient->scanWeek] += wt;
                avgUrgentScanWT += wt;
            }
            numberOfPatientsWeek[patient->patientType - 1]++;
            numberOfPatients[patient->patientType - 1]++;
        }

        // Overtime
        if (prevDay > -1 && prevDay != patient->scanDay) {
            double endOfDay = (prevDay == 3 || prevDay == 5) ? 13.0 : 17.0;
            movingAvgOT[prevWeek] += max(0.0, prevScanEndTime - endOfDay);
            avgOT                 += max(0.0, prevScanEndTime - endOfDay);
        }

        if (prevWeek != patient->scanWeek) {
            // Bug 5 fix: guard against division by zero when a week has no
            // scanned patients of a given type.
            if (numberOfPatientsWeek[0] > 0)
                movingAvgElectiveScanWT[prevWeek] /= numberOfPatientsWeek[0];
            else
                movingAvgElectiveScanWT[prevWeek] = 0.0;
            if (numberOfPatientsWeek[1] > 0)
                movingAvgUrgentScanWT[prevWeek]   /= numberOfPatientsWeek[1];
            else
                movingAvgUrgentScanWT[prevWeek]   = 0.0;
            movingAvgOT[prevWeek]             /= D;
            numberOfPatientsWeek[0] = numberOfPatientsWeek[1] = 0;
        }

        if (patient->isNoShow) {
            prevIsNoShow = true;
            if (patient->scanWeek != prevWeek || patient->scanDay != prevDay)
                prevScanEndTime = weekSchedule[patient->scanDay][patient->slotNr].startTime;
        } else {
            prevScanEndTime = patient->scanTime + patient->duration;
            prevIsNoShow    = false;
        }
        prevWeek = patient->scanWeek;
        prevDay  = patient->scanDay;
    }

    // Bug 3 fix: add the overtime of the LAST day in the simulation.
    // The loop only accumulates a day's overtime when the day changes, so the
    // final day (prevDay) was previously ignored.
    if (prevDay > -1) {
        double endOfDay = (prevDay == 3 || prevDay == 5) ? 13.0 : 17.0;
        movingAvgOT[prevWeek] += max(0.0, prevScanEndTime - endOfDay);
        avgOT                 += max(0.0, prevScanEndTime - endOfDay);
    }

    // Bug 5 fix: guard against division by zero for the last week.
    if (numberOfPatientsWeek[0] > 0)
        movingAvgElectiveScanWT[W - 1] /= numberOfPatientsWeek[0];
    else
        movingAvgElectiveScanWT[W - 1] = 0.0;
    if (numberOfPatientsWeek[1] > 0)
        movingAvgUrgentScanWT[W - 1]   /= numberOfPatientsWeek[1];
    else
        movingAvgUrgentScanWT[W - 1]   = 0.0;
    movingAvgOT[W - 1]             /= D;

    if (numberOfPatients[0] > 0) avgElectiveScanWT /= numberOfPatients[0];
    if (numberOfPatients[1] > 0) avgUrgentScanWT   /= numberOfPatients[1];
    avgOT             /= (D * W);
}

// ── runSimulations (legacy) ──────────────────────────────────────────────────
void simulation::runSimulations() {
    double elAppWT = 0, elScanWT = 0, urScanWT = 0, OT = 0, OV = 0;
    setWeekSchedule();
    printf("r\telAppWT\telScanWT\turScanWT\tOT\tOV\n");
    for (r = 0; r < R; r++) {
        resetSystem();
        srand(r);
        runOneSimulation();
        elAppWT += avgElectiveAppWT;
        elScanWT += avgElectiveScanWT;
        urScanWT += avgUrgentScanWT;
        OT += avgOT;
        OV += avgElectiveAppWT * weightEl + avgUrgentScanWT * weightUr;
        printf("%d\t%.4f\t%.5f\t%.4f\t%.4f\t%.4f\n",
               r, avgElectiveAppWT, avgElectiveScanWT, avgUrgentScanWT, avgOT,
               avgElectiveAppWT * weightEl + avgUrgentScanWT * weightUr);
    }
    printf("AVG\t%.4f\t%.5f\t%.4f\t%.4f\t%.4f\n",
           elAppWT/R, elScanWT/R, urScanWT/R, OT/R, OV/R);
}

// ── runWarmupAnalysis ────────────────────────────────────────────────────────
// Runs R replications, averages the per-week moving averages across replications,
// and prints CSV lines to stdout: week,el_app_wt,el_scan_wt,ur_scan_wt,ot,objective
void simulation::runWarmupAnalysis() {
    setWeekSchedule();

    // Accumulate weekly sums across replications
    vector<double> sumElApp(W, 0), sumElScan(W, 0), sumUrScan(W, 0), sumOT(W, 0);

    for (r = 0; r < R; r++) {
        resetSystem();
        srand(r);
        runOneSimulation();
        for (w = 0; w < W; w++) {
            sumElApp[w]  += movingAvgElectiveAppWT[w];
            sumElScan[w] += movingAvgElectiveScanWT[w];
            sumUrScan[w] += movingAvgUrgentScanWT[w];
            sumOT[w]     += movingAvgOT[w];
        }
    }

    // Output CSV
    printf("week,avg_el_app_wt_hrs,avg_el_scan_wt_hrs,avg_ur_scan_wt_hrs,avg_ot_hrs,avg_objective\n");
    for (w = 0; w < W; w++) {
        double elApp  = sumElApp[w]  / R;
        double elScan = sumElScan[w] / R;
        double urScan = sumUrScan[w] / R;
        double ot     = sumOT[w]     / R;
        double obj    = weightEl * elApp + weightUr * urScan;
        printf("%d,%.6f,%.6f,%.6f,%.6f,%.6f\n",
               w + 1, elApp, elScan, urScan, ot, obj);
    }
}
