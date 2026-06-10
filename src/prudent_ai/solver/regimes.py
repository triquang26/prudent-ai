"""Evidence regimes — R ⊆ A (§8.1).

An *evidence regime* `R` is the set of axes on which a rule is permitted to
depend. A rule is **R-restricted** if it reads B_E only through axes in R
(§8.1). We realize this solver-side: when classifying under regime R, any axis
`a ∉ R` is treated as ⊥ regardless of what the substrate holds — the rule is
*blind* to off-regime evidence.

This is the IV ablation of §16 (accuracy-only → +cost → +energy → full) and the
mechanism that makes the limit theorem (§8) empirically visible: a query whose
binding axis lies outside R must be underdetermined for every R-restricted rule.
"""

from __future__ import annotations

# The eight right-sizing axes (§5 / §1).
ALL_AXES: frozenset[str] = frozenset({
    "quality",
    "latency_p95",
    "throughput",
    "cost",
    "energy",
    "memory_hw",
    "governance",
    "reviewer_burden",
})

# Named regimes, ordered from leaderboard-poor to full. Each is the IV ladder
# in §16: accuracy-only → +cost → +latency → +energy → full.
ACCURACY_ONLY: frozenset[str] = frozenset({"quality"})
ACC_COST: frozenset[str] = frozenset({"quality", "cost"})
ACC_COST_LATENCY: frozenset[str] = frozenset({"quality", "cost", "latency_p95"})
ACC_COST_LATENCY_THROUGHPUT: frozenset[str] = frozenset(
    {"quality", "cost", "latency_p95", "throughput"}
)
PLUS_ENERGY: frozenset[str] = frozenset(
    {"quality", "cost", "latency_p95", "throughput", "energy"}
)
FULL: frozenset[str] = ALL_AXES

# The regime ladder used by the decidability map, in order.
REGIME_LADDER: list[tuple[str, frozenset[str]]] = [
    ("accuracy_only", ACCURACY_ONLY),
    ("acc_cost", ACC_COST),
    ("acc_cost_latency", ACC_COST_LATENCY),
    ("acc_cost_lat_throughput", ACC_COST_LATENCY_THROUGHPUT),
    ("plus_energy", PLUS_ENERGY),
    ("full", FULL),
]


def in_regime(axis: str, regime: frozenset[str]) -> bool:
    """True iff the rule may see evidence on *axis* under *regime*."""
    return axis in regime
