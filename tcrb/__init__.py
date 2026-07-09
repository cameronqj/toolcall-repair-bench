"""toolcall-repair-bench (tcrb).

A vendor-neutral, hermetic, deterministic benchmark for local-model tool-call
repair. The package scores repair adapters against an offline corpus of real
raw local-model outputs. Everything here is offline: no network, no GPU, no
wall-clock, no randomness.
"""

__version__ = "0.1.0"
