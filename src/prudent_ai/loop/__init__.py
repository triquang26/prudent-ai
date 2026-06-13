"""Live acquisition loop (Tier-3).

Close the selective procedure's loop for real: when a query is underdetermined, rank the
blocking axes by VoI/cost, *actually acquire* the top measurable axis (reveal its measured
value into a scratch overlay — never the frozen store), re-run the verdict, and commit or
re-rank. Governance cannot be looped (no config↔audit data exists); the loop raises rather
than fake it.
"""

from .live_acquisition import LiveAcquisitionLoop, LoopResult, NoMeasurementPathError

__all__ = ["LiveAcquisitionLoop", "LoopResult", "NoMeasurementPathError"]
