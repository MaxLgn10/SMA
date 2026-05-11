//
//  Simulation.hpp
//  projectSMA
//
//  Created by Tine Meersman on 03/02/2022.
//  Copyright © 2022 Tine Meersman. All rights reserved.
//

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

class simulation{
public:
    struct Slot{
        double startTime;  // start time of the slot (in hours)
        double appTime;    // appointment time of the slot, dependant on type and rule (in hours)
        int slotType;       // type of slot (0=none, 1=elective, 2=urgent within normal working hours, 3=urgent in overtime)
        int patientType;    // (0=none, 1=elective, 2=urgent)
        
        
    };
    
    struct Patient{
        int nr;
        int patientType;    // (0=none, 1=elective, 2=urgent)
        int scanType;       // elective: (0=none), urgent: (0=brain, 1=lumbar, 2=cervival, 3=abdomen, 4=others)
        int callWeek;       // week of arrival (elective: call, urgent: actual arrival)
        int callDay;        // day of arrival (elective: call, urgent: actual arrival)
        double callTime;    // time of arrival (elective: call, urgent: actual arrival) (in hours)
        int scanWeek;       // week of appointment
        int scanDay;        // day of appointment
        int slotNr;         // slot number of appointment
        double appTime;     // time of appointment (elective: according to rule, urgent: slot start time) (in hours)
        double tardiness;   // (in hours)
        bool isNoShow;
        double scanTime;    // actual start time of the scan
        double duration;    // actual duration of the scan
        
        Patient(int nr_, int patientType_, int scanType_, int callWeek_, int callDay_, double callTime_, double tardiness_, bool isNoShow_, double duration_){
            nr = nr_;
            patientType = patientType_;
            scanType = scanType_;
            callWeek = callWeek_;
            callDay = callDay_;
            callTime = callTime_;
            tardiness = tardiness_;
            isNoShow = isNoShow_;
            duration = duration_;
            
            //unplanned
            scanWeek = -1;
            scanDay = -1;
            slotNr = -1;
            appTime = -1;
            scanTime = -1.0;
        }

        double getAppWT(){
            if(slotNr != -1){
                return (double)(((scanWeek-callWeek)*7 + scanDay - callDay)*24 + appTime - callTime); // in hours
            }else{
                printf("CAN NOT CALCULATE APPOINTMENT WT OF PATIENT %d", nr);
                exit(1);
            }
        }
        
        double getScanWT(){
            if(scanTime != 0){
                double wt = 0;
                if(patientType == 1){ // elective
                    wt = scanTime - (appTime + tardiness);
                }else{ // urgent
                    wt = scanTime - callTime;
                }
                return max(0.0,wt);
            }else{
                printf("CAN NOT CALCULATE SCAN WT OF PATIENT %d", nr);  // in hours
                exit(1);
            }
        }
    };

    
    // Variables and parameters
    string inputFileName;
    int D = 6;                         // number of days per week (NOTE: Sunday not included! so do NOT use to calculate appointment waiting time)
    int amountOTSlotsPerDay = 10;      // number of overtime slots per day
    int S = 32 + amountOTSlotsPerDay;  // number of slots per day
    double slotLenght = 15.0 / 60.0;             // duration of a slot (in hours)
    double lambdaElective = 28.345;
    double meanTardiness = 0;
    double stdevTardiness = 2.5;
    double probNoShow = 0.02;
    double meanElectiveDuration = 15;
    double stdevElectiveDuration = 3;
    double lambdaUrgent[2] = {2.5, 1.25};
    double probUrgentType[5] = {0.7, 0.1, 0.1, 0.05, 0.05};
    double cumulativeProbUrgentType[5] = {0.7, 0.8, 0.9, 0.95, 1.0};
    double meanUrgentDuration[5] = {15, 17.5, 22.5, 30, 30};
    double stdevUrgentDuration[5] = {2.5, 1, 2.5, 1, 4.5};
    double weightEl = 1.0 / 168.0;      // objective weight elective appointment wait time
    double weightUr = 1.0 / 9.0;        // objective weight urgent scan wait time
    int W, R;                          // number of weeks (= runs lenght) and number of replications (set their values yourself in the initalization method!)
    int d,s,w,r;
    int rule;                          // the appointment scheduling rule
    Slot **weekSchedule;               // array of the cyclic slot schedule (days-slots)
    
    // Variables within one simuation
    list<Patient> patients;            // patient list
    list<Patient>::iterator patient;   // iterator for patient list
    double *movingAvgElectiveAppWT;    // moving average elective appointment waiting time
    double *movingAvgElectiveScanWT;   // moving average elective scan waiting time
    double *movingAvgUrgentScanWT;     // moving average urgent scan waiting time
    double *movingAvgOT;               // moving average overtime
    double avgElectiveAppWT;           // average elective appointment waiting time
    double avgElectiveScanWT;          // average elective scan waiting time
    double avgUrgentScanWT;            // average urgent scan waiting time
    double avgOT;                      // average overtime
    int numberOfElectivePatientsPlanned, numberOfUrgentPatientsPlanned;
    
    
    
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

#endif /* Simulation_hpp */
