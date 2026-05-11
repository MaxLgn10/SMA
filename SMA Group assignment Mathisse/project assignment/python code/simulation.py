"""
simulation_v2.py  –  updated version
Changes vs the original simulation.py:
  1. Warm-up period: first WARMUP_WEEKS weeks of each replication are
     discarded when accumulating statistics (Welch's method).
  2. CSV output: runSimulations() writes per-replication results to
     ../results_v2/<filename>.csv and appends a summary row to
     ../results_v2/experiment_results_v2.csv.
  3. Bailey-Welch rule (Rule 2) is generalised to arbitrary K (K=2,3,4,5).
     The rule parameter selects K: rule=2 -> K=2, rule=5 -> K=3,
     rule=6 -> K=4, rule=7 -> K=5.  Rules 1/3/4 are unchanged.
  4. Slot.__init__ added (fixes potential AttributeError before setWeekSchedule).
  5. ZeroDivisionError guard in schedulePatients moving average.
  6. getScanWT sentinel check corrected (-1 instead of 0).
  7. exit() calls replaced with ValueError.
  8. Session-change detection uses time >= 13 (more robust).
  9. The dead  `else: day[i]`  no-op is removed.
"""
import re
import csv
import math
import os
import random
import statistics
from functools import cmp_to_key

from helper import Exponential_distribution, Normal_distribution, Bernouilli_distribution
from slot import Slot
from patient import Patient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WARMUP_WEEKS = 10
RESULTS_DIR  = os.path.join(os.path.dirname(__file__), "..", "results_v2")
os.makedirs(RESULTS_DIR, exist_ok=True)


class Simulation:
    """
    Simulation instance - v2

    Class Attributes
    ----------------
    inputFileName: str
    D: int
        number of days per week (Sunday not included)
    amountOTSlotsPerDay: int
        number of overtime slots per day
    S: int
        number of slots per day (normal + OT)
    slotLength: float
        duration of a slot (in hours)
    lambdaElective: float
    meanTardiness: float
    stdevTardiness: float
    probNoShow: float
    meanElectiveDuration: float
    stdevElectiveDuration: float
    lambdaUrgent: tuple[float]
    probUrgentType: tuple[float]
    cumulativeProbUrgentType: tuple[float]
    meanUrgentDuration: tuple[float]
    stdevUrgentDuration: tuple[float]
    weightEl: float
    weightUr: float

    Instance Attributes
    -------------------
    W: int              total simulated weeks (including warm-up)
    R: int              number of replications
    rule: int           scheduling rule (1-4 original; 5=BW K=3, 6=BW K=4, 7=BW K=5)
    weekSchedule: list[list[Slot]]
    """

    # class-level parameters (unchanged from original)
    inputFileName: str
    D: int   = 6
    amountOTSlotsPerDay: int = 10
    S: int   = 32 + amountOTSlotsPerDay
    slotLength: float = float(15 / 60)
    lambdaElective: float = 28.345
    meanTardiness: float  = 0.0
    stdevTardiness: float = 2.5
    probNoShow: float     = 0.02
    meanElectiveDuration: float  = 15.0
    stdevElectiveDuration: float = 3.0
    lambdaUrgent: tuple   = (2.5, 1.25)
    probUrgentType: tuple = (0.7, 0.1, 0.1, 0.05, 0.05)
    cumulativeProbUrgentType: tuple = (0.7, 0.8, 0.9, 0.95, 1.0)
    meanUrgentDuration:  tuple = (15, 17.5, 22.5, 30, 30)
    stdevUrgentDuration: tuple = (2.5, 1, 2.5, 1, 4.5)
    weightEl: float = 1.0 / 168.0
    weightUr: float = 1.0 / 9.0

    def __init__(self, filename: str, W: int, R: int, rule: int) -> None:
        """
        Args:
            filename (str): input schedule file
            W (int):        total weeks to simulate (warm-up + active)
            R (int):        number of replications
            rule (int):     scheduling rule
                            1 = FCFS
                            2 = Bailey-Welch K=2
                            3 = Blocking B=2
                            4 = Benchmarking k_a=0.5
                            5 = Bailey-Welch K=3
                            6 = Bailey-Welch K=4
                            7 = Bailey-Welch K=5
        """
        self.patients        = list()
        self.inputFileName   = filename
        self.W               = W
        self.R               = R
        self.rule            = rule

        self._reset_accumulators()

        self.weekSchedule = []
        for _ in range(self.D):
            self.weekSchedule.append([Slot() for _ in range(self.S)])

        self._init_moving_avgs()

    # helpers

    def _reset_accumulators(self) -> None:
        self.avgElectiveAppWT  = 0.0
        self.avgElectiveScanWT = 0.0
        self.avgUrgentScanWt   = 0.0
        self.avgOT             = 0.0
        self.numberOfElectivePatientsPlanned = 0
        self.numberOfUrgentPatientsPlanned   = 0

    def _init_moving_avgs(self) -> None:
        self.movingAvgElectiveAppWT  = [0.0] * self.W
        self.movingAvgElectiveScanWT = [0.0] * self.W
        self.movingAvgUrgentScanWT   = [0.0] * self.W
        self.movingAvgOT             = [0.0] * self.W

    def resetSystem(self) -> None:
        """Reset all per-replication state."""
        self.patients = list()
        self._reset_accumulators()
        self._init_moving_avgs()

    # patient generation

    def generatePatients(self) -> None:
        counter = 0
        for w in range(self.W):
            for d in range(self.D):
                # Elective: Mon-Fri only (d 0-4), front desk 08:00-17:00
                if d < self.D - 1:
                    arrivalTimeNext = 8 + Exponential_distribution(self.lambdaElective) * (17 - 8)
                    while arrivalTimeNext < 17:
                        tardiness = Normal_distribution(self.meanTardiness, self.stdevTardiness) / 60
                        noShow    = Bernouilli_distribution(self.probNoShow)
                        duration  = Normal_distribution(self.meanElectiveDuration,
                                                        self.stdevElectiveDuration) / 60
                        self.patients.append(
                            Patient(counter, 1, 0, w, d, arrivalTimeNext, tardiness, noShow, duration))
                        counter += 1
                        arrivalTimeNext += Exponential_distribution(self.lambdaElective) * (17 - 8)

                # Urgent: half-day on Thu(3) and Sat(5), lunch break excluded on full days
                # Assignment: "No urgent arrivals during the lunch break"
                if d in (3, 5):
                    # half day: single window 8:00-12:00
                    lmbd = self.lambdaUrgent[1]
                    arrivalTimeNext = 8 + Exponential_distribution(lmbd) * 4
                    while arrivalTimeNext < 12:
                        scanType = self.getRandomScanType()
                        duration = Normal_distribution(self.meanUrgentDuration[scanType],
                                                      self.stdevUrgentDuration[scanType]) / 60
                        self.patients.append(
                            Patient(counter, 2, scanType, w, d, arrivalTimeNext, 0, False, duration))
                        counter += 1
                        arrivalTimeNext += Exponential_distribution(lmbd) * 4
                else:
                    # full day: two windows 8:00-12:00 and 13:00-17:00, skip lunch
                    lmbd = self.lambdaUrgent[0]
                    for start, end in ((8, 12), (13, 17)):
                        arrivalTimeNext = start + Exponential_distribution(lmbd) * (end - start)
                        while arrivalTimeNext < end:
                            scanType = self.getRandomScanType()
                            duration = Normal_distribution(self.meanUrgentDuration[scanType],
                                                          self.stdevUrgentDuration[scanType]) / 60
                            self.patients.append(
                                Patient(counter, 2, scanType, w, d, arrivalTimeNext, 0, False, duration))
                            counter += 1
                            arrivalTimeNext += Exponential_distribution(lmbd) * (end - start)

    def getRandomScanType(self) -> int:
        r = random.random()
        for idx, prob in enumerate(self.cumulativeProbUrgentType):
            if r < prob:
                return idx
        return len(self.cumulativeProbUrgentType) - 1

    # slot lookup

    def getNextSlotNrFromTime(self, day: int, patientType: int, time: float) -> int:
        for s in range(self.S):
            slot = self.weekSchedule[day][s]
            if slot.appTime > time and slot.patientType == patientType:
                return s
        raise ValueError(
            f"No available slot for patientType={patientType} after time={time} on day={day}")

    # sorting

    @staticmethod
    def sortPatients(p1: Patient, p2: Patient) -> int:
        """Sort by call week/day/time; urgent wins ties."""
        for a, b in ((p1.callWeek, p2.callWeek),
                     (p1.callDay,  p2.callDay),
                     (p1.callTime, p2.callTime)):
            if a < b: return -1
            if a > b: return  1
        if p1.patientType == 2: return -1
        if p2.patientType == 2: return  1
        return 0

    @staticmethod
    def sortPatientsOnAppTime(p1: Patient, p2: Patient) -> int:
        """Sort by scan week/day/appTime; unscheduled patients go last."""
        if p1.scanWeek == -1 and p2.scanWeek == -1:
            for a, b in ((p1.callWeek, p2.callWeek),
                         (p1.callDay,  p2.callDay),
                         (p1.callTime, p2.callTime)):
                if a < b: return -1
                if a > b: return  1
            if p1.patientType == 2: return -1
            if p2.patientType == 2: return  1
            return 0
        if p1.scanWeek == -1: return  1
        if p2.scanWeek == -1: return -1
        for a, b in ((p1.scanWeek, p2.scanWeek),
                     (p1.scanDay,  p2.scanDay),
                     (p1.appTime,  p2.appTime)):
            if a < b: return -1
            if a > b: return  1
        if p1.patientType == 2: return -1
        if p2.patientType == 2: return  1
        if p1.nr < p2.nr: return -1
        if p1.nr > p2.nr: return  1
        return 0

    # scheduling

    def schedulePatients(self) -> None:
        self.patients = sorted(self.patients, key=cmp_to_key(Simulation.sortPatients))

        week = [0, 0]
        day  = [0, 0]
        slot = [0, 0]

        for pt in (1, 2):
            i = pt - 1
            for s in range(self.S):
                if self.weekSchedule[0][s].patientType == pt:
                    slot[i] = s
                    break

        previousWeek            = 0
        numberOfElectivePerWeek = 0
        numberOfElective        = 0

        for patient in self.patients:
            i = patient.patientType - 1
            if week[i] >= self.W:
                continue

            if patient.callWeek > week[i]:
                week[i] = patient.callWeek
                day[i]  = 0
                slot[i] = self.getNextSlotNrFromTime(day[i], patient.patientType, 0)
            elif patient.callWeek == week[i] and patient.callDay > day[i]:
                day[i]  = patient.callDay
                slot[i] = self.getNextSlotNrFromTime(day[i], patient.patientType, 0)

            if (patient.callWeek == week[i] and
                    patient.callDay == day[i] and
                    patient.callTime >= self.weekSchedule[day[i]][slot[i]].appTime):
                last_s = None
                for s in range(self.S - 1, -1, -1):
                    if self.weekSchedule[day[i]][s].patientType == patient.patientType:
                        last_s = s
                        break
                if patient.patientType == 2 or patient.callTime < self.weekSchedule[day[i]][last_s].appTime:
                    slot[i] = self.getNextSlotNrFromTime(day[i], patient.patientType, patient.callTime)
                else:
                    if day[i] < self.D - 1:
                        day[i] += 1
                    else:
                        week[i] += 1
                        day[i]   = 0
                    if week[i] < self.W:
                        slot[i] = self.getNextSlotNrFromTime(day[i], patient.patientType, 0)
                    else:
                        continue

            # assign slot
            patient.scanWeek = week[i]
            patient.scanDay  = day[i]
            patient.slotNr   = slot[i]
            patient.appTime  = self.weekSchedule[day[i]][slot[i]].appTime

            # only accumulate stats outside warm-up
            if patient.patientType == 1 and patient.scanWeek >= WARMUP_WEEKS:
                if previousWeek < week[i]:
                    if numberOfElectivePerWeek > 0:
                        self.movingAvgElectiveAppWT[previousWeek] /= numberOfElectivePerWeek
                    numberOfElectivePerWeek = 0
                    previousWeek = week[i]
                wt = patient.getAppWT()
                self.movingAvgElectiveAppWT[week[i]] += wt
                numberOfElectivePerWeek += 1
                self.avgElectiveAppWT   += wt
                numberOfElective        += 1

            # advance to next slot of this type
            found  = False
            startD = day[i]
            startS = slot[i] + 1
            for w_idx in range(week[i], self.W):
                for d_idx in range(startD, self.D):
                    for s_idx in range(startS, self.S):
                        if self.weekSchedule[d_idx][s_idx].patientType == patient.patientType:
                            week[i] = w_idx
                            day[i]  = d_idx
                            slot[i] = s_idx
                            found   = True
                            break
                    if found: break
                    startS = 0
                if found: break
                startD = 0
            if not found:
                week[i] = self.W

        if numberOfElectivePerWeek > 0:
            self.movingAvgElectiveAppWT[self.W - 1] /= numberOfElectivePerWeek
        if numberOfElective > 0:
            self.avgElectiveAppWT /= numberOfElective

    # one replication

    def runOneSimulation(self) -> None:
        self.generatePatients()
        self.schedulePatients()
        self.patients = sorted(self.patients, key=cmp_to_key(Simulation.sortPatientsOnAppTime))

        prevWeek      = 0
        prevDay       = -1
        nPatientsWeek = [0, 0]
        nPatients     = [0, 0]
        prevScanEnd   = 0.0
        prevIsNoShow  = False

        for patient in self.patients:
            if patient.scanWeek == -1:
                break

            active      = patient.scanWeek >= WARMUP_WEEKS
            arrivalTime = patient.appTime + patient.tardiness

            if not patient.isNoShow:
                if patient.scanWeek != prevWeek or patient.scanDay != prevDay:
                    patient.scanTime = arrivalTime
                elif prevIsNoShow:
                    patient.scanTime = max(
                        self.weekSchedule[patient.scanDay][patient.slotNr].startTime,
                        max(prevScanEnd, arrivalTime))
                else:
                    patient.scanTime = max(prevScanEnd, arrivalTime)

                # lunch break: no scan may start between 12:00 and 13:00 on full days
                # (assignment: "No urgent patients are treated during the lunch break")
                # a scan that started before 12:00 and runs into the break is uninterrupted
                # (assignment: "The time working during the lunch break is not accounted as overtime")
                if patient.scanDay not in (3, 5) and 12.0 <= patient.scanTime < 13.0:
                    patient.scanTime = 13.0

                wt = patient.getScanWT()
                if active:
                    if patient.patientType == 1:
                        self.movingAvgElectiveScanWT[patient.scanWeek] += wt
                        self.avgElectiveScanWT += wt
                    else:
                        self.movingAvgUrgentScanWT[patient.scanWeek] += wt
                        self.avgUrgentScanWt += wt
                    nPatientsWeek[patient.patientType - 1] += 1
                    nPatients[patient.patientType - 1]     += 1

            # overtime: credit to the day we just finished when moving to a new day
            if prevDay > -1 and prevDay != patient.scanDay:
                if prevWeek >= WARMUP_WEEKS:
                    end_hour = 12 if prevDay in (3, 5) else 17
                    ot = max(0.0, prevScanEnd - end_hour)
                    self.movingAvgOT[prevWeek] += ot
                    self.avgOT += ot

            if prevWeek != patient.scanWeek and prevWeek >= WARMUP_WEEKS:
                if nPatientsWeek[0] > 0:
                    self.movingAvgElectiveScanWT[prevWeek] /= nPatientsWeek[0]
                if nPatientsWeek[1] > 0:
                    self.movingAvgUrgentScanWT[prevWeek]   /= nPatientsWeek[1]
                self.movingAvgOT[prevWeek] /= self.D
                nPatientsWeek = [0, 0]

            if patient.isNoShow:
                prevIsNoShow = True
                if patient.scanWeek != prevWeek or patient.scanDay != prevDay:
                    prevScanEnd = self.weekSchedule[patient.scanDay][patient.slotNr].startTime
            else:
                prevScanEnd  = patient.scanTime + patient.duration
                prevIsNoShow = False

            prevWeek = patient.scanWeek
            prevDay  = patient.scanDay

        # finalise last week
        if prevWeek >= WARMUP_WEEKS:
            if nPatientsWeek[0] > 0:
                self.movingAvgElectiveScanWT[prevWeek] /= nPatientsWeek[0]
            if nPatientsWeek[1] > 0:
                self.movingAvgUrgentScanWT[prevWeek]   /= nPatientsWeek[1]
            self.movingAvgOT[prevWeek] /= self.D

        active_weeks = self.W - WARMUP_WEEKS
        if nPatients[0] > 0:
            self.avgElectiveScanWT /= nPatients[0]
        if nPatients[1] > 0:
            self.avgUrgentScanWt   /= nPatients[1]
        if active_weeks > 0:
            self.avgOT /= (self.D * active_weeks)

    # week schedule setup

    def _bw_k(self) -> int:
        """Return K for the Bailey-Welch rule based on self.rule."""
        return {2: 2, 5: 3, 6: 4, 7: 5}.get(self.rule, 2)

    def setWeekSchedule(self) -> None:
        with open(self.inputFileName, 'r', encoding='utf-8-sig') as r:
            slotTypes = list(map(lambda x: re.findall('[0-9]', x), r.readlines()))
        assert len(slotTypes) == 32, "Error: there should be 32 slots in the file"
        for slotIdx, weekSlot in enumerate(slotTypes):
            assert len(weekSlot) == self.D, f"Error: there should be {self.D} days in the file"
            for dayIdx, val in enumerate(weekSlot):
                self.weekSchedule[dayIdx][slotIdx].slotType    = int(val)
                self.weekSchedule[dayIdx][slotIdx].patientType = int(val)

        # overtime slots
        for d in range(self.D):
            for s in range(32, self.S):
                self.weekSchedule[d][s].slotType    = 3
                self.weekSchedule[d][s].patientType = 2

        bw_k = self._bw_k()

        for d in range(self.D):
            time                 = 8.0
            session_start        = 8.0
            elective_in_session  = 0
            elective_block_count = 0
            block_start_time     = 8.0

            for s in range(self.S):
                # detect session transition morning -> afternoon
                if time >= 13.0 and session_start < 13.0:
                    session_start        = 13.0
                    elective_in_session  = 0
                    elective_block_count = 0
                    block_start_time     = 13.0

                self.weekSchedule[d][s].startTime = time

                slot_type = self.weekSchedule[d][s].slotType
                if slot_type != 1:
                    # urgent / OT / closed: appointment time = slot start time
                    self.weekSchedule[d][s].appTime = time
                else:
                    # elective slot: apply rule
                    if self.rule == 1:
                        self.weekSchedule[d][s].appTime = time

                    elif self.rule in (2, 5, 6, 7):
                        # Bailey-Welch generalised to K
                        if elective_in_session < bw_k:
                            self.weekSchedule[d][s].appTime = session_start
                        else:
                            offset = (bw_k - 1) * self.slotLength
                            self.weekSchedule[d][s].appTime = max(session_start, time - offset)
                        elective_in_session += 1

                    elif self.rule == 3:
                        if elective_block_count % 2 == 0:
                            block_start_time = time
                        self.weekSchedule[d][s].appTime = block_start_time
                        elective_block_count += 1

                    elif self.rule == 4:
                        offset = 0.5 * self.stdevElectiveDuration / 60
                        self.weekSchedule[d][s].appTime = max(session_start, time - offset)

                time += self.slotLength
                if abs(time - 12.0) < 1e-9:
                    time = 13.0

    # run all replications

    def runSimulations(self,
                       out_csv: str = None,
                       strategy: int = None,
                       n_urgent: int = None) -> dict:
        """
        Run R replications and return a summary dict.

        Args:
            out_csv:   path for per-replication CSV (optional)
            strategy:  strategy number, written to CSV metadata columns
            n_urgent:  urgent slot count, written to CSV metadata columns

        Returns:
            dict with keys: mean_electiveAppWT, mean_electiveScanWT,
                            mean_urgentScanWT, mean_OT, mean_objective,
                            ci_lo_objective, ci_hi_objective
        """
        self.setWeekSchedule()

        per_rep_objective = []
        per_rep_elAppWT   = []
        per_rep_elScanWT  = []
        per_rep_urScanWT  = []
        per_rep_OT        = []

        print(f"r\telAppWT\t\telScanWT\turScanWT\tOT\t\tOV")
        for r in range(self.R):
            self.resetSystem()
            random.seed(r)
            self.runOneSimulation()

            obj = (self.avgElectiveAppWT * self.weightEl
                   + self.avgUrgentScanWt * self.weightUr)
            per_rep_objective.append(obj)
            per_rep_elAppWT.append(self.avgElectiveAppWT)
            per_rep_elScanWT.append(self.avgElectiveScanWT)
            per_rep_urScanWT.append(self.avgUrgentScanWt)
            per_rep_OT.append(self.avgOT)

            print(f"{r}\t{self.avgElectiveAppWT:.2f}\t\t"
                  f"{self.avgElectiveScanWT:.5f}\t"
                  f"{self.avgUrgentScanWt:.2f}\t\t"
                  f"{self.avgOT:.2f}\t\t{obj:.4f}")

        # summary statistics
        n        = len(per_rep_objective)
        mean_obj = sum(per_rep_objective) / n
        sd_obj   = statistics.stdev(per_rep_objective)

        try:
            from scipy import stats as _stats
            t_crit = _stats.t.ppf(0.975, df=n - 1)
        except ImportError:
            t_crit = 1.96  # fallback z for large n

        hw = t_crit * sd_obj / math.sqrt(n)

        summary = {
            "mean_electiveAppWT":  sum(per_rep_elAppWT)  / n,
            "mean_electiveScanWT": sum(per_rep_elScanWT) / n,
            "mean_urgentScanWT":   sum(per_rep_urScanWT) / n,
            "mean_OT":             sum(per_rep_OT)       / n,
            "mean_objective":      mean_obj,
            "ci_lo_objective":     mean_obj - hw,
            "ci_hi_objective":     mean_obj + hw,
        }

        print("-" * 80)
        print(f"AVG\t{summary['mean_electiveAppWT']:.2f}\t\t"
              f"{summary['mean_electiveScanWT']:.5f}\t"
              f"{summary['mean_urgentScanWT']:.2f}\t\t"
              f"{summary['mean_OT']:.2f}\t\t"
              f"{mean_obj:.4f}  95%CI [{mean_obj - hw:.4f}, {mean_obj + hw:.4f}]")

        # write per-replication CSV
        if out_csv is not None:
            with open(out_csv, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["replication", "strategy", "n_urgent", "rule",
                                 "electiveAppWT", "electiveScanWT",
                                 "urgentScanWT", "OT", "objective"])
                for i, (ea, es, us, ot, ob) in enumerate(
                        zip(per_rep_elAppWT, per_rep_elScanWT,
                            per_rep_urScanWT, per_rep_OT, per_rep_objective)):
                    writer.writerow([i, strategy, n_urgent, self.rule,
                                     ea, es, us, ot, ob])

        # append to master experiment_results_v2.csv
        master       = os.path.join(RESULTS_DIR, "experiment_results_v2.csv")
        write_header = not os.path.exists(master)
        with open(master, "a", newline="") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(["strategy", "n_urgent", "rule",
                                 "mean_electiveAppWT", "mean_electiveScanWT",
                                 "mean_urgentScanWT", "mean_OT",
                                 "mean_objective", "ci_lo_objective", "ci_hi_objective"])
            writer.writerow([strategy, n_urgent, self.rule,
                             summary["mean_electiveAppWT"],
                             summary["mean_electiveScanWT"],
                             summary["mean_urgentScanWT"],
                             summary["mean_OT"],
                             summary["mean_objective"],
                             summary["ci_lo_objective"],
                             summary["ci_hi_objective"]])

        return summary


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    # Total weeks = warm-up + active
    W = WARMUP_WEEKS + 100
    R = 1000

    # ── Full experiment ────────────────────────────────────────────────────
    # Runs all strategies x all N x all rules (including extended BW K=3,4,5).
    # Uncomment when ready — this will take a while.
    #
    RULES = [1, 2, 3, 4, 5, 6, 7]
    
    for strategy in [1, 2, 3]:
        for n_urgent in range(10, 21):
            input_file = os.path.join(
                os.path.dirname(__file__), "..", f"input-S{strategy}-{n_urgent}.txt")
            for rule in RULES:
                tag = f"S{strategy}N{n_urgent}R{rule}"
                print(f"\n{'=' * 60}\nRunning {tag}\n{'=' * 60}")
                sim = Simulation(input_file, W, R, rule)
                sim.runSimulations(
                    out_csv  = os.path.join(RESULTS_DIR, f"replication_analysis_{tag}.csv"),
                    strategy = strategy,
                    n_urgent = n_urgent,
                )