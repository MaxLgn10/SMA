#include <iostream>
#include <vector>
#include <random>
#include <fstream>
#include <iomanip>
#include <cmath>

using namespace std;

// Parameters
const int NUM_REPS = 10000;    
const int NUM_CITIES = 4;
const int TOTAL_CARS = 400;
const int TOTAL_WEEKS = 200;   
const int T0 = 30; // Welch-analyse: Phoenix stabiliseert rond week 28-30

string city_names[4] = {"Phoenix", "Denver", "Chicago", "Atlanta"};
double P[4][4] = {
    {0.70, 0.06, 0.18, 0.06}, 
    {0.00, 0.70, 0.18, 0.12}, 
    {0.00, 0.15, 0.70, 0.15}, 
    {0.03, 0.03, 0.24, 0.70}  
};

int main() {
    // Y_weekly_sum: gemiddelde per week over alle runs
    vector<vector<double>> Y_weekly_sum(NUM_CITIES, vector<double>(TOTAL_WEEKS + 1, 0.0));
    
    // Y_rep_averages: het gemiddelde van ELKE replicatie (voor betrouwbaarheidsintervallen)
    vector<vector<double>> Y_rep_averages(NUM_REPS, vector<double>(NUM_CITIES, 0.0));

    const unsigned int BASE_SEED = 42;
    cout << "Start schattingsfase met t0 = " << T0 << " en 10.000 runs..." << endl;

    for (int i = 0; i < NUM_REPS; i++) {
        mt19937 gen(BASE_SEED + i); // Reproduceerbaar: vaste base seed + replicatie-index
        int current_cars[4] = {100, 100, 100, 100}; 

        vector<double> city_sums_in_run(NUM_CITIES, 0.0);

        for (int t = 0; t <= TOTAL_WEEKS; t++) {
            for(int c = 0; c < NUM_CITIES; c++) {
                Y_weekly_sum[c][t] += current_cars[c];
                
                // Alleen data vanaf t0 gebruiken voor de steady-state schatting
                if (t >= T0) {
                    city_sums_in_run[c] += current_cars[c];
                }
            }
            
            // Integer simulatie stap
            int next_cars[4] = {0, 0, 0, 0};
            for (int city = 0; city < NUM_CITIES; city++) {
                vector<double> weights(P[city], P[city] + 4);
                discrete_distribution<int> dist(weights.begin(), weights.end());
                for (int car = 0; car < current_cars[city]; car++) {
                    next_cars[dist(gen)]++; 
                }
            }
            for (int c = 0; c < NUM_CITIES; c++) current_cars[c] = next_cars[c];
        }

        // Bereken gemiddelde per replicatie over de steady-state periode
        for(int c = 0; c < NUM_CITIES; c++) {
            Y_rep_averages[i][c] = city_sums_in_run[c] / (TOTAL_WEEKS - T0 + 1);
        }
    }

    // Bestand 1: Wekelijkse gemiddelden (10.000 runs gemiddelde per week)
    ofstream f_weekly("Final_weekly_averages.csv");
    f_weekly << "Week,Phoenix,Denver,Chicago,Atlanta\n";
    for (int t = 0; t <= TOTAL_WEEKS; t++) {
        f_weekly << t;
        for (int c = 0; c < NUM_CITIES; c++) f_weekly << "," << fixed << setprecision(4) << Y_weekly_sum[c][t] / NUM_REPS;
        f_weekly << "\n";
    }
    f_weekly.close();

    // Bestand 2: Gemiddelde per replicatie (10.000 onafhankelijke waarnemingen)
    ofstream f_reps("Final_replication_averages.csv");
    f_reps << "Replication,Phoenix_Avg,Denver_Avg,Chicago_Avg,Atlanta_Avg\n";
    for (int i = 0; i < NUM_REPS; i++) {
        f_reps << i + 1;
        for (int c = 0; c < NUM_CITIES; c++) f_reps << "," << fixed << setprecision(4) << Y_rep_averages[i][c];
        f_reps << "\n";
    }
    f_reps.close();

    // Console output met definitieve steady-state schattingen
    cout << "\n--- DEFINITIEVE STEADY-STATE SCHATTINGEN ---" << endl;
    cout << left << setw(10) << "Stad" << setw(18) << "Gem. Auto's" << "Kans (pi)" << endl;
    for(int c = 0; c < NUM_CITIES; c++) {
        double final_avg = 0;
        for (int i = 0; i < NUM_REPS; i++) final_avg += Y_rep_averages[i][c];
        final_avg /= NUM_REPS;

        cout << left << setw(10) << city_names[c] 
             << setw(18) << (int)round(final_avg) // Afgerond naar integer zoals gevraagd
             << fixed << setprecision(4) << final_avg / TOTAL_CARS << endl;
    }

    return 0;
}