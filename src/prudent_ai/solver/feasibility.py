"""Three-state feasibility classifier (§4 / §7).

For a candidate `x`, a constraint bundle `c`, a confidence filter κ, an
aggregation mode φ, and an evidence regime R, classify each candidate into:

  provably-feasible        — every constraint certified-sat, no required field ⊥
  provably-infeasible      — some constraint certified-violated
  possibly-feasible (F)    — neither; F = required fields that are ⊥ or straddle

This module is **solver-side** (C7): it reads cells *only* through the substrate
interface `cell(x, a)`, and applies κ, φ, R itself. The substrate performs no
filtering, aggregation, or certification.

Constraint operators (Constraint.op):  '>=', '<=', '==', 'in'.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from prudent_ai.solver.beliefs import (
    DEFAULT_KAPPA,
    Belief,
    Phi,
    aggregate,
)
from prudent_ai.solver.regimes import FULL, in_regime

if TYPE_CHECKING:
    from prudent_ai.substrate import Bundle, Substrate


class FeasState(StrEnum):
    PROVABLY_FEASIBLE = "provably_feasible"
    PROVABLY_INFEASIBLE = "provably_infeasible"
    POSSIBLY_FEASIBLE = "possibly_feasible"


@dataclass(frozen=True)
class CandidateVerdict:
    """Result of classifying one candidate against a bundle."""

    config_id: str
    state: FeasState
    pending_fields: frozenset[str]   # required axes that are ⊥ or straddle (the F set)
    cost_belief: Belief              # belief on the 'cost' axis (may be ⊥)


def _certify_numeric(belief: Belief, op: str, target: float, phi: Phi) -> str:
    """Return 'sat' | 'violated' | 'straddle' for a numeric constraint.

    interval mode: certified only if the *whole* interval clears the threshold.
    point mode:    certified on the point estimate (no straddle band).
    """
    if belief.is_bottom:
        return "straddle"   # ⊥ axis is undetermined → treated as straddle/pending

    if phi is Phi.POINT:
        v = belief.point
        if op == ">=":
            return "sat" if v >= target else "violated"
        if op == "<=":
            return "sat" if v <= target else "violated"
        if op == "==":
            return "sat" if v == target else "violated"
        raise ValueError(f"unsupported numeric op: {op}")

    # interval mode — need the whole [lo, hi] to clear
    lo, hi = belief.lo, belief.hi
    if op == ">=":
        if lo >= target:
            return "sat"
        if hi < target:
            return "violated"
        return "straddle"
    if op == "<=":
        if hi <= target:
            return "sat"
        if lo > target:
            return "violated"
        return "straddle"
    if op == "==":
        if lo == hi == target:
            return "sat"
        if lo > target or hi < target:
            return "violated"
        return "straddle"
    raise ValueError(f"unsupported numeric op: {op}")


def classify_candidate(
    sub: Substrate,
    config_id: str,
    bundle: Bundle,
    kappa: tuple[str, ...] = DEFAULT_KAPPA,
    phi: Phi = Phi.INTERVAL,
    regime: frozenset[str] = FULL,
) -> CandidateVerdict:
    """Classify one candidate into the three feasibility states (§4).

    Off-regime axes (a ∉ regime) are treated as ⊥ — the R-restricted rule is
    blind to them (§8.1). This is the only place the regime mask is applied.
    """
    pending: set[str] = set()
    violated = False

    for con in bundle:
        axis = con.axis
        # Regime mask: a rule restricted to R cannot see evidence on a ∉ R.
        if in_regime(axis, regime):
            belief = aggregate(sub.cell(config_id, axis), kappa, phi)
        else:
            belief = Belief(is_bottom=True)

        verdict = _certify_numeric(belief, con.op, float(con.value), phi)
        if verdict == "violated":
            violated = True
        elif verdict == "straddle":
            pending.add(axis)

    # Cost belief (for min-sufficiency ranking) — also subject to the regime mask.
    if in_regime("cost", regime):
        cost_belief = aggregate(sub.cell(config_id, "cost"), kappa, phi)
    else:
        cost_belief = Belief(is_bottom=True)

    if violated:
        state = FeasState.PROVABLY_INFEASIBLE
    elif pending:
        state = FeasState.POSSIBLY_FEASIBLE
    else:
        state = FeasState.PROVABLY_FEASIBLE

    return CandidateVerdict(
        config_id=config_id,
        state=state,
        pending_fields=frozenset(pending),
        cost_belief=cost_belief,
    )
