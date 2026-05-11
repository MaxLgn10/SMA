#ifndef Helper_hpp
#define Helper_hpp

#include <random>
#include <cstdint>

// Derives a reproducible stream-specific seed from a base replication seed.
// Using different stream_id values ensures independent streams per component.
uint32_t derive_seed(int base_seed, int stream_id);

// All distribution functions take an explicit mt19937 stream — no global state.
double Exponential_distribution(double lambda, std::mt19937& rng);

// Plain normal (for tardiness, which can legitimately be negative).
double Normal_distribution(double mean, double stdev, std::mt19937& rng);

// Truncated normal: rejects draws < 0 (scan durations cannot be negative).
double Normal_distribution_truncated(double mean, double stdev, std::mt19937& rng);

int Bernouilli_distribution(double prob, std::mt19937& rng);

double Uniform_distribution(std::mt19937& rng);

#endif
