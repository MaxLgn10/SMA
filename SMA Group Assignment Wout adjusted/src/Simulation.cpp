#include "Simulation.hpp"

#include <cmath>
#include <iostream>
#include <vector>

using namespace std;

simulation::simulation() {
  S = 32 + amountOTSlotsPerDay;
  weekSchedule = new Slot *[D];
  for (d = 0; d < D; d++) {
    weekSchedule[d] = new Slot[S];
  }
  allocateMovingArrays();
}

simulation::~simulation() {
  if (weekSchedule != nullptr) {
    for (d = 0; d < D; d++) {
      delete[] weekSchedule[d];
    }
    delete[] weekSchedule;
  }
  delete[] movingAvgElectiveAppWT;
  delete[] movingAvgElectiveScanWT;
  delete[] movingAvgUrgentScanWT;
  delete[] movingAvgOT;
}

// Fix 2: seed six independent mt19937 streams from a single base seed.
// Each stream_id must be unique so streams never overlap.
void simulation::seed_streams(int base_seed) {
  rng_elective_arrival.seed(derive_seed(base_seed, 0));
  rng_urgent_arrival.seed(derive_seed(base_seed, 1));
  rng_elective_scan.seed(derive_seed(base_seed, 2));
  rng_urgent_scan.seed(derive_seed(base_seed, 3));
  rng_tardiness.seed(derive_seed(base_seed, 4));
  rng_noshow.seed(derive_seed(base_seed, 5));
}

void simulation::allocateMovingArrays() {
  delete[] movingAvgElectiveAppWT;
  delete[] movingAvgElectiveScanWT;
  delete[] movingAvgUrgentScanWT;
  delete[] movingAvgOT;

  movingAvgElectiveAppWT = new double[W]();
  movingAvgElectiveScanWT = new double[W]();
  movingAvgUrgentScanWT = new double[W]();
  movingAvgOT = new double[W]();
}

void simulation::resetSystem() {
  patients.clear();
  avgElectiveAppWT = 0.0;
  avgElectiveScanWT = 0.0;
  avgUrgentScanWT = 0.0;
  avgOT = 0.0;
  numberOfElectivePatientsPlanned = 0;
  numberOfUrgentPatientsPlanned = 0;

  for (w = 0; w < W; w++) {
    movingAvgElectiveAppWT[w] = 0.0;
    movingAvgElectiveScanWT[w] = 0.0;
    movingAvgUrgentScanWT[w] = 0.0;
    movingAvgOT[w] = 0.0;
  }
}

void simulation::setWeekSchedule() {
  allocateMovingArrays();

  for (d = 0; d < D; d++) {
    for (s = 0; s < S; s++) {
      weekSchedule[d][s] = Slot();
    }
  }

  ifstream inputFile(inputFileName);
  if (!inputFile.is_open()) {
    cerr << "ERROR: cannot open input schedule file: " << inputFileName << endl;
    exit(1);
  }

  int elementInt = 0;
  for (s = 0; s < 32; s++) {
    for (d = 0; d < D; d++) {
      if (!(inputFile >> elementInt)) {
        cerr << "ERROR: input file must contain 32 rows and 6 columns of "
                "integers."
             << endl;
        exit(1);
      }
      weekSchedule[d][s].slotType = elementInt;
      weekSchedule[d][s].patientType = elementInt;
    }
  }
  inputFile.close();

  for (d = 0; d < D; d++) {
    for (s = 32; s < S; s++) {
      weekSchedule[d][s].slotType = 3;
      weekSchedule[d][s].patientType = 2;
    }
  }

  for (d = 0; d < D; d++) {
    double time = 8.0;
    double sessionStart = 8.0;
    int electiveInSession = 0;
    int electiveBlockCount = 0;
    double blockStartTime = 8.0;

    for (s = 0; s < S; s++) {
      if (s == 16) {
        sessionStart = 13.0;
        electiveInSession = 0;
        electiveBlockCount = 0;
        blockStartTime = 13.0;
      }

      weekSchedule[d][s].startTime = time;

      if (weekSchedule[d][s].slotType != 1) {
        weekSchedule[d][s].appTime = time;
      } else if (rule == 1) {
        weekSchedule[d][s].appTime = time;
      } else if (rule == 2) {
        if (electiveInSession < 2) {
          weekSchedule[d][s].appTime = sessionStart;
        } else {
          weekSchedule[d][s].appTime = max(sessionStart, time - slotLength);
        }
        electiveInSession++;
      } else if (rule == 3) {
        if (electiveBlockCount % 2 == 0) {
          blockStartTime = time;
        }
        weekSchedule[d][s].appTime = blockStartTime;
        electiveBlockCount++;
      } else if (rule == 4) {
        const double ka = 0.5;
        double offset = ka * stdevElectiveDuration / 60.0;
        weekSchedule[d][s].appTime = max(sessionStart, time - offset);
      } else {
        cerr << "ERROR: unknown scheduling rule " << rule << endl;
        exit(1);
      }

      time += slotLength;
      if (fabs(time - 12.0) < 1e-9) {
        time = 13.0;
      }
    }
  }
}

// Fix 1 + Fix 2: uses rng_urgent_scan stream, full-precision uniform.
int simulation::getRandomScanType(std::mt19937& rng) {
  double rnd = Uniform_distribution(rng);
  for (int i = 0; i < 5; i++) {
    if (rnd < cumulativeProbUrgentType[i])
      return i;
  }
  return 4;
}

void simulation::generatePatients() {
  double arrivalTimeNext = 0.0;
  int counter = 0;

  for (w = 0; w < W; w++) {
    for (d = 0; d < D; d++) {
      if (d < D - 1) {
        // Fix 1+2: elective arrivals use rng_elective_arrival stream.
        arrivalTimeNext =
            8.0 + Exponential_distribution(lambdaElective, rng_elective_arrival) * (17.0 - 8.0);
        while (arrivalTimeNext < 17.0) {
          double tardiness =
              Normal_distribution(meanTardiness, stdevTardiness, rng_tardiness) / 60.0;
          bool noShow = Bernouilli_distribution(probNoShow, rng_noshow) == 1;
          // Fix 3: truncated normal — elective durations cannot be negative.
          double duration =
              Normal_distribution_truncated(meanElectiveDuration, stdevElectiveDuration, rng_elective_scan) /
              60.0;
          patients.push_back(Patient(counter++, 1, 0, w, d, arrivalTimeNext,
                                     tardiness, noShow, duration));
          arrivalTimeNext +=
              Exponential_distribution(lambdaElective, rng_elective_arrival) * (17.0 - 8.0);
        }
      }

      double lambda = lambdaUrgent[0];
      double endTime = 17.0;
      if (d == 3 || d == 5) {
        lambda = lambdaUrgent[1];
        endTime = 12.0;
      }

      if (urgentArrivalTwoBlocks && endTime > 12.0) {
        double lambdaPart = lambda / 2.0;

        // Morning block: 08:00 - 12:00
        arrivalTimeNext = 8.0 + Exponential_distribution(lambdaPart, rng_urgent_arrival) * 4.0;
        while (arrivalTimeNext < 12.0) {
          int scanType = getRandomScanType(rng_urgent_scan);
          // Fix 3: truncated normal for urgent scan durations.
          double duration = Normal_distribution_truncated(meanUrgentDuration[scanType],
                                                stdevUrgentDuration[scanType], rng_urgent_scan) /
                            60.0;
          patients.push_back(Patient(counter++, 2, scanType, w, d,
                                     arrivalTimeNext, 0.0, false, duration));
          arrivalTimeNext += Exponential_distribution(lambdaPart, rng_urgent_arrival) * 4.0;
        }

        // Afternoon block: 13:00 - 17:00
        arrivalTimeNext = 13.0 + Exponential_distribution(lambdaPart, rng_urgent_arrival) * 4.0;
        while (arrivalTimeNext < 17.0) {
          int scanType = getRandomScanType(rng_urgent_scan);
          double duration = Normal_distribution_truncated(meanUrgentDuration[scanType],
                                                stdevUrgentDuration[scanType], rng_urgent_scan) /
                            60.0;
          patients.push_back(Patient(counter++, 2, scanType, w, d,
                                     arrivalTimeNext, 0.0, false, duration));
          arrivalTimeNext += Exponential_distribution(lambdaPart, rng_urgent_arrival) * 4.0;
        }
      } else {
        // Single block: 08:00 - endTime (default 17:00)
        arrivalTimeNext =
            8.0 + Exponential_distribution(lambda, rng_urgent_arrival) * (endTime - 8.0);
        while (arrivalTimeNext < endTime) {
          int scanType = getRandomScanType(rng_urgent_scan);
          // Fix 3: truncated normal for urgent scan durations.
          double duration = Normal_distribution_truncated(meanUrgentDuration[scanType],
                                                stdevUrgentDuration[scanType], rng_urgent_scan) /
                            60.0;
          patients.push_back(Patient(counter++, 2, scanType, w, d,
                                     arrivalTimeNext, 0.0, false, duration));
          arrivalTimeNext += Exponential_distribution(lambda, rng_urgent_arrival) * (endTime - 8.0);
        }
      }
    }
  }
}

int simulation::getNextSlotNrFromTime(int day, int patientType, double time) {
  for (s = 0; s < S; s++) {
    if (weekSchedule[day][s].appTime > time &&
        patientType == weekSchedule[day][s].patientType) {
      return s;
    }
  }
  printf("NO SLOT EXISTS DURING TIME %.2f ON DAY %d FOR PATIENT TYPE %d\n",
         time, day, patientType);
  exit(1);
}

void simulation::schedulePatients() {
  patients.sort([](const Patient &p1, const Patient &p2) {
    if (p1.callWeek != p2.callWeek)
      return p1.callWeek < p2.callWeek;
    if (p1.callDay != p2.callDay)
      return p1.callDay < p2.callDay;
    if (p1.callTime != p2.callTime)
      return p1.callTime < p2.callTime;
    if (p1.patientType == 2 && p2.patientType != 2)
      return true;
    if (p2.patientType == 2 && p1.patientType != 2)
      return false;
    return p1.nr < p2.nr;
  });

  int week[2] = {0, 0};
  int day[2] = {0, 0};
  int slot[2] = {0, 0};

  bool found = false;
  for (s = 0; s < S && !found; s++) {
    if (weekSchedule[0][s].patientType == 1) {
      slot[0] = s;
      found = true;
    }
  }
  if (!found) {
    cerr << "ERROR: schedule has no elective slot on day 0." << endl;
    exit(1);
  }

  found = false;
  for (s = 0; s < S && !found; s++) {
    if (weekSchedule[0][s].patientType == 2) {
      slot[1] = s;
      found = true;
    }
  }
  if (!found) {
    cerr << "ERROR: schedule has no urgent slot on day 0." << endl;
    exit(1);
  }

  vector<int> electiveCountPerWeek(W, 0);
  int totalElectiveScheduled = 0;

  for (patient = patients.begin(); patient != patients.end(); ++patient) {
    int i = patient->patientType - 1;
    if (week[i] >= W)
      continue;

    if (patient->callWeek > week[i]) {
      week[i] = patient->callWeek;
      day[i] = 0;
      slot[i] = getNextSlotNrFromTime(day[i], patient->patientType, 0.0);
    }

    if (patient->callWeek == week[i] && patient->callDay > day[i]) {
      day[i] = patient->callDay;
      slot[i] = getNextSlotNrFromTime(day[i], patient->patientType, 0.0);
    }

    if (patient->callWeek == week[i] && patient->callDay == day[i] &&
        patient->callTime >= weekSchedule[day[i]][slot[i]].appTime) {
      int lastSlotOfType = -1;
      for (s = S - 1; s >= 0; s--) {
        if (weekSchedule[day[i]][s].patientType == patient->patientType) {
          lastSlotOfType = s;
          break;
        }
      }

      if (lastSlotOfType == -1) {
        cerr << "ERROR: no slot of required patient type on day." << endl;
        exit(1);
      }

      if (patient->patientType == 2 ||
          patient->callTime < weekSchedule[day[i]][lastSlotOfType].appTime) {
        slot[i] = getNextSlotNrFromTime(day[i], patient->patientType,
                                        patient->callTime);
      } else {
        if (day[i] < D - 1) {
          day[i]++;
        } else {
          day[i] = 0;
          week[i]++;
        }
        if (week[i] < W) {
          slot[i] = getNextSlotNrFromTime(day[i], patient->patientType, 0.0);
        }
      }
    }

    if (week[i] < W) {
      patient->scanWeek = week[i];
      patient->scanDay = day[i];
      patient->slotNr = slot[i];
      patient->appTime = weekSchedule[day[i]][slot[i]].appTime;

      if (patient->patientType == 1) {
        double wt = patient->getAppWT();
        movingAvgElectiveAppWT[patient->scanWeek] += wt;
        electiveCountPerWeek[patient->scanWeek]++;
        avgElectiveAppWT += wt;
        totalElectiveScheduled++;
        numberOfElectivePatientsPlanned++;
      } else {
        numberOfUrgentPatientsPlanned++;
      }

      found = false;
      int startD = day[i];
      int startS = slot[i] + 1;
      for (w = week[i]; w < W && !found; w++) {
        for (d = startD; d < D && !found; d++) {
          for (s = startS; s < S && !found; s++) {
            if (weekSchedule[d][s].patientType == patient->patientType) {
              week[i] = w;
              day[i] = d;
              slot[i] = s;
              found = true;
            }
          }
          startS = 0;
        }
        startD = 0;
      }
      if (!found)
        week[i] = W;
    }
  }

  for (w = 0; w < W; w++) {
    if (electiveCountPerWeek[w] > 0) {
      movingAvgElectiveAppWT[w] /= electiveCountPerWeek[w];
    }
  }
  if (totalElectiveScheduled > 0) {
    avgElectiveAppWT /= totalElectiveScheduled;
  }
}

void simulation::sortPatientsOnAppTime() {
  patients.sort([](const Patient &p1, const Patient &p2) {
    if (p1.scanWeek == -1 && p2.scanWeek == -1) {
      if (p1.callWeek != p2.callWeek)
        return p1.callWeek < p2.callWeek;
      if (p1.callDay != p2.callDay)
        return p1.callDay < p2.callDay;
      if (p1.callTime != p2.callTime)
        return p1.callTime < p2.callTime;
      if (p1.patientType == 2 && p2.patientType != 2)
        return true;
      if (p2.patientType == 2 && p1.patientType != 2)
        return false;
      return p1.nr < p2.nr;
    }
    if (p1.scanWeek == -1)
      return false;
    if (p2.scanWeek == -1)
      return true;
    if (p1.scanWeek != p2.scanWeek)
      return p1.scanWeek < p2.scanWeek;
    if (p1.scanDay != p2.scanDay)
      return p1.scanDay < p2.scanDay;
    if (p1.appTime != p2.appTime)
      return p1.appTime < p2.appTime;
    if (p1.patientType == 2 && p2.patientType != 2)
      return true;
    if (p2.patientType == 2 && p1.patientType != 2)
      return false;
    return p1.nr < p2.nr;
  });
}

void simulation::runOneSimulation() {
  generatePatients();
  schedulePatients();
  sortPatientsOnAppTime();

  vector<int> electiveScanCountPerWeek(W, 0);
  vector<int> urgentScanCountPerWeek(W, 0);
  int totalElectiveScanned = 0;
  int totalUrgentScanned = 0;

  int prevWeek = -1;
  int prevDay = -1;
  double prevScanEndTime = 0.0;
  bool prevIsNoShow = false;
  double totalOT = 0.0;

  auto close_previous_day = [&]() {
    if (prevWeek >= 0 && prevDay >= 0 && prevWeek < W) {
      double endOfDay = (prevDay == 3 || prevDay == 5) ? 12.0 : 17.0;
      double ot = max(0.0, prevScanEndTime - endOfDay);
      movingAvgOT[prevWeek] += ot;
      totalOT += ot;
    }
  };

  for (patient = patients.begin(); patient != patients.end(); ++patient) {
    if (patient->scanWeek == -1)
      break;

    bool newDay =
        (patient->scanWeek != prevWeek || patient->scanDay != prevDay);
    if (newDay) {
      close_previous_day();
      prevIsNoShow = false;
    }

    double arrivalTime = patient->appTime + patient->tardiness;

    if (!patient->isNoShow) {
      if (newDay) {
        patient->scanTime = arrivalTime;
      } else if (prevIsNoShow) {
        patient->scanTime =
            max(weekSchedule[patient->scanDay][patient->slotNr].startTime,
                max(prevScanEndTime, arrivalTime));
      } else {
        patient->scanTime = max(prevScanEndTime, arrivalTime);
      }

      // Enforce strict lunch break on full days (not Wed/Sat)
      if (patient->scanDay != 3 && patient->scanDay != 5) {
        if (patient->scanTime > 12.0 - 1e-9 && patient->scanTime < 13.0) {
          patient->scanTime = 13.0;
        }
      }

      double wt = patient->getScanWT();
      if (patient->patientType == 1) {
        movingAvgElectiveScanWT[patient->scanWeek] += wt;
        avgElectiveScanWT += wt;
        electiveScanCountPerWeek[patient->scanWeek]++;
        totalElectiveScanned++;
      } else {
        movingAvgUrgentScanWT[patient->scanWeek] += wt;
        avgUrgentScanWT += wt;
        urgentScanCountPerWeek[patient->scanWeek]++;
        totalUrgentScanned++;
      }

      prevScanEndTime = patient->scanTime + patient->duration;
      prevIsNoShow = false;
    } else {
      if (newDay) {
        prevScanEndTime =
            weekSchedule[patient->scanDay][patient->slotNr].startTime;
      }
      prevIsNoShow = true;
    }

    prevWeek = patient->scanWeek;
    prevDay = patient->scanDay;
  }
  close_previous_day();

  for (w = 0; w < W; w++) {
    if (electiveScanCountPerWeek[w] > 0) {
      movingAvgElectiveScanWT[w] /= electiveScanCountPerWeek[w];
    }
    if (urgentScanCountPerWeek[w] > 0) {
      movingAvgUrgentScanWT[w] /= urgentScanCountPerWeek[w];
    }
    movingAvgOT[w] /= D;
  }

  if (totalElectiveScanned > 0)
    avgElectiveScanWT /= totalElectiveScanned;
  if (totalUrgentScanned > 0)
    avgUrgentScanWT /= totalUrgentScanned;
  avgOT = totalOT / (D * W);
}

void simulation::runSimulations() {
  double electiveAppWT = 0.0;
  double electiveScanWT = 0.0;
  double urgentScanWT = 0.0;
  double OT = 0.0;
  double OV = 0.0;

  int firstWeek = max(0, warmupWeeks);
  int activeWeeks = W - firstWeek;
  if (activeWeeks <= 0) {
    printf("ERROR: warmupWeeks must be smaller than W.\n");
    return;
  }

  setWeekSchedule();
  printf("r,el_app_wt,el_scan_wt,ur_scan_wt,ot,objective\n");

  for (r = 0; r < R; r++) {
    resetSystem();
    seed_streams(r);
    runOneSimulation();

    // Apply warmup: average only post-warmup weeks.
    double repElApp = 0.0, repElScan = 0.0, repUrScan = 0.0, repOT = 0.0;
    for (w = firstWeek; w < W; w++) {
      repElApp  += movingAvgElectiveAppWT[w];
      repElScan += movingAvgElectiveScanWT[w];
      repUrScan += movingAvgUrgentScanWT[w];
      repOT     += movingAvgOT[w];
    }
    repElApp  /= activeWeeks;
    repElScan /= activeWeeks;
    repUrScan /= activeWeeks;
    repOT     /= activeWeeks;

    double objective = repElApp * weightEl + repUrScan * weightUr;
    electiveAppWT += repElApp;
    electiveScanWT += repElScan;
    urgentScanWT += repUrScan;
    OT += repOT;
    OV += objective;
    printf("%d,%.8f,%.8f,%.8f,%.8f,%.8f\n", r, repElApp,
           repElScan, repUrScan, repOT, objective);
  }

  electiveAppWT /= R;
  electiveScanWT /= R;
  urgentScanWT /= R;
  OT /= R;
  OV /= R;
  printf("AVG,%.8f,%.8f,%.8f,%.8f,%.8f\n", electiveAppWT, electiveScanWT,
         urgentScanWT, OT, OV);
}
