#include "Helper.hpp"

#include <cmath>
#include <cstdlib>

static double uniform01_legacy() {
    return static_cast<double>(rand() % 1000) / 1000.0;
}

double Exponential_distribution(double lambda) {
    double u = uniform01_legacy();
    if (u <= 0.0) u = 0.0001;
    return -log(u) / lambda;
}

int Poisson_distribution(double lambda) {
    double u = uniform01_legacy();
    double cumulative = 0.0;
    double probability = exp(-lambda);
    int k = 0;

    while (true) {
        cumulative += probability;
        if (u <= cumulative) return k;
        k++;
        probability *= lambda / k;
    }
}

double Normal_distribution(double mean, double stdev) {
    double v1, v2, t;
    do {
        v1 = 2.0 * uniform01_legacy() - 1.0;
        v2 = 2.0 * uniform01_legacy() - 1.0;
        t = v1 * v1 + v2 * v2;
    } while (t >= 1.0 || t == 0.0);

    double multiplier = sqrt(-2.0 * log(t) / t);
    return v1 * multiplier * stdev + mean;
}

int Bernouilli_distribution(double prob) {
    return uniform01_legacy() < prob ? 1 : 0;
}

int Uniform_distribution(double a, double b) {
    double u = uniform01_legacy();
    return static_cast<int>(a + (b - a) * u);
}

int Triangular_distribution(int a, int b, int c) {
    double u = uniform01_legacy();
    double f = static_cast<double>(b - a) / static_cast<double>(c - a);

    if (u < f) {
        return static_cast<int>(a + sqrt(u * (b - a) * (c - a)));
    }
    return static_cast<int>(c - sqrt((1.0 - u) * (c - b) * (c - a)));
}
