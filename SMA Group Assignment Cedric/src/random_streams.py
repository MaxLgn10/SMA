"""
RandomStreamManager: provides independent, reproducible numpy RNG streams per event type.

Using Common Random Numbers (CRN): every configuration uses the same seeds per replication.
Each stream is seeded deterministically from a base seed and a stream name, so that:
  - Across configs, the same replication uses the same random numbers → variance reduction.
  - Across replications, different seeds ensure statistical independence.

Stream names mirror the six random components identified in the assignment.
"""
from __future__ import annotations

import hashlib
import numpy as np
from typing import Dict

STREAM_NAMES = [
    "elective_arrival",   # call interarrival times
    "urgent_arrival",     # urgent patient interarrival times
    "elective_scan",      # elective scan durations
    "urgent_scan",        # urgent scan durations (includes type selection)
    "tardiness",          # punctuality deviation from appointment
    "no_show",            # no-show Bernoulli draws
]


class RandomStreamManager:
    """
    Manages one independent numpy.random.Generator per stream name.

    Usage:
        rsm = RandomStreamManager(base_seed=42)
        rng = rsm.get("elective_scan")
        duration = elective_scan_duration(rng)
    """

    def __init__(self, base_seed: int):
        self._streams: Dict[str, np.random.Generator] = {}
        for name in STREAM_NAMES:
            seed = _derive_seed(base_seed, name)
            self._streams[name] = np.random.default_rng(seed)

    def get(self, name: str) -> np.random.Generator:
        if name not in self._streams:
            raise KeyError(f"Unknown stream '{name}'. Valid streams: {STREAM_NAMES}")
        return self._streams[name]

    @property
    def stream_names(self) -> list[str]:
        return list(STREAM_NAMES)


def make_replication_seed(replication: int, stream_name: str) -> int:
    """
    Derive a unique integer seed for a (replication, stream_name) pair.
    Used when you want to create streams independently without a manager.
    """
    return _derive_seed(replication, stream_name)


def _derive_seed(base: int, name: str) -> int:
    """
    Hash (base, name) to a 32-bit integer seed, giving a different RNG per stream
    while staying fully deterministic across runs.
    """
    digest = hashlib.sha256(f"{base}:{name}".encode()).digest()
    return int.from_bytes(digest[:4], "big")
