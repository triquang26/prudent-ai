"""Calibrated transfer (Tier-1).

Predict a distribution-free *interval* for a fragmented-⊥ measurable cell by transfer
from the same model's other benchmarks, then feed the interval — not a point — into the
existing possible-worlds verdict. Commits only when the interval does not straddle the
threshold, inheriting a split-conformal feasibility guarantee P(infeasible | commit) ≤ α.

Boundary (load-bearing): transfer REFUSES on the never-measured structural axes
(governance, reviewer_burden, energy, throughput, memory_hw) — no cross-context signal to
transfer from — so the method abstains there by construction. See `CalibratedTransfer`
and `OverlayedSubstrate`.
"""

from .calibrated_transfer import CalibratedTransfer
from .overlay import OverlayedSubstrate, apply_transfer

__all__ = ["CalibratedTransfer", "OverlayedSubstrate", "apply_transfer"]
