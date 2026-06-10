"""Stub solvers for P1 — proving C7 (substrate ⊥ solver).

These are minimum-viable stubs: they make the correct substrate calls and
return plausible outputs, but their solve quality is irrelevant for P1.
The gate test (test_interface_invariance) checks only that both solvers
make an identical multiset of substrate calls.

Two solvers:
  solve_lexicographic(sub, q, kappa)              — phi=interval
  solve_chance_constrained(sub, q, kappa, alpha)  — phi=distribution

Shared infrastructure:
  _evaluate_all_cells(sub, q, kappa)
    Makes the three substrate calls (candidates / required_fields / cell)
    in a deterministic order.  Both solvers call this helper identically;
    they differ only in the aggregation applied to the returned observations.

  Query
    Plain dataclass: tau (str) + bundle (Bundle).

Design note on C7:
  By routing all substrate access through the shared _evaluate_all_cells
  helper, we prove at the code level that neither phi nor kappa influence
  *which* calls are made to the substrate — only how the returned
  observations are subsequently aggregated.  The gate test verifies this
  property at the call-multiset level.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prudent_ai.substrate import Bundle, Candidate, Observation, Substrate


# ---------------------------------------------------------------------------
# Query type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Query:
    """A deployment-context query passed to a solver.

    Attributes:
        tau:    Deployment-context tag identifying the candidate set.
        bundle: Tuple of Constraints describing the solver's requirements.
    """

    tau: str
    bundle: Bundle


# ---------------------------------------------------------------------------
# Shared substrate-access helper (the key to C7)
# ---------------------------------------------------------------------------


def _evaluate_all_cells(
    sub: Substrate,
    q: Query,
    kappa: tuple[str, ...],  # accepted for signature parity; NOT used for filtering here
) -> tuple[list[Candidate], set[str], dict[tuple[str, str], list[Observation]]]:
    """Fetch candidates, required axes, and every (candidate, axis) cell.

    This is the single point that issues all three substrate calls.  Both
    solvers invoke it identically, guaranteeing an identical substrate call
    multiset regardless of phi or kappa.

    Note: kappa is accepted as a parameter so callers can pass it through
    naturally, but it is NOT used here — the substrate is kappa-free.
    Confidence filtering happens in the solver-side aggregation step, after
    this function returns.

    Args:
        sub:   The Substrate instance.
        q:     The query (tau + bundle).
        kappa: Confidence tiers the solver will accept (solver-side policy,
               not used in substrate calls).

    Returns:
        (cands, axes, cells) where:
          cands  — list[Candidate] from sub.candidates(q.tau)
          axes   — set[str] from sub.required_fields(q.bundle)
          cells  — dict mapping (config_id, axis) -> list[Observation]
                   for every (cand, axis) pair, in sorted(axes) order.
    """
    cands = sub.candidates(q.tau)               # substrate call 1
    axes = sub.required_fields(q.bundle)        # substrate call 2

    cells: dict[tuple[str, str], list[Observation]] = {}
    for cand in cands:
        for axis in sorted(axes):               # deterministic call order
            cells[(cand.id, axis)] = sub.cell(cand.id, axis)  # substrate call 3..N

    return cands, axes, cells


# ---------------------------------------------------------------------------
# Solver 1: lexicographic (phi = interval)
# ---------------------------------------------------------------------------


def solve_lexicographic(
    sub: Substrate,
    q: Query,
    kappa: tuple[str, ...],
) -> Candidate:
    """Minimum-viable lexicographic solver (phi=interval).

    Aggregation: for each (candidate, axis) cell, keep observations whose
    confidence is in kappa, then compute (lo=min, hi=max) over numeric values.
    Candidates with no qualifying observations on an axis get None (⊥) for
    that axis.

    Selection: prefer the candidate with the highest lo-bound on 'quality';
    break ties by candidate id for determinism.

    Args:
        sub:   Substrate instance.
        q:     Query specifying tau and bundle.
        kappa: Accepted confidence tiers, e.g. ('H', 'M').

    Returns:
        The selected Candidate.
    """
    cands, axes, cells = _evaluate_all_cells(sub, q, kappa)

    # Solver-side aggregation: interval
    scores: dict[str, dict[str, tuple[float, float] | None]] = {}
    for cand in cands:
        beliefs: dict[str, tuple[float, float] | None] = {}
        for axis in axes:
            obs = cells[(cand.id, axis)]
            active = [o for o in obs if o.confidence in kappa]
            if not active:
                beliefs[axis] = None  # ⊥
            else:
                vals = [o.value_num for o in active if o.value_num is not None]
                if vals:
                    beliefs[axis] = (min(vals), max(vals))
                else:
                    beliefs[axis] = (0.0, 1.0)  # categorical fallback
        scores[cand.id] = beliefs

    # Lex selection: highest lo-bound on quality; tie-break by cand.id
    def _lex_key(cand: Candidate) -> tuple[float, str]:
        interval = scores[cand.id].get("quality")
        lo = interval[0] if interval is not None else 0.0
        return (lo, cand.id)

    return max(cands, key=_lex_key)


# ---------------------------------------------------------------------------
# Solver 2: chance-constrained (phi = distribution)
# ---------------------------------------------------------------------------


def solve_chance_constrained(
    sub: Substrate,
    q: Query,
    kappa: tuple[str, ...],
    alpha: float,
) -> Candidate:
    """Minimum-viable chance-constrained solver (phi=distribution).

    Aggregation: for each (candidate, axis) cell, keep observations whose
    confidence is in kappa, then compute (mean, std) over numeric values.
    Candidates with no qualifying observations on an axis get None (⊥).

    Selection: find candidates where the mean quality >= (1 - alpha);
    return the first feasible one (by candidates() order) or fall back to
    the first candidate if none is feasible.

    Args:
        sub:   Substrate instance.
        q:     Query specifying tau and bundle.
        kappa: Accepted confidence tiers, e.g. ('H', 'M').
        alpha: Risk tolerance (0 < alpha < 1).  A candidate is feasible
               when its mean quality estimate >= 1 - alpha.

    Returns:
        The selected Candidate.
    """
    cands, axes, cells = _evaluate_all_cells(sub, q, kappa)

    # Solver-side aggregation: distribution (mean, std)
    scores: dict[str, dict[str, tuple[float, float] | None]] = {}
    for cand in cands:
        probs: dict[str, tuple[float, float] | None] = {}
        for axis in axes:
            obs = cells[(cand.id, axis)]
            active = [o for o in obs if o.confidence in kappa]
            if not active:
                probs[axis] = None  # ⊥
            else:
                vals = [o.value_num for o in active if o.value_num is not None]
                if vals:
                    mean = sum(vals) / len(vals)
                    # Std dev: 0.0 for single obs, else sample std
                    if len(vals) > 1:
                        variance = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
                        std = variance ** 0.5
                    else:
                        std = 0.0
                    probs[axis] = (mean, std)
                else:
                    probs[axis] = (0.5, 0.5)  # categorical fallback
        scores[cand.id] = probs

    # Chance selection: quality mean >= 1 - alpha
    threshold = 1.0 - alpha
    feasible = [
        c for c in cands
        if (scores[c.id].get("quality") or (0.0, 0.0))[0] >= threshold
    ]
    return feasible[0] if feasible else cands[0]
