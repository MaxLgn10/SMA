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
const int WINDOW_SIZE = 15; // De 'w' uit Welch's algoritme
const int T0_ESTIMATE = 30; // Welch-analyse: Phoenix stabiliseert rond week 28-30

string city_names[4] = {"Phoenix", "Denver", "Chicago", "Atlanta"};
double P[4][4] = {
    {0.70, 0.06, 0.18, 0.06}, 
    {0.00, 0.70, 0.18, 0.12}, 
    {0.00, 0.15, 0.70, 0.15}, 
    {0.03, 0.03, 0.24, 0.70}  
};

int main() {
    // Y_bar[stad][week] voor het gemiddelde over alle runs
    vector<vector<double>> Y_bar(NUM_CITIES, vector<double>(TOTAL_WEEKS + 1, 0.0));
    // Voor de replicatie-averages (gebruikt voor CI berekening)
    vector<vector<double>> Y_rep_averages(NUM_REPS, vector<double>(NUM_CITIES, 0.0));

    const unsigned int BASE_SEED = 42;
    cout << "Start 10.000 replicaties..." << endl;

    for (int i = 0; i < NUM_REPS; i++) {
        mt19937 gen(BASE_SEED + i); // Reproduceerbaar: vaste base seed + replicatie-index
        int current_cars[4] = {100, 100, 100, 100}; 
        vector<double> city_sums_in_run(NUM_CITIES, 0.0);

        for (int t = 0; t <= TOTAL_WEEKS; t++) {
            for(int c = 0; c < NUM_CITIES; c++) {
                Y_bar[c][t] += current_cars[c];
                if (t >= T0_ESTIMATE) city_sums_in_run[c] += current_cars[c];
            }
            
            // Transitie stap (integer simulatie)
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

        for(int c = 0; c < NUM_CITIES; c++) {
            Y_rep_averages[i][c] = city_sums_in_run[c] / (TOTAL_WEEKS - T0_ESTIMATE + 1);
        }
    }

    // Bereken het gemiddelde over de replicaties (Step 2 Welch)
    for (int t = 0; t <= TOTAL_WEEKS; t++) {
        for (int c = 0; c < NUM_CITIES; c++) Y_bar[c][t] /= NUM_REPS;
    }

    // Export bestand voor grafiek met Welch Moving Average (Step 3 & 4)
    ofstream f_welch("welch_analysis_10k.csv");
    f_welch << "Week,PHX_Raw,DEN_Raw,CHI_Raw,ATL_Raw,PHX_Welch,DEN_Welch,CHI_Welch,ATL_Welch\n";

    for (int t = 1; t <= TOTAL_WEEKS - WINDOW_SIZE; t++) {
        f_welch << t;
        // Raw averages
        for (int c = 0; c < NUM_CITIES; c++) f_welch << "," << Y_bar[c][t];
        
        // Welch Moving Averages per stad
        for (int c = 0; c < NUM_CITIES; c++) {
            double ma = 0;
            if (t <= WINDOW_SIZE) {
                for (int i = 1; i <= 2 * t - 1; i++) ma += Y_bar[c][i];
                ma /= (2 * t - 1);
            } else {
                for (int i = -WINDOW_SIZE; i <= WINDOW_SIZE; i++) ma += Y_bar[c][t + i];
                ma /= (2 * WINDOW_SIZE + 1);
            }
            f_welch << "," << ma;
        }
        f_welch << "\n";
    }
    f_welch.close();

    // Export voor replicatie-averages (Confidence Intervals)
    ofstream f_reps("replication_data.csv");
    f_reps << "Replication,Phoenix,Denver,Chicago,Atlanta\n";
    for (int i = 0; i < NUM_REPS; i++) {
        f_reps << i + 1;
        for (int c = 0; c < NUM_CITIES; c++) f_reps << "," << Y_rep_averages[i][c];
        f_reps << "\n";
    }
    f_reps.close();

    // Console output steady state resultaten
    cout << "\n--- STEADY-STATE RESULTATEN (n=10.000) ---" << endl;
    for(int c = 0; c < NUM_CITIES; c++) {
        double total_ss = 0;
        for(int t = T0_ESTIMATE; t <= TOTAL_WEEKS; t++) total_ss += Y_bar[c][t];
        double final_avg = total_ss / (TOTAL_WEEKS - T0_ESTIMATE + 1);
        cout << left << setw(10) << city_names[c] 
             << ": " << fixed << setprecision(2) << final_avg << " auto's "
             << "(prob: " << setprecision(4) << final_avg/TOTAL_CARS << ")" << endl;
    }

    return 0;
}