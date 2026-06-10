"""Query objects (§1 / §5) — a query is q = (τ, hard-constraint bundle).

A query asks: under archetype τ and hard constraints c, what is the
minimum-sufficient configuration? The decidability classifier answers whether
the *evidence* identifies that decision at all.

This module holds the plain data types. Grounded grid generation (choosing
realistic thresholds from observed values) lives in `analysis/`, which reads the
substrate to set percentile thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass

from prudent_ai.substrate import Constraint

# A bundle is a tuple of hard constraints (immutable, hashable).
Bundle = tuple[Constraint, ...]


@dataclass(frozen=True)
class Query:
    """q = (τ, c). `bundle` is the hard-constraint bundle c."""

    tau: str
    bundle: Bundle
    label: str = ""   # human-readable tag, e.g. "latency-bound" (optional)

    @property
    def constrained_axes(self) -> frozenset[str]:
        """The axes the bundle places a constraint on (syntactic; cf. C7)."""
        return frozenset(c.axis for c in self.bundle)


def make_query(
    tau: str,
    constraints: list[tuple[str, str, float]],
    label: str = "",
) -> Query:
    """Build a Query from (axis, op, target) triples.

    Example:
        make_query("function-calling",
                   [("quality", ">=", 0.7), ("latency_p95", "<=", 5000.0)],
                   label="quality+latency")
    """
    bundle = tuple(Constraint(axis=a, op=op, value=t) for a, op, t in constraints)
    return Query(tau=tau, bundle=bundle, label=label)
