#include "Helper.hpp"

#include <cmath>

// Fix 1: full double-precision uniform, not rand() % 1000 (1000 values only).
static std::uniform_real_distribution<double> uniform_dist(0.0, 1.0);

uint32_t derive_seed(int base_seed, int stream_id) {
    // Multiplicative hash to mix base seed and stream id into a unique seed.
    uint32_t h = (uint32_t)(base_seed * 2654435761u) ^ (uint32_t)(stream_id * 2246822519u);
    h ^= h >> 16;
    h *= 0x45d9f3bu;
    h ^= h >> 16;
    return h;
}

double Exponential_distribution(double lambda, std::mt19937& rng) {
    double u = uniform_dist(rng);
    if (u <= 0.0) u = 1e-15;
    return -std::log(u) / lambda;
}

double Normal_distribution(double mean, double stdev, std::mt19937& rng) {
    double v1, v2, t;
    do {
        v1 = 2.0 * uniform_dist(rng) - 1.0;
        v2 = 2.0 * uniform_dist(rng) - 1.0;
        t = v1 * v1 + v2 * v2;
    } while (t >= 1.0 || t == 0.0);
    double multiplier = std::sqrt(-2.0 * std::log(t) / t);
    return v1 * multiplier * stdev + mean;
}

// Fix 3: truncated normal — redraws until value >= 0 (scan durations only).
double Normal_distribution_truncated(double mean, double stdev, std::mt19937& rng) {
    double val;
    do {
        val = Normal_distribution(mean, stdev, rng);
    } while (val < 0.0);
    return val;
}

int Bernouilli_distribution(double prob, std::mt19937& rng) {
    return uniform_dist(rng) < prob ? 1 : 0;
}

double Uniform_distribution(std::mt19937& rng) {
    return uniform_dist(rng);
}
